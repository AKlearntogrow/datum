"""Fixtures for storage layer tests.

Provides a DB session that wraps each test in a transaction and rolls it
back at the end so tests don't leave state in the app database.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from src.core.db import SessionLocal


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Yield a DB session wrapped in a transaction that rolls back after the test.

    This lets storage tests exercise real SQL against the app database without
    persisting anything. Each test gets a clean slate.
    """
    session = SessionLocal()
    session.begin_nested()  # SAVEPOINT so we can rollback without closing the connection
    try:
        yield session
    finally:
        session.rollback()
        session.close()
