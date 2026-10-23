from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.job import Job
from app.models.job_preference import JobPreference
from app.models.resume import Resume
from app.models.application_draft import ApplicationDraft
from app.services.application_assistant import analyze_job, generate_materials
import json

router = APIRouter(prefix="/analysis", tags=["job analysis and application materials"])

class MaterialsRequest(BaseModel):
    resume_id: int | None = None
    language: Literal["pl", "en"] = "pl"
    applicant_name: str = Field(default="", max_length=120)


class SaveDraftRequest(BaseModel):
    resume_id: int
    language: Literal["pl", "en"] = "pl"
    summary_draft: str = Field(default="", max_length=10000)
    actions: list[str] = Field(default_factory=list, max_length=30)
    cover_letter: str = Field(default="", max_length=30000)


def get_job_or_404(job_id: int, db: Session) -> Job:
    row = db.get(Job, job_id)
    if row is None:
        raise HTTPException(404, "Nie znaleziono oferty pracy.")
    return row


def get_resume_or_404(resume_id: int | None, db: Session) -> Resume:
    if resume_id is None:
        prefs = db.get(JobPreference, 1)
        resume_id = prefs.preferred_resume_id if prefs and prefs.preferred_resume_id else None
    if resume_id is None:
        latest = db.scalar(select(Resume).order_by(Resume.created_at.desc()).limit(1))
        resume_id = latest.id if latest else None
    resume = db.get(Resume, resume_id) if resume_id else None
    if resume is None:
        raise HTTPException(400, "Najpierw dodaj CV w sekcji „Moje CV” lub wybierz istniejące CV.")
    return resume


@router.get("/jobs/{job_id}")
def job_analysis(job_id: int, resume_id: int | None = None, db: Session = Depends(get_db)):
    job = get_job_or_404(job_id, db)
    resume = get_resume_or_404(resume_id, db)
    return analyze_job(job, resume)


@router.post("/jobs/{job_id}/materials")
async def application_materials(job_id: int, body: MaterialsRequest, db: Session = Depends(get_db)):
    job = get_job_or_404(job_id, db)
    resume = get_resume_or_404(body.resume_id, db)
    result = await generate_materials(job, resume, body.language, body.applicant_name)
    result["job_id"] = job.id
    result["resume_id"] = resume.id
    result["job_title"] = job.title
    result["company"] = job.company
    result["disclaimer"] = "To roboczy szkic oparty na odczytanym CV i treści ogłoszenia. Sprawdź każdą informację i edytuj tekst przed wysłaniem."
    return result


@router.put("/jobs/{job_id}/materials/save")
def save_application_draft(job_id: int, body: SaveDraftRequest, db: Session = Depends(get_db)):
    get_job_or_404(job_id, db)
    if db.get(Resume, body.resume_id) is None:
        raise HTTPException(404, "Nie znaleziono CV przypisanego do szkicu.")
    row = db.scalar(select(ApplicationDraft).where(
        ApplicationDraft.job_id == job_id,
        ApplicationDraft.resume_id == body.resume_id,
        ApplicationDraft.language == body.language,
    ))
    if row is None:
        row = ApplicationDraft(job_id=job_id, resume_id=body.resume_id, language=body.language)
        db.add(row)
    row.summary_draft = body.summary_draft
    row.actions_json = json.dumps(body.actions, ensure_ascii=False)
    row.cover_letter = body.cover_letter
    db.commit()
    db.refresh(row)
    return {"id": row.id, "job_id": row.job_id, "resume_id": row.resume_id, "language": row.language, "summary_draft": row.summary_draft, "actions": json.loads(row.actions_json or "[]"), "cover_letter": row.cover_letter, "updated_at": row.updated_at.isoformat(), "message": "Zapisano szkic materiałów aplikacyjnych w bazie danych."}


@router.get("/jobs/{job_id}/materials/saved")
def get_saved_application_draft(job_id: int, resume_id: int | None = None, language: Literal["pl", "en"] = "pl", db: Session = Depends(get_db)):
    get_job_or_404(job_id, db)
    resume = get_resume_or_404(resume_id, db)
    row = db.scalar(select(ApplicationDraft).where(
        ApplicationDraft.job_id == job_id,
        ApplicationDraft.resume_id == resume.id,
        ApplicationDraft.language == language,
    ))
    if row is None:
        raise HTTPException(404, "Nie znaleziono zapisanego szkicu dla tej oferty, CV i języka.")
    return {"id": row.id, "job_id": row.job_id, "resume_id": row.resume_id, "language": row.language, "summary_draft": row.summary_draft, "actions": json.loads(row.actions_json or "[]"), "cover_letter": row.cover_letter, "updated_at": row.updated_at.isoformat()}
