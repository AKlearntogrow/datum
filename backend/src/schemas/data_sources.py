"""Pydantic request/response schemas for data source endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.models.sources import DataSource


# ----------------------------------------------------------------------
# Request bodies
# ----------------------------------------------------------------------

class DataSourceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    warehouse_type: str
    connection_url: str
    description: str | None = None


# ----------------------------------------------------------------------
# Response bodies
# ----------------------------------------------------------------------

class SchemaInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: str
    tables: list[str]


class SchemaListResponse(BaseModel):
    """Response for the /schemas introspection endpoint."""
    model_config = ConfigDict(extra="forbid")

    schemas: list[SchemaInfo]


class DataSourceResponse(BaseModel):
    """What the API returns for a single data source.

    connection_url is returned unredacted per ADR 0009 — v0 is local-only
    and the UI shows a plain-text warning.
    """
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    warehouse_type: str
    connection_url: str
    description: str | None = None
    created_by: str
    created_at: datetime


class DataSourceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DataSourceResponse]
    total: int


# ----------------------------------------------------------------------
# ORM -> API conversion
# ----------------------------------------------------------------------

def data_source_to_response(ds: DataSource) -> DataSourceResponse:
    return DataSourceResponse(
        id=ds.id,
        name=ds.name,
        warehouse_type=ds.warehouse_type,
        connection_url=ds.connection_url,
        description=ds.description,
        created_by=ds.created_by,
        created_at=ds.created_at,
    )
