from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.resumes import router as resumes_router
from app.api.jobs import router as jobs_router
from app.api.analysis import router as analysis_router
from app.core.config import settings
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Creates the initial table(s) for the MVP. Use Alembic migrations before production.
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.4.0",
    description="JobPilot AI — etap 4: analiza wymagań, luki kompetencyjne i szkice materiałów aplikacyjnych.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(resumes_router, prefix=settings.api_prefix)
app.include_router(jobs_router, prefix=settings.api_prefix)
app.include_router(analysis_router, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "JobPilot AI API działa", "docs": "/docs"}
