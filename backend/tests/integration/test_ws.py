import sys
import os
import pytest
from unittest.mock import MagicMock, patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.job import Job

client = TestClient(app)

import uuid

def test_websocket_job_not_found():
    non_existent = str(uuid.uuid4())
    with client.websocket_connect(f"/api/v1/ws/jobs/{non_existent}") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "failed"
        assert data["error"] == "Job not found"

def test_websocket_terminal_success():
    db = SessionLocal()
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id, status="SUCCESS", progress_stage="done", progress_percent=100,
        input_filename="test.pdf", input_format="PDF", input_size_bytes=100, storage_input_path="/tmp/test.pdf"
    )
    db.add(job)
    db.commit()
    
    try:
        with client.websocket_connect(f"/api/v1/ws/jobs/{job.id}") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "completed"
            assert data["job_id"] == str(job.id)
    finally:
        db.delete(job)
        db.commit()
        db.close()

def test_websocket_non_terminal_snapshot():
    db = SessionLocal()
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id, status="RUNNING", progress_stage="ocr", progress_percent=50,
        input_filename="test.pdf", input_format="PDF", input_size_bytes=100, storage_input_path="/tmp/test.pdf"
    )
    db.add(job)
    db.commit()
    
    # Mock redis so it doesn't try to connect to a real redis server in the loop
    with patch("app.api.v1.ws.redis.Redis.from_url") as mock_redis:
        mock_pubsub = MagicMock()
        mock_redis.return_value.pubsub.return_value = mock_pubsub
        
        with client.websocket_connect(f"/api/v1/ws/jobs/{job.id}") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "snapshot"
            assert data["percent"] == 50
            assert data["stage"] == "ocr"
            
    db.delete(job)
    db.commit()
    db.close()
