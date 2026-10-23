from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class JobPreference(Base):
    __tablename__ = "job_preferences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    roles_json: Mapped[str] = mapped_column(Text, nullable=False, default='["IT Support", "Junior System Administrator", "Junior DevOps"]')
    location: Mapped[str] = mapped_column(String(255), nullable=False, default="Kraków, Poland")
    remote_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    keywords_json: Mapped[str] = mapped_column(Text, nullable=False, default='[]')
    preferred_resume_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
