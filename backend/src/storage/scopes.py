"""Persistence and validation for scopes.

Public API:
    validate_included_schemas(included_schemas, available_schemas) -> None
    create_scope(db, ...) -> Scope
    list_scopes(db, data_source_id=None) -> list[Scope]
    load_scope(db, scope_id) -> Scope | None
    delete_scope(db, scope_id) -> None

No update_scope for v0 — editing included_schemas on a scope with
existing snapshots creates orphaned rows. Delete-and-recreate is the
v0 story. See ADR 0009.

Every function that takes a Session lets the caller own commit/rollback.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.sources import DataSource, Scope
from src.storage.data_sources import load_data_source


class ScopeStorageError(Exception):
    """Raised when a scope operation can't be completed."""


# ----------------------------------------------------------------------
# Validation (pure function, no db)
# ----------------------------------------------------------------------

def validate_included_schemas(
    included_schemas: list[str],
    available_schemas: list[str],
) -> None:
    """Validate that included_schemas is non-empty and a subset of available_schemas.

    Raises ScopeStorageError listing all invalid entries (not just the first)
    so the caller can fix everything in one pass. Case-sensitive — Postgres
    schema names are case-sensitive by default.
    """
    if not included_schemas:
        raise ScopeStorageError(
            "included_schemas must not be empty — an empty scope is meaningless."
        )

    available_set = set(available_schemas)
    invalid = [s for s in included_schemas if s not in available_set]
    if invalid:
        raise ScopeStorageError(
            f"Scope references schemas not present in data source: {invalid}. "
            f"Available: {sorted(available_set)}."
        )


# ----------------------------------------------------------------------
# Create
# ----------------------------------------------------------------------

def create_scope(
    db: Session,
    data_source_id: str,
    name: str,
    included_schemas: list[str],
    available_schemas: list[str],
    excluded_tables: list[str] | None = None,
    description: str | None = None,
    created_by: str = "local_user",
) -> Scope:
    """Create a new scope against a data source.

    available_schemas is the list of schemas the data source actually
    exposes — the caller's responsibility to fetch via the connector.
    We validate included_schemas against it before writing.
    """
    validate_included_schemas(included_schemas, available_schemas)

    ds = load_data_source(db, data_source_id)
    if ds is None:
        raise ScopeStorageError(f"Data source {data_source_id} not found")

    scope = Scope(
        data_source_id=data_source_id,
        name=name,
        included_schemas=included_schemas,
        excluded_tables=excluded_tables,
        description=description,
        created_by=created_by,
    )
    db.add(scope)
    db.flush()
    return scope


# ----------------------------------------------------------------------
# Read
# ----------------------------------------------------------------------

def list_scopes(
    db: Session,
    data_source_id: str | None = None,
) -> list[Scope]:
    """Return all scopes, optionally filtered by data_source_id.

    Ordered by created_at descending (newest first).
    """
    stmt = select(Scope).order_by(Scope.created_at.desc())
    if data_source_id is not None:
        stmt = stmt.where(Scope.data_source_id == data_source_id)
    return list(db.execute(stmt).scalars())


def load_scope(db: Session, scope_id: str) -> Scope | None:
    """Return one scope by id, or None if not found."""
    return db.get(Scope, scope_id)


# ----------------------------------------------------------------------
# Delete
# ----------------------------------------------------------------------

def delete_scope(db: Session, scope_id: str) -> None:
    """Delete a scope. Raises ScopeStorageError if not found or if
    snapshots/definitions still reference it (ON DELETE RESTRICT).

    Pre-checks dependent row counts so the error message is actionable.
    """
    scope = db.get(Scope, scope_id)
    if scope is None:
        raise ScopeStorageError(f"Scope {scope_id} not found")

    # Check for dependent rows that would block deletion via RESTRICT FKs.
    from src.models.snapshots import SchemaSnapshot
    from src.models.entities import EntityDefinition

    snap_count = db.execute(
        select(func.count()).select_from(SchemaSnapshot).where(SchemaSnapshot.scope_id == scope_id)
    ).scalar_one()

    entity_count = db.execute(
        select(func.count()).select_from(EntityDefinition).where(EntityDefinition.scope_id == scope_id)
    ).scalar_one()

    if snap_count > 0 or entity_count > 0:
        raise ScopeStorageError(
            f"Cannot delete scope {scope_id} — "
            f"{snap_count} snapshot(s) and {entity_count} entity definition(s) "
            f"still reference it. Delete the dependent rows first."
        )

    db.delete(scope)
    db.flush()
