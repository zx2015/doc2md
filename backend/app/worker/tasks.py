import redis
import json
import os
import shutil
import asyncio
import re
from datetime import datetime, timedelta, timezone
from app.worker.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.job import Job
from app.models.document import Document
from app.models.app_config import AppConfig
from app.services.docling_service import run_docling_conversion
from app.services.llm_service import clean_document_llm
from app.core.security import decrypt_key
from app.core.config import settings

r_client = redis.Redis.from_url(celery_app.conf.broker_url)

def broadcast_progress(job_id: str, percent: int, stage: str, message: str):
    payload = {
        "type": "progress",
        "job_id": job_id,
        "stage": stage,
        "percent": percent,
        "message": message
    }
    r_client.publish(f"job:{job_id}:progress", json.dumps(payload))

@celery_app.task(name="app.worker.tasks.convert_task")
def convert_task(job_id: str):
    db = SessionLocal()
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        db.close()
        return
        
    try:
        # 1. Update status to RUNNING
        job.status = "RUNNING"
        job.progress_stage = "ocr"
        job.progress_percent = 5
        job.started_at = datetime.now(timezone.utc)
        db.commit() # Commit first!
        broadcast_progress(job_id, 5, "ocr", "Initializing Docling Conversion Engine...")
        
        config = db.query(AppConfig).filter(AppConfig.id == 1).first()
        device_setting = config.device if config else "auto"
        use_llm_cleanup = True # assuming global enable or derived from options
        
        # 2. Run Docling
        raw_md, result = run_docling_conversion(job.storage_input_path, device_setting=device_setting)
        
        # [Log Addition] 显式将原生的 raw.md 保存到磁盘供溯源排查
        job_dir = os.path.dirname(job.storage_input_path)
        raw_md_path = os.path.join(job_dir, "raw.md")
        with open(raw_md_path, "w", encoding="utf-8") as f:
            f.write(raw_md)
            
        image_count = len(re.findall(r'data:image/[a-zA-Z0-9]+;base64,', raw_md))
        estimated_vlm = image_count * 2
        
        job.options = {**(job.options or {}), "estimated_vlm_calls": estimated_vlm, "image_count": image_count}
        db.commit()
        broadcast_progress(job_id, 78, "vlm_image", f"Detected {image_count} images, {estimated_vlm} VLM calls")

        # 3. Update progress after OCR
        job.progress_percent = 80
        job.progress_stage = "llm_cleanup"
        db.commit()
        broadcast_progress(job_id, 80, "llm_cleanup", "Docling conversion complete. Cleaning up...")
        
        # 4. Optional LLM post-processing
        final_md = raw_md
        if use_llm_cleanup and config and config.llm_api_key_encrypted:
            decrypted_key = decrypt_key(config.llm_api_key_encrypted)
            
            # Progress callback inside LLM chunk pipeline
            def llm_prog(idx, total):
                percent = 80 + int((idx / total) * 15) # maps chunks to 80%-95% progress
                job.progress_percent = percent
                job.progress_stage = "llm_cleanup"
                db.commit()
                broadcast_progress(job_id, percent, "llm_cleanup", f"Cleaning segment {idx}/{total}...")
                
            # Docling core conversion result provides the DoclingDocument
            from asgiref.sync import async_to_sync
            final_md = async_to_sync(clean_document_llm)(
                raw_md=raw_md,
                api_key=decrypted_key,
                base_url=config.llm_base_url,
                model=config.vlm_model if job.options.get('use_vlm_image_reconstruction', False) else config.llm_model,
                aggressiveness=config.llm_cleanup_aggressiveness,
                max_tokens=config.llm_chunk_max_tokens,
                concurrency=config.llm_chunk_concurrency,
                use_vlm=job.options.get('use_vlm_image_reconstruction', False),
                keep_original_images=False,
                progress_callback=llm_prog
            )
                
        # 5. Save output Markdown to file
        out_path = os.path.join(job_dir, "output.md")
        with open(out_path, "w") as f:
            f.write(final_md)
            
        job.storage_output_path = out_path
        job.status = "SUCCESS"
        job.progress_percent = 100
        job.progress_stage = "done"
        job.finished_at = datetime.now(timezone.utc)
        
        doc_record = db.query(Document).filter(Document.job_id == job.id).first()
        if not doc_record:
            doc_record = Document(job_id=job.id)
            db.add(doc_record)
            
        doc_record.markdown_content = final_md
        try:
            doc_record.page_count = len(result.document.pages)
        except Exception:
            doc_record.page_count = 1
        doc_record.metadata_json = {}
        db.commit()
        
        # Publish complete event
        r_client.publish(f"job:{job_id}:progress", json.dumps({
            "type": "completed",
            "job_id": job_id
        }))
        
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        tb_str = traceback.format_exc()
        logger.error(f"Job {job_id} failed with error: {e}\n{tb_str}")
        
        db.rollback()
        job.status = "FAILED"
        job.error_message = f"{str(e)}\n\nTraceback:\n{tb_str}"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        r_client.publish(f"job:{job_id}:progress", json.dumps({
            "type": "failed",
            "job_id": job_id,
            "error": str(e)
        }))
    finally:
        db.close()

@celery_app.task(name="app.worker.tasks.cleanup_expired_jobs_task")
def cleanup_expired_jobs_task():
    db = SessionLocal()
    try:
        config = db.query(AppConfig).filter(AppConfig.id == 1).first()
        retention_days = config.storage_retention_days if config else 7
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        expired_jobs = db.query(Job).filter(
            Job.status.in_(["SUCCESS", "FAILED", "CANCELLED"]),
            Job.finished_at < cutoff_date
        ).all()
        
        for job in expired_jobs:
            job_dir = os.path.join(settings.STORAGE_ROOT, str(job.id))
            if os.path.exists(job_dir):
                shutil.rmtree(job_dir)
            db.delete(job)
            
        db.commit()
    except Exception as e:
        pass
    finally:
        db.close()
