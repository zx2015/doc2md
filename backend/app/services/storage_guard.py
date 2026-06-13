import shutil
from fastapi import HTTPException
from app.core.config import settings
from app.models.app_config import AppConfig
from sqlalchemy.orm import Session

def check_disk_space(db: Session) -> None:
    """Check if STORAGE_ROOT has enough free space. If below threshold, raise 503."""
    import os
    os.makedirs(settings.STORAGE_ROOT, exist_ok=True)
    config = db.query(AppConfig).filter(AppConfig.id == 1).first()
    # Assume 2GB if config missing or fields don't exist yet (before alembic migration)
    min_gb = getattr(config, 'disk_free_min_gb', 2) if config else 2
    total, used, free = shutil.disk_usage(settings.STORAGE_ROOT)
    free_gb = free // (1024 ** 3)
    if free_gb < min_gb:
        raise HTTPException(
            status_code=503,
            detail="Disk space insufficient, please retry later"
        )
