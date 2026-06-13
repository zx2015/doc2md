import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, BigInteger, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class Job(Base):
    __tablename__ = "jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String, nullable=False, default="PENDING")  # PENDING, RUNNING, SUCCESS, FAILED, CANCELLED
    input_filename = Column(String, nullable=False)
    input_format = Column(String, nullable=False)
    input_size_bytes = Column(BigInteger, nullable=False)
    storage_input_path = Column(String, nullable=False)
    storage_output_path = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    progress_percent = Column(Integer, nullable=False, default=0)
    progress_stage = Column(String, nullable=False, default="uploading")  # uploading, ocr, llm_cleanup, vlm_image, done
    options = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
