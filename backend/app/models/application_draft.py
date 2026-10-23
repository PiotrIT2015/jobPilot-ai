from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class ApplicationDraft(Base):
    __tablename__ = "application_drafts"
    __table_args__ = (UniqueConstraint("job_id", "resume_id", "language", name="uq_application_draft_job_resume_language"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    resume_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(2), nullable=False, default="pl")
    summary_draft: Mapped[str] = mapped_column(Text, nullable=False, default="")
    actions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    cover_letter: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
