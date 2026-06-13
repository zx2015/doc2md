from app.core.database import SessionLocal
from app.models.app_config import AppConfig

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_app_config(db):
    config = db.query(AppConfig).filter(AppConfig.id == 1).first()
    if not config:
        config = AppConfig(id=1)
        db.add(config)
        db.commit()
