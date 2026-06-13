import os
import sys
import pytest
import subprocess
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.mineru_service import run_mineru_conversion

@patch("subprocess.run")
def test_run_mineru_conversion_success(mock_run):
    # Mock subprocess success and file read
    mock_run.return_value = MagicMock(stdout="Success", returncode=0)
    
    mock_open_content = "Parsed markdown content"
    
    # We need to mock open() to avoid reading actual filesystem during unit test
    with patch("builtins.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=mock_open_content)))))):
        with patch("os.path.exists", return_value=True):
            from pathlib import Path as RealPath
            with patch("pathlib.Path.rglob", return_value=[RealPath("/tmp/out/dummy/dummy.md")]):
                res, real_dir = run_mineru_conversion("dummy.pdf", "/tmp/out")
                assert res == mock_open_content
                assert real_dir == "/tmp/out/dummy"

@patch("subprocess.run")
def test_run_mineru_conversion_failure(mock_run):
    # Mock subprocess failure with stderr
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=["magic-pdf"],
        output="CLI Output",
        stderr="CLI Error Message"
    )
    
    with pytest.raises(RuntimeError) as exc_info:
        run_mineru_conversion("dummy.pdf", "/tmp/out")
    
    assert "MinerU conversion failed" in str(exc_info.value)
    assert "CLI Error Message" in str(exc_info.value)

@patch("subprocess.run")
def test_run_mineru_conversion_timeout(mock_run):
    # Mock subprocess timeout
    mock_run.side_effect = subprocess.TimeoutExpired(
        cmd=["magic-pdf"],
        timeout=600
    )
    
    with pytest.raises(RuntimeError) as exc_info:
        run_mineru_conversion("dummy.pdf", "/tmp/out")
        
    assert "MinerU conversion timed out" in str(exc_info.value)

@patch("subprocess.run")
def test_run_mineru_conversion_no_md_file(mock_run):
    # Mock subprocess success but no .md file is generated
    mock_run.return_value = MagicMock(stdout="Success", returncode=0)
    
    from pathlib import Path as RealPath
    with patch("pathlib.Path.rglob", return_value=[]):
        with pytest.raises(RuntimeError) as exc_info:
            run_mineru_conversion("dummy.pdf", "/tmp/out")
            
        assert "MinerU conversion failed" in str(exc_info.value)
        assert "No .md produced." in str(exc_info.value)
