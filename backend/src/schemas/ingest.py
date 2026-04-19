"""Request and response schemas for the /api/ingest endpoint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class IngestRequest(BaseModel):
    """POST body to kick off an ingestion run.

    v0 supports only Postgres and takes a connection URL. Future revisions
    will accept an inline connector type and per-type config.
    """

    model_config = ConfigDict(extra="forbid")

    warehouse_url: str


class IngestResponse(BaseModel):
    """Summary of one ingestion run."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    source_database: str
    tables_ingested: int
    columns_ingested: int

    entities_proposed: int
    measures_proposed: int
    dimensions_proposed: int
    time_dimensions_proposed: int
    relationships_proposed: int
    data_quality_flags_proposed: int

    entities_persisted: int
    """Only entities are persisted in v0 (ADR 0007: tracer bullet per category).
    Other categories are proposed but not yet stored; counts are still reported
    so the UI can show totals."""
