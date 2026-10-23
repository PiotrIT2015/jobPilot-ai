import json
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.job import Job
from app.models.job_preference import JobPreference
from app.models.resume import Resume
from app.services.job_matching import score_job
from app.services.job_sources import fetch_jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])
STATUSES = {"saved", "applied", "interview", "rejected", "offer", "archived"}
DEFAULT_ROLES = ["IT Support", "Junior System Administrator", "Junior DevOps"]

class PreferencesIn(BaseModel):
    roles: list[str] = Field(default=DEFAULT_ROLES, max_length=10)
    location: str = Field(default="Kraków, Poland", max_length=255)
    remote_only: bool = False
    keywords: list[str] = Field(default_factory=list, max_length=30)
    preferred_resume_id: int | None = None

class StatusIn(BaseModel):
    status: str

class SyncIn(BaseModel):
    source: Literal["all", "arbeitnow", "remotive"] = "all"
    query: str = Field(default="", max_length=100)
    location: str = Field(default="", max_length=255)
    remote_only: bool = False
    limit: int = Field(default=50, ge=1, le=100)


def get_preferences(db: Session) -> JobPreference:
    prefs = db.get(JobPreference, 1)
    if not prefs:
        prefs = JobPreference(id=1, roles_json=json.dumps(DEFAULT_ROLES), location="Kraków, Poland", remote_only=False, keywords_json="[]")
        db.add(prefs); db.commit(); db.refresh(prefs)
    return prefs

def preferences_dict(p: JobPreference) -> dict:
    return {"roles": json.loads(p.roles_json or "[]"), "location": p.location, "remote_only": p.remote_only, "keywords": json.loads(p.keywords_json or "[]"), "preferred_resume_id": p.preferred_resume_id}

def serialize_job(job: Job) -> dict:
    return {"id":job.id, "source":job.source, "source_job_id":job.source_job_id, "title":job.title, "company":job.company, "location":job.location, "remote":job.remote, "job_type":job.job_type, "description":job.description, "url":job.url, "tags":json.loads(job.tags_json or "[]"), "published_at":job.published_at, "match_score":job.match_score, "match_reasons":json.loads(job.match_reasons_json or "[]"), "application_status":job.application_status, "created_at":job.created_at.isoformat(), "updated_at":job.updated_at.isoformat()}

def recompute_score(row: Job, prefs: JobPreference, db: Session) -> None:
    resume_id = prefs.preferred_resume_id
    if resume_id is None:
        latest = db.scalar(select(Resume).order_by(Resume.created_at.desc()).limit(1))
        resume_id = latest.id if latest else None
    resume = db.get(Resume, resume_id) if resume_id else None
    data = {"title":row.title,"company":row.company,"location":row.location,"remote":row.remote,"description":row.description,"tags":json.loads(row.tags_json or "[]")}
    score, reasons = score_job(data, resume, json.loads(prefs.roles_json or "[]"), json.loads(prefs.keywords_json or "[]"))
    row.match_score = score
    row.match_reasons_json = json.dumps(reasons, ensure_ascii=False)

@router.get("/preferences")
def read_preferences(db: Session = Depends(get_db)):
    return preferences_dict(get_preferences(db))

@router.put("/preferences")
def update_preferences(body: PreferencesIn, db: Session = Depends(get_db)):
    if body.preferred_resume_id is not None and db.get(Resume, body.preferred_resume_id) is None:
        raise HTTPException(404, "Wybrane CV nie istnieje.")
    p = get_preferences(db)
    p.roles_json = json.dumps([x.strip() for x in body.roles if x.strip()], ensure_ascii=False)
    p.location = body.location.strip()
    p.remote_only = body.remote_only
    p.keywords_json = json.dumps([x.strip() for x in body.keywords if x.strip()], ensure_ascii=False)
    p.preferred_resume_id = body.preferred_resume_id
    db.commit(); db.refresh(p)
    for row in db.scalars(select(Job)).all():
        recompute_score(row, p, db)
    db.commit()
    return preferences_dict(p)

@router.post("/sync")
async def sync_jobs(body: SyncIn, db: Session = Depends(get_db)):
    prefs = get_preferences(db)
    location = body.location.strip() or prefs.location
    remote_only = body.remote_only or prefs.remote_only
    query = body.query.strip()
    try:
        incoming = await fetch_jobs(body.source, query, location, remote_only, body.limit)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, "Nie udało się pobrać ofert ze źródła. Sprawdź połączenie z internetem i spróbuj później.") from exc
    inserted = updated = 0
    for item in incoming:
        if not item.get("url") or not item.get("title"):
            continue
        row = db.scalar(select(Job).where(Job.source == item["source"], Job.source_job_id == item["source_job_id"]))
        if row is None:
            row = Job(source=item["source"], source_job_id=item["source_job_id"], title=item["title"], company=item["company"], location=item["location"], remote=item["remote"], job_type=item["job_type"], description=item["description"], url=item["url"], tags_json=json.dumps(item["tags"], ensure_ascii=False), published_at=item["published_at"])
            db.add(row); inserted += 1
        else:
            row.title=item["title"]; row.company=item["company"]; row.location=item["location"]; row.remote=item["remote"]; row.job_type=item["job_type"]; row.description=item["description"]; row.url=item["url"]; row.tags_json=json.dumps(item["tags"], ensure_ascii=False); row.published_at=item["published_at"]; updated += 1
        db.flush()
        recompute_score(row, prefs, db)
    db.commit()
    return {"source":body.source, "received":len(incoming), "inserted":inserted, "updated":updated, "total_saved":db.scalar(select(Job).count()) if False else db.query(Job).count(), "message":"Synchronizacja zakończona. Wyniki zapisano w MySQL."}

@router.get("")
def list_jobs(q: str = Query(default="", max_length=200), status: str | None = None, source: str | None = None, remote_only: bool = False, min_score: float = Query(default=0, ge=0, le=100), limit: int = Query(default=100, ge=1, le=300), db: Session = Depends(get_db)):
    stmt = select(Job)
    if status:
        if status not in STATUSES: raise HTTPException(400, "Nieprawidłowy status aplikacji.")
        stmt = stmt.where(Job.application_status == status)
    if source: stmt = stmt.where(Job.source == source)
    if remote_only: stmt = stmt.where(Job.remote.is_(True))
    if q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where((Job.title.ilike(term)) | (Job.company.ilike(term)) | (Job.location.ilike(term)) | (Job.description.ilike(term)))
    stmt = stmt.where(Job.match_score >= min_score).order_by(Job.match_score.desc(), Job.created_at.desc()).limit(limit)
    return [serialize_job(row) for row in db.scalars(stmt).all()]

@router.patch("/{job_id}/status")
def update_job_status(job_id: int, body: StatusIn, db: Session = Depends(get_db)):
    if body.status not in STATUSES:
        raise HTTPException(400, "Dozwolone statusy: " + ", ".join(sorted(STATUSES)))
    row = db.get(Job, job_id)
    if row is None: raise HTTPException(404, "Nie znaleziono oferty.")
    row.application_status = body.status
    db.commit(); db.refresh(row)
    return serialize_job(row)

@router.get("/sources")
def sources():
    return {"sources":[{"id":"arbeitnow","name":"Arbeitnow Job Board API","url":"https://www.arbeitnow.com/","coverage":"Oferty międzynarodowe; lokalizacja zależna od oferty"},{"id":"remotive","name":"Remotive Remote Jobs API","url":"https://remotive.com/","coverage":"Oferty zdalne; ograniczenia lokalizacyjne mogą występować"}], "note":"JobPilot zapisuje źródło i oryginalny link. Dostępność ofert i warunki korzystania zależą od dostawcy."}
