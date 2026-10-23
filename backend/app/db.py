from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def init_db() -> None:
    # Import ensures models are registered with SQLAlchemy metadata.
    from app.models.resume import Resume  # noqa: F401
    from app.models.job import Job  # noqa: F401
    from app.models.job_preference import JobPreference  # noqa: F401
    from app.models.application_draft import ApplicationDraft  # noqa: F401
    Base.metadata.create_all(bind=engine)
