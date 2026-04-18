"""Database connection and session management."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import get_settings

settings = get_settings()

# The engine is a connection pool, created once per process.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Checks connection health before using; handles dropped connections gracefully.
    echo=False,  # Set True for SQL query logging during debugging.
)

# Session factory. Each request gets its own session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session per request.

    Ensures the session is always closed, even if the request raises.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
