from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "doc2md_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.worker.tasks", "app.worker.beat_schedule"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True, # Late ack to prevent progress loss on worker crash
    worker_concurrency=1  # CRITICAL: Strict concurrency=1 to prevent GPU OOM
)

celery_app.conf.beat_schedule = {
    'cleanup-expired-jobs': {
        'task': 'app.worker.beat_schedule.cleanup_expired_jobs',
        'schedule': crontab(hour=3, minute=0),
    },
}
