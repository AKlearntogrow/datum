"""Pydantic request/response schemas for entity definition endpoints.

These are the shapes the HTTP API exposes — deliberately separate from
the ORM models (backend/src/models/entities.py) and from the Proposer's
schemas (backend/src/semantic/proposals.py).

Why three separate type families?
- ORM models are how we talk to the database; they include columns like
  `evidence_json` (text) that API consumers shouldn't see.
- Proposer schemas are what Claude returns; they represent "a proposal",
  not "an entity with a lifecycle state".
- API schemas are what the UI sees; they present a clean, stable contract
  regardless of how the database or LLM output evolves.

An explicit mapping function (below) converts ORM -> API response.
"""

from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.entities import EntityDefinition
from src.semantic.proposals import Confidence


# ----------------------------------------------------------------------
# Request bodies
# ----------------------------------------------------------------------

class EntityUpdateRequest(BaseModel):
    """PATCH body for revising a proposed entity before approval.

    Every field is optional — only included fields are updated.
    Matches the editable-fields whitelist in storage.update_entity_definition.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    display_name: str | None = None
    description: str | None = None
    rationale: str | None = None
    confidence: Confidence | None = None


class EntityApproveRequest(BaseModel):
    """POST body for approving. v0 has no auth, so approved_by defaults
    server-side. The field exists on the request so we can add real
    auth later without changing the API shape — current UI can omit it."""

    model_config = ConfigDict(extra="forbid")

    approved_by: str | None = None   # v0: server substitutes 'local_user'


class EntityRejectRequest(BaseModel):
    """POST body for rejecting. Reason is optional but encouraged."""

    model_config = ConfigDict(extra="forbid")

    rejected_by: str | None = None   # v0: server substitutes 'local_user'
    reason: str | None = None


# ----------------------------------------------------------------------
# Response bodies
# ----------------------------------------------------------------------

class SourceColumnRef(BaseModel):
    """One source column a definition references.

    Emits the qualified table name as 'schema.table' plus the column name,
    mirroring what the LLM produces and what humans read. The snapshot
    column id is included for future compatibility-report use cases.
    """

    model_config = ConfigDict(extra="forbid")

    snapshot_column_id: str
    table: str           # "schema.table" form
    column: str


class EntityResponse(BaseModel):
    """What the API returns for a single entity definition."""

    model_config = ConfigDict(extra="forbid")

    id: str

    # Content
    name: str
    display_name: str
    description: str
    rationale: str
    evidence: list[str]
    confidence: Confidence
    source_columns: list[SourceColumnRef]

    # Lifecycle
    status: str
    proposed_by: str
    proposed_at: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejected_by: str | None = None
    rejected_at: datetime | None = None
    rejected_reason: str | None = None

    # Provenance (optional to consumers, useful for debugging)
    prompt_version: str | None = None
    model: str | None = None


class EntityListResponse(BaseModel):
    """Envelope for list endpoints. Using an envelope (rather than a
    bare list) lets us add pagination fields later without a breaking change."""

    model_config = ConfigDict(extra="forbid")

    items: list[EntityResponse]
    total: int


# ----------------------------------------------------------------------
# ORM -> API conversion
# ----------------------------------------------------------------------

def entity_to_response(entity: EntityDefinition) -> EntityResponse:
    """Convert an ORM EntityDefinition into an EntityResponse.

    This is the only function that knows about both shapes. API routes
    call this; they never hand an ORM object to Pydantic directly.
    """
    source_columns = [
        SourceColumnRef(
            snapshot_column_id=link.snapshot_column_id,
            table=f"{link.snapshot_column.table.schema_name}.{link.snapshot_column.table.table_name}",
            column=link.snapshot_column.column_name,
        )
        for link in entity.source_columns
    ]

    evidence = json.loads(entity.evidence_json) if entity.evidence_json else []

    return EntityResponse(
        id=entity.id,
        name=entity.name,
        display_name=entity.display_name,
        description=entity.description,
        rationale=entity.rationale,
        evidence=evidence,
        confidence=Confidence(entity.confidence),
        source_columns=source_columns,
        status=entity.status,
        proposed_by=entity.proposed_by,
        proposed_at=entity.proposed_at,
        approved_by=entity.approved_by,
        approved_at=entity.approved_at,
        rejected_by=entity.rejected_by,
        rejected_at=entity.rejected_at,
        rejected_reason=entity.rejected_reason,
        prompt_version=entity.prompt_version,
        model=entity.model,
    )
