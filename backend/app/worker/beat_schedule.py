from datetime import datetime, timedelta
from celery import shared_task
from app.core.database import SessionLocal
from app.models.job import Job
from app.models.app_config import AppConfig
import os, shutil
from app.core.config import settings

@shared_task(name="app.worker.beat_schedule.cleanup_expired_jobs")
def cleanup_expired_jobs():
    db = SessionLocal()
    try:
        config = db.query(AppConfig).filter(AppConfig.id == 1).first()
        retention_days = getattr(config, 'storage_retention_days', 7) if config else 7
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        expired = db.query(Job).filter(
            Job.status.in_(["SUCCESS", "FAILED"]),
            Job.finished_at < cutoff
        ).all()
        for job in expired:
            job_dir = os.path.join(settings.STORAGE_ROOT, str(job.id))
            if os.path.exists(job_dir):
                shutil.rmtree(job_dir)
            db.delete(job)
        db.commit()
    finally:
        db.close()
