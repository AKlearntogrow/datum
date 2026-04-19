"""Datum backend — FastAPI application entry point."""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.entities import router as entities_router
from src.api.errors import register_exception_handlers
from src.api.ingest import router as ingest_router
from src.core.config import get_settings
from src.core.db import get_db

settings = get_settings()

app = FastAPI(
    title="Datum",
    description="AI-assisted semantic layer for messy data warehouses.",
    version="0.1.0",
)

# CORS — allow the Next.js dev server to call this API from the browser.
# In production we'll tighten origins and add rate limiting.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,  # We don't use cookies; setting True with wildcard methods trips some browsers.
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
    expose_headers=["*"],
    max_age=3600,
)

# Translate internal exceptions into HTTP status codes.
register_exception_handlers(app)

# Route registration — one router per resource.
app.include_router(ingest_router)
app.include_router(entities_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Confirms the app is running."""
    return {"status": "ok", "environment": settings.environment}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """Readiness check. Confirms the app can talk to the database
    and that the pgvector extension is installed."""
    db.execute(text("SELECT 1"))
    result = db.execute(
        text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    ).scalar()
    return {
        "status": "ok",
        "database": "connected",
        "pgvector_version": result or "not_installed",
    }
