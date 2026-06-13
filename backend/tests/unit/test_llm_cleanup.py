import os
import sys
from unittest.mock import MagicMock, AsyncMock



sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import pytest
import asyncio
from app.services.llm_service import clean_chunk
from app.services.cleanup import collapse_whitespace

def test_collapse_whitespace():
    raw = "Hello\n\n\nWorld  \n"
    res = collapse_whitespace(raw)
    assert res == "Hello\n\nWorld\n"

@pytest.mark.asyncio
async def test_clean_chunk_success():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="Cleaned text"))]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
    
    res = await clean_chunk(mock_client, "Raw chunk", 1, 1, "gpt-4o", "balanced")
    assert res == "Cleaned text"

@pytest.mark.asyncio
async def test_clean_chunk_degradation():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
    
    res = await clean_chunk(mock_client, "Raw chunk", 1, 1, "gpt-4o", "balanced")
    assert res == "Raw chunk" # Falls back to original text
