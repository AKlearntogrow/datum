"""Request and response schemas for the /api/ingest endpoint."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IngestRequest(BaseModel):
    """POST body to kick off an ingestion run."""

    model_config = ConfigDict(extra="forbid")

    warehouse_url: str


class IngestResponse(BaseModel):
    """Summary of one ingestion run.

    When `skipped` is True, the warehouse was structurally unchanged since
    the last run and no new snapshot was created. All counts are zero in
    that case, and `last_snapshot_id` / `last_snapshot_captured_at` point
    to the most recent existing snapshot. See ADR 0008.
    """

    model_config = ConfigDict(extra="forbid")

    skipped: bool = False
    reason: str | None = None
    last_snapshot_id: str | None = None
    last_snapshot_captured_at: datetime | None = None

    snapshot_id: str | None = None
    source_database: str
    tables_ingested: int = 0
    columns_ingested: int = 0

    entities_proposed: int = 0
    measures_proposed: int = 0
    dimensions_proposed: int = 0
    time_dimensions_proposed: int = 0
    relationships_proposed: int = 0
    data_quality_flags_proposed: int = 0

    entities_persisted: int = 0
