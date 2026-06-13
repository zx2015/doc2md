import os
import sys
from unittest.mock import MagicMock

# Mock torch and docling before importing docling_service
sys.modules['torch'] = MagicMock()
sys.modules['docling'] = MagicMock()
sys.modules['docling.document_converter'] = MagicMock()
sys.modules['docling.datamodel'] = MagicMock()
sys.modules['docling.datamodel.pipeline_options'] = MagicMock()
sys.modules['docling.datamodel.base_models'] = MagicMock()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import pytest
import torch
from app.services.docling_service import resolve_device

def test_resolve_device():
    # Test fallback to CPU when CUDA is explicitly requested but not available
    torch.cuda.is_available.return_value = False
    assert resolve_device("cuda") == "cpu"
    
    # Test CPU explicitly requested
    assert resolve_device("cpu") == "cpu"
    
    # Test AUTO
    torch.cuda.is_available.return_value = True
    assert resolve_device("auto") == "cuda"
