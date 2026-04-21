"""Pydantic request/response schemas for scope endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.sources import Scope


# ----------------------------------------------------------------------
# Request bodies
# ----------------------------------------------------------------------

class ScopeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_source_id: str
    name: str
    included_schemas: list[str]
    excluded_tables: list[str] | None = Field(
        default=None, description='Qualified table names in the form "schema.table"'
    )
    description: str | None = None


class ScopeUpdateRequest(BaseModel):
    """PATCH body. Only name and description are editable per ADR 0009."""
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None


# ----------------------------------------------------------------------
# Response bodies
# ----------------------------------------------------------------------

class ScopeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    data_source_id: str
    name: str
    included_schemas: list[str]
    excluded_tables: list[str] | None = None
    description: str | None = None
    created_by: str
    created_at: datetime


class ScopeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScopeResponse]
    total: int


# ----------------------------------------------------------------------
# ORM -> API conversion
# ----------------------------------------------------------------------

def scope_to_response(scope: Scope) -> ScopeResponse:
    return ScopeResponse(
        id=scope.id,
        data_source_id=scope.data_source_id,
        name=scope.name,
        included_schemas=scope.included_schemas,
        excluded_tables=scope.excluded_tables,
        description=scope.description,
        created_by=scope.created_by,
        created_at=scope.created_at,
    )
