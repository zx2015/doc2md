from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, func
from app.models.base import Base

class AppConfig(Base):
    __tablename__ = "app_config"
    id = Column(Integer, primary_key=True, default=1)
    llm_provider = Column(String, default="openai")
    llm_base_url = Column(String, nullable=True)
    llm_api_key_encrypted = Column(String, nullable=True)
    llm_model = Column(String, default="gpt-4o")
    vlm_model = Column(String, nullable=True, comment="For image reconstruction")
    llm_context_window = Column(Integer, default=8192)
    llm_chunk_max_tokens = Column(Integer, default=4000)
    llm_chunk_concurrency = Column(Integer, default=3)
    llm_chunk_overlap_tokens = Column(Integer, default=200)
    llm_cleanup_aggressiveness = Column(String, default="balanced") # conservative, balanced, aggressive
    use_vlm_image_reconstruction = Column(Boolean, default=False)
    keep_original_images = Column(Boolean, default=True)
    # v1.1 Patch 12.5: 字段保留以兼容历史，但前端永远不展示、worker 永远不读取
    enable_toc_removal = Column(Boolean, default=True, comment="⚠️ deprecated since v1.0.3")
    enable_reference_removal = Column(Boolean, default=True, comment="⚠️ deprecated since v1.0.3")
    enable_header_footer_removal = Column(Boolean, default=True)
    enable_whitespace_cleanup = Column(Boolean, default=True)
    device = Column(String, default="auto")  # cuda, cpu, auto
    ocr_timeout_seconds = Column(Integer, default=600)
    docling_options = Column(JSON, default=dict)
    storage_retention_days = Column(Integer, default=7)
    disk_free_min_gb = Column(Integer, default=2)
    updated_at = Column(DateTime, default=None, onupdate=func.now())
