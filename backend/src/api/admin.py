"""Admin API routes for data sources and scopes.

All routes live under /api/admin. No authentication in v0 (ADR 0007).
Routes are thin: call storage or connector, commit, convert, return.
Errors propagate to handlers registered in api/errors.py.
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.connectors import PostgresConnector
from src.core.db import get_db
from src.schemas.data_sources import (
    DataSourceCreateRequest,
    DataSourceListResponse,
    DataSourceResponse,
    SchemaInfo,
    SchemaListResponse,
    data_source_to_response,
)
from src.schemas.scopes import (
    ScopeCreateRequest,
    ScopeListResponse,
    ScopeResponse,
    ScopeUpdateRequest,
    scope_to_response,
)
from src.storage.data_sources import (
    DataSourceStorageError,
    create_data_source,
    delete_data_source,
    list_data_sources,
    load_data_source,
)
from src.storage.scopes import (
    ScopeStorageError,
    create_scope,
    delete_scope,
    list_scopes,
    load_scope,
    update_scope,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def _introspect_schemas(data_source_id: str, db: Session) -> list[SchemaInfo]:
    """Connect to the warehouse behind a data source and return its schemas + tables.

    Uses list_tables() from the connector protocol, grouped by schema.
    Connector exceptions propagate to the 502 handlers in errors.py.
    """
    ds = load_data_source(db, data_source_id)
    if ds is None:
        raise DataSourceStorageError(f"Data source {data_source_id} not found")

    connector = _make_connector(ds.warehouse_type, ds.connection_url)
    tables = connector.list_tables()

    by_schema: dict[str, list[str]] = defaultdict(list)
    for t in tables:
        by_schema[t.schema].append(t.name)

    return [
        SchemaInfo(schema_name=schema, tables=sorted(tbl_names))
        for schema, tbl_names in sorted(by_schema.items())
    ]


def _list_available_schema_names(data_source_id: str, db: Session) -> list[str]:
    """Return just the schema names visible to a data source's credentials."""
    schema_infos = _introspect_schemas(data_source_id, db)
    return [s.schema_name for s in schema_infos]


def _make_connector(warehouse_type: str, connection_url: str) -> PostgresConnector:
    """Factory for connectors. v0 supports only Postgres; future types dispatch here."""
    if warehouse_type == "postgres":
        return PostgresConnector(connection_url)
    raise DataSourceStorageError(
        f"Unsupported warehouse type: '{warehouse_type}'. v0 supports 'postgres' only."
    )


# ----------------------------------------------------------------------
# Data source endpoints
# ----------------------------------------------------------------------

@router.post("/data-sources", response_model=DataSourceResponse)
def admin_create_data_source(
    body: DataSourceCreateRequest,
    db: Session = Depends(get_db),
) -> DataSourceResponse:
    ds = create_data_source(
        db,
        name=body.name,
        warehouse_type=body.warehouse_type,
        connection_url=body.connection_url,
        description=body.description,
    )
    db.commit()
    db.refresh(ds)
    return data_source_to_response(ds)


@router.get("/data-sources", response_model=DataSourceListResponse)
def admin_list_data_sources(db: Session = Depends(get_db)) -> DataSourceListResponse:
    sources = list_data_sources(db)
    items = [data_source_to_response(ds) for ds in sources]
    return DataSourceListResponse(items=items, total=len(items))


@router.get("/data-sources/{data_source_id}", response_model=DataSourceResponse)
def admin_get_data_source(
    data_source_id: str,
    db: Session = Depends(get_db),
) -> DataSourceResponse:
    ds = load_data_source(db, data_source_id)
    if ds is None:
        raise DataSourceStorageError(f"Data source {data_source_id} not found")
    return data_source_to_response(ds)


@router.delete("/data-sources/{data_source_id}", status_code=204, response_class=Response)
def admin_delete_data_source(
    data_source_id: str,
    db: Session = Depends(get_db),
) -> Response:
    delete_data_source(db, data_source_id)
    db.commit()
    return Response(status_code=204)


# ----------------------------------------------------------------------
# Schema introspection
# ----------------------------------------------------------------------

@router.post(
    "/data-sources/{data_source_id}/schemas",
    response_model=SchemaListResponse,
)
def admin_list_schemas(
    data_source_id: str,
    db: Session = Depends(get_db),
) -> SchemaListResponse:
    """List schemas and tables visible to a data source's credentials.

    POST (not GET) because it hits the external warehouse — signals to
    logging and rate-limiting that this action has side-channel cost.
    """
    schema_infos = _introspect_schemas(data_source_id, db)
    return SchemaListResponse(schemas=schema_infos)


# ----------------------------------------------------------------------
# Scope endpoints
# ----------------------------------------------------------------------

@router.post("/scopes", response_model=ScopeResponse)
def admin_create_scope(
    body: ScopeCreateRequest,
    db: Session = Depends(get_db),
) -> ScopeResponse:
    """Create a scope. Validates included_schemas against the warehouse's
    actual schemas by connecting to the data source."""
    available = _list_available_schema_names(body.data_source_id, db)
    scope = create_scope(
        db,
        data_source_id=body.data_source_id,
        name=body.name,
        included_schemas=body.included_schemas,
        available_schemas=available,
        excluded_tables=body.excluded_tables,
        description=body.description,
    )
    db.commit()
    db.refresh(scope)
    return scope_to_response(scope)


@router.get("/scopes", response_model=ScopeListResponse)
def admin_list_scopes(
    data_source_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ScopeListResponse:
    scopes = list_scopes(db, data_source_id=data_source_id)
    items = [scope_to_response(s) for s in scopes]
    return ScopeListResponse(items=items, total=len(items))


@router.get("/scopes/{scope_id}", response_model=ScopeResponse)
def admin_get_scope(
    scope_id: str,
    db: Session = Depends(get_db),
) -> ScopeResponse:
    scope = load_scope(db, scope_id)
    if scope is None:
        raise ScopeStorageError(f"Scope {scope_id} not found")
    return scope_to_response(scope)


@router.patch("/scopes/{scope_id}", response_model=ScopeResponse)
def admin_update_scope(
    scope_id: str,
    body: ScopeUpdateRequest,
    db: Session = Depends(get_db),
) -> ScopeResponse:
    fields = body.model_dump(exclude_unset=True)
    scope = update_scope(db, scope_id, fields)
    db.commit()
    db.refresh(scope)
    return scope_to_response(scope)


@router.delete("/scopes/{scope_id}", status_code=204, response_class=Response)
def admin_delete_scope(
    scope_id: str,
    db: Session = Depends(get_db),
) -> Response:
    delete_scope(db, scope_id)
    db.commit()
    return Response(status_code=204)
