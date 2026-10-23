from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    source_job_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False, default="Unknown")
    location: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    remote: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    published_at: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    match_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    match_reasons_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    application_status: Mapped[str] = mapped_column(String(30), nullable=False, default="saved")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
