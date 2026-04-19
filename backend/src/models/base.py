"""Shared SQLAlchemy DeclarativeBase for all Datum models.

Every model subclasses Base; every table registers automatically with
Base.metadata, which is what Alembic autogenerate uses to detect schema
changes.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """All Datum ORM models inherit from this."""
    pass
