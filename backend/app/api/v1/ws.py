import asyncio
import json
import redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.models.job import Job
from app.core.config import settings

router = APIRouter()

@router.websocket("/ws/jobs/{job_id}")
async def websocket_progress(websocket: WebSocket, job_id: str, db: Session = Depends(get_db)):
    await websocket.accept()
    
    import uuid
    from sqlalchemy.exc import DataError

    try:
        uuid_obj = uuid.UUID(job_id)
    except ValueError:
        await websocket.send_json({"type": "failed", "job_id": job_id, "error": "Invalid Job ID format"})
        await websocket.close(code=1000)
        return

    # 1. Database compensation query
    try:
        job = db.query(Job).filter(Job.id == str(uuid_obj)).first()
    except DataError:
        db.rollback()
        job = None

    if not job:
        await websocket.send_json({"type": "failed", "job_id": job_id, "error": "Job not found"})
        await websocket.close(code=1000)
        return
        
    # 2. Terminal state closure check
    if job.status in ["SUCCESS", "FAILED", "CANCELLED"]:
        if job.status == "SUCCESS":
            await websocket.send_json({"type": "completed", "job_id": job_id})
        else:
            await websocket.send_json({"type": "failed", "job_id": job_id, "error": job.error_message})
        await websocket.close(code=1000)
        return
        
    # 3. Non-terminal: Push initial DB snapshot to prevent progress freeze on reload
    await websocket.send_json({
        "type": "snapshot",
        "job_id": job_id,
        "status": job.status,
        "stage": job.progress_stage,
        "percent": job.progress_percent,
        "message": f"Reconnected: resuming progress from {job.progress_percent}%"
    })
    
    # 4. Subscribe to Redis Pub/Sub for subsequent events
    r_client = redis.Redis.from_url(settings.REDIS_URL)
    pubsub = r_client.pubsub()
    pubsub.subscribe(f"job:{job_id}:progress")
    
    async def listen_redis():
        try:
            while True:
                # Non-blocking check
                message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    data = json.loads(message['data'].decode('utf-8'))
                    await websocket.send_json(data)
                    if data.get("type") in ["completed", "failed"]:
                        break
                await asyncio.sleep(0.1)
        except Exception:
            pass
            
    try:
        await listen_redis()
    except WebSocketDisconnect:
        pass
    finally:
        pubsub.unsubscribe()
        pubsub.close()
        # Ensure websocket is closed
        try:
            await websocket.close(code=1000)
        except RuntimeError:
            pass
