import json
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models.resume import Resume
from app.services.cv_parser import build_candidate_profile, extract_text

router = APIRouter(prefix="/resumes", tags=["resumes"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"


def safe_filename(filename: str) -> str:
    # Do not use a user-supplied path as a filesystem path.
    name = Path(filename or "resume").name
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name[:200] or "resume"


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    original_name = safe_filename(file.filename or "resume")
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Dozwolone formaty: PDF i DOCX.")

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    if not data:
        raise HTTPException(400, "Przesłany plik jest pusty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Maksymalny rozmiar pliku to 5 MB.")

    # Basic format signature validation; MIME headers supplied by clients are not trusted.
    if extension == ".pdf" and not data.startswith(b"%PDF-"):
        raise HTTPException(400, "Plik nie wygląda na prawidłowy PDF.")
    if extension == ".docx" and not data.startswith(b"PK"):
        raise HTTPException(400, "Plik nie wygląda na prawidłowy DOCX.")

    try:
        extracted = extract_text(data, extension)
    except Exception as exc:
        raise HTTPException(422, f"Nie udało się odczytać CV: {str(exc)[:250]}") from exc

    profile = build_candidate_profile(extracted)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / stored_name).write_bytes(data)

    resume = Resume(
        original_filename=original_name,
        stored_filename=stored_name,
        file_type=extension.lstrip("."),
        file_size=len(data),
        extracted_text=extracted,
        profile_json=json.dumps(profile, ensure_ascii=False),
    )
    try:
        db.add(resume)
        db.commit()
        db.refresh(resume)
    except Exception:
        db.rollback()
        (UPLOAD_DIR / stored_name).unlink(missing_ok=True)
        raise HTTPException(500, "Nie udało się zapisać metadanych CV w bazie danych.")

    return {
        "id": resume.id,
        "filename": resume.original_filename,
        "file_type": resume.file_type,
        "file_size": resume.file_size,
        "created_at": resume.created_at.isoformat(),
        "profile": profile,
    }


@router.get("")
def list_resumes(db: Session = Depends(get_db)):
    records = db.query(Resume).order_by(Resume.created_at.desc()).all()
    return [
        {
            "id": row.id,
            "filename": row.original_filename,
            "file_type": row.file_type,
            "file_size": row.file_size,
            "created_at": row.created_at.isoformat(),
            "profile": json.loads(row.profile_json or "{}"),
        }
        for row in records
    ]


@router.get("/{resume_id}")
def get_resume(resume_id: int, db: Session = Depends(get_db)):
    row = db.get(Resume, resume_id)
    if row is None:
        raise HTTPException(404, "Nie znaleziono CV.")
    return {
        "id": row.id,
        "filename": row.original_filename,
        "file_type": row.file_type,
        "file_size": row.file_size,
        "created_at": row.created_at.isoformat(),
        "extracted_text": row.extracted_text,
        "profile": json.loads(row.profile_json or "{}"),
    }
