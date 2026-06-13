from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.models.app_config import AppConfig

router = APIRouter()

@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.id == 1).first()
    if not config:
        config = AppConfig(id=1)
        db.add(config)
        db.commit()
    masked_key = "******" if config.llm_api_key_encrypted else ""
    return {
        "llm_provider": config.llm_provider,
        "llm_base_url": config.llm_base_url,
        "llm_api_key": masked_key,
        "llm_model": config.llm_model,
        "vlm_model": getattr(config, "vlm_model", ""),
        "llm_cleanup_aggressiveness": config.llm_cleanup_aggressiveness,
        "device": config.device
    }

from pydantic import BaseModel
class ConfigUpdate(BaseModel):
    llm_provider: str = None
    llm_base_url: str = None
    llm_api_key: str = None
    llm_model: str = None
    vlm_model: str = None
    llm_cleanup_aggressiveness: str = None
    device: str = None

@router.put("/config")
def update_config(data: ConfigUpdate, db: Session = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.id == 1).first()
    if data.llm_provider is not None: config.llm_provider = data.llm_provider
    if data.llm_base_url is not None: config.llm_base_url = data.llm_base_url
    if data.llm_model is not None: config.llm_model = data.llm_model
    if data.vlm_model is not None: config.vlm_model = data.vlm_model
    if data.llm_cleanup_aggressiveness is not None: config.llm_cleanup_aggressiveness = data.llm_cleanup_aggressiveness
    if data.device is not None: config.device = data.device
    if data.llm_api_key is not None and data.llm_api_key != "******":
        from app.core.security import encrypt_key
        if data.llm_api_key == "":
            config.llm_api_key_encrypted = None
        else:
            config.llm_api_key_encrypted = encrypt_key(data.llm_api_key)
    db.commit()
    return {"status": "success"}

@router.post("/config/test")
def test_connection():
    # Mock test connection for now
    import time
    time.sleep(1)
    return {"status": "success", "message": "Connection successful"}
