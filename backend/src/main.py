"""Datum backend — FastAPI application entry point."""

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.db import get_db

settings = get_settings()

app = FastAPI(
    title="Datum",
    description="AI-assisted semantic layer for messy data warehouses.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Confirms the app is running.

    Does NOT check database connectivity — that's /health/db.
    """
    return {"status": "ok", "environment": settings.environment}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """Readiness check. Confirms the app can talk to the database
    and that the pgvector extension is installed.
    """
    # Basic connectivity
    db.execute(text("SELECT 1"))

    # Confirm pgvector is available — we'll need it soon
    result = db.execute(
        text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    ).scalar()

    return {
        "status": "ok",
        "database": "connected",
        "pgvector_version": result or "not_installed",
    }
