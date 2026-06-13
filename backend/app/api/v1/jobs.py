import os
import shutil
import aiofiles
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.models.job import Job
from app.models.app_config import AppConfig
from app.core.config import settings

router = APIRouter()

@router.get("/jobs")
def list_jobs(page: int = 1, limit: int = 20, status: str = None, db: Session = Depends(get_db)):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    total = query.count()
    jobs = query.order_by(Job.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return {"total": total, "items": jobs}

@router.post("/jobs", status_code=201)
async def create_job(
    file: UploadFile = File(...),
    options: str = Form(None),
    db: Session = Depends(get_db)
):
    from app.services.storage_guard import check_disk_space
    check_disk_space(db)

    # Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg"]:
        raise HTTPException(status_code=400, detail="Unsupported file format")
        
    import json
    parsed_options = {}
    if options:
        try:
            parsed_options = json.loads(options)
        except json.JSONDecodeError:
            pass

    job = Job(
        input_filename=file.filename,
        input_format=ext[1:].upper(),
        input_size_bytes=0, # updated after write
        storage_input_path="",
        progress_stage="uploading",
        options=parsed_options
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Save file to STORAGE_ROOT/job_id/input.ext
    job_dir = os.path.join(settings.STORAGE_ROOT, str(job.id))
    os.makedirs(job_dir, exist_ok=True)
    input_path = os.path.join(job_dir, f"input{ext}")
    
    size = 0
    # Patch 12.2 流式上传
    async with aiofiles.open(input_path, "wb") as buffer:
        while True:
            chunk = await file.read(1024 * 1024) # 1MB chunks
            if not chunk:
                break
            await buffer.write(chunk)
            size += len(chunk)
        
    job.input_size_bytes = size
    job.storage_input_path = input_path
    job.status = "PENDING"
    db.commit()
    
    # Pre-estimate cost (simulation based on size: 1 token per 4 bytes roughly)
    est_tokens = int(size / 4)
    est_calls = max(1, int(est_tokens / 4000))
    
    config = db.query(AppConfig).filter(AppConfig.id == 1).first()
    est_vlm_calls = 0 # Will be updated by worker after Docling conversion
    
    # Enqueue Celery task (Task 7)
    from app.worker.celery_app import celery_app
    celery_app.send_task("app.worker.tasks.convert_task", args=[str(job.id)])
    
    return {
        "job_id": str(job.id),
        "status": job.status,
        "created_at": job.created_at,
        "estimated_llm_calls": est_calls,
        "estimated_vlm_calls": est_vlm_calls,
        "estimated_input_tokens": est_tokens
    }

@router.get("/jobs/{job_id}/result")
def get_job_result(job_id: str, db: Session = Depends(get_db)):
    from app.models.document import Document
    doc = db.query(Document).filter(Document.job_id == job_id).first()
    job = db.query(Job).filter(Job.id == job_id).first()
    if not doc or not job:
        raise HTTPException(status_code=404, detail="Result not found or job pending")
    return {
        "job_id": job_id,
        "markdown": doc.markdown_content,
        "metadata": doc.metadata_json,
        "page_count": doc.page_count,
        "input_filename": job.input_filename
    }

@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str, db: Session = Depends(get_db)):
    from app.models.document import Document
    import uuid
    try:
        j_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID")
    job = db.query(Job).filter(Job.id == j_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    doc = db.query(Document).filter(Document.job_id == job_id).first()
    if doc:
        db.delete(doc)
    
    db.delete(job)
    db.commit()
    
    # Clean up files
    job_dir = os.path.join(settings.STORAGE_ROOT, str(job_id))
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir)
    return None
