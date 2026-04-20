"""Persistence for data source connections.

Public API:
    create_data_source(db, ...) -> DataSource
    list_data_sources(db) -> list[DataSource]
    load_data_source(db, data_source_id) -> DataSource | None
    delete_data_source(db, data_source_id) -> None

Every function takes a Session; the caller owns commit/rollback.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.sources import DataSource, Scope


class DataSourceStorageError(Exception):
    """Raised when a data source operation can't be completed."""


def create_data_source(
    db: Session,
    name: str,
    warehouse_type: str,
    connection_url: str,
    description: str | None = None,
    created_by: str = "local_user",
) -> DataSource:
    """Create a new data source and return it with a populated id.

    No validation on warehouse_type for v0 — it's free-form text per
    ADR 0009. A future slice can add an allowlist when we support
    multiple warehouse types.
    """
    ds = DataSource(
        name=name,
        warehouse_type=warehouse_type,
        connection_url=connection_url,
        description=description,
        created_by=created_by,
    )
    db.add(ds)
    db.flush()
    return ds


def list_data_sources(db: Session) -> list[DataSource]:
    """Return all data sources ordered by created_at descending (newest first)."""
    stmt = select(DataSource).order_by(DataSource.created_at.desc())
    return list(db.execute(stmt).scalars())


def load_data_source(db: Session, data_source_id: str) -> DataSource | None:
    """Return one data source by id, or None if not found."""
    return db.get(DataSource, data_source_id)


def delete_data_source(db: Session, data_source_id: str) -> None:
    """Delete a data source. Raises DataSourceStorageError if not found or
    if scopes still reference it (ON DELETE RESTRICT).

    We pre-check the scope count so the error message tells the caller
    exactly how many scopes are blocking the delete, rather than surfacing
    a raw IntegrityError.
    """
    ds = db.get(DataSource, data_source_id)
    if ds is None:
        raise DataSourceStorageError(f"Data source {data_source_id} not found")

    scope_count = db.execute(
        select(func.count()).select_from(Scope).where(Scope.data_source_id == data_source_id)
    ).scalar_one()

    if scope_count > 0:
        raise DataSourceStorageError(
            f"Cannot delete data source {data_source_id} — "
            f"{scope_count} scope(s) still reference it. Delete the scopes first."
        )

    db.delete(ds)
    db.flush()
