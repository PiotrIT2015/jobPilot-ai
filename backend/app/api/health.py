from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.db import check_database_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "jobpilot-api"}


@router.get("/health/db")
def database_health_check() -> dict[str, str]:
    try:
        check_database_connection()
        return {"status": "ok", "database": "mysql", "connection": "available"}
    except SQLAlchemyError as exc:
        # Nie zwracamy szczegółów połączenia ani sekretów w odpowiedzi HTTP.
        raise HTTPException(
            status_code=503,
            detail="Nie udało się połączyć z bazą danych. Sprawdź DATABASE_URL i dostępność MySQL.",
        ) from exc
