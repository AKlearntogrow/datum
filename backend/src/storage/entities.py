"""Persistence and mutation for entity definitions.

Public API:
    persist_entity_proposals(db, snapshot_id, proposals, ...)
        -> list[str] of new entity ids
    list_entity_definitions(db, status=None) -> list[EntityDefinition]
    load_entity_definition(db, entity_id) -> EntityDefinition | None
    approve_entity_definition(db, entity_id, approved_by)
        -> EntityDefinition
    reject_entity_definition(db, entity_id, rejected_by, reason=None)
        -> EntityDefinition
    update_entity_definition(db, entity_id, fields) -> EntityDefinition

Every function takes a Session; the caller owns commit/rollback.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.entities import EntityDefinition, EntitySourceColumn
from src.semantic.proposals import EntityProposal
from src.storage.snapshots import snapshot_column_id_for


class EntityStorageError(Exception):
    """Raised when an entity operation can't be completed."""


# ----------------------------------------------------------------------
# Create
# ----------------------------------------------------------------------

def persist_entity_proposals(
    db: Session,
    snapshot_id: str,
    proposals: list[EntityProposal],
    prompt_version: str,
    model: str,
    proposed_by: str = "system",
) -> list[str]:
    """Persist a batch of EntityProposals against a given snapshot.

    Each proposal becomes one EntityDefinition with status='proposed'
    and one EntitySourceColumn per referenced column.

    Raises EntityStorageError if any proposal references a column that
    isn't in the snapshot. We fail rather than silently dropping the
    reference — if the LLM hallucinated a column, we want to know.

    Returns the list of newly created entity IDs in input order.
    """
    now = datetime.now(timezone.utc)
    new_ids: list[str] = []

    for proposal in proposals:
        source_col_ids: list[str] = []
        for ref in proposal.source_columns:
            col_id = snapshot_column_id_for(db, snapshot_id, ref.table, ref.column)
            if col_id is None:
                raise EntityStorageError(
                    f"Entity '{proposal.name}' references unknown column "
                    f"{ref.table}.{ref.column} in snapshot {snapshot_id}"
                )
            source_col_ids.append(col_id)

        entity = EntityDefinition(
            name=proposal.name,
            display_name=proposal.display_name,
            description=proposal.description,
            rationale=proposal.rationale,
            evidence_json=json.dumps(proposal.evidence),
            confidence=proposal.confidence.value,
            status="proposed",
            proposed_by=proposed_by,
            proposed_at=now,
            prompt_version=prompt_version,
            model=model,
            source_snapshot_id=snapshot_id,
        )
        db.add(entity)
        db.flush()  # populate entity.id

        for col_id in source_col_ids:
            db.add(EntitySourceColumn(
                entity_id=entity.id,
                snapshot_column_id=col_id,
            ))

        new_ids.append(entity.id)

    db.flush()
    return new_ids


# ----------------------------------------------------------------------
# Read
# ----------------------------------------------------------------------

def list_entity_definitions(
    db: Session,
    status: str | None = None,
) -> list[EntityDefinition]:
    """List entity definitions, optionally filtered by status.

    Ordered by proposed_at descending (newest first).
    """
    stmt = select(EntityDefinition).order_by(EntityDefinition.proposed_at.desc())
    if status is not None:
        stmt = stmt.where(EntityDefinition.status == status)
    return list(db.execute(stmt).scalars())


def load_entity_definition(db: Session, entity_id: str) -> EntityDefinition | None:
    return db.get(EntityDefinition, entity_id)


# ----------------------------------------------------------------------
# Mutations (lifecycle transitions)
# ----------------------------------------------------------------------

def approve_entity_definition(
    db: Session,
    entity_id: str,
    approved_by: str,
) -> EntityDefinition:
    """Move a proposed entity to approved. Idempotent on already-approved.
    Raises EntityStorageError if the entity is in a non-approvable state."""
    entity = db.get(EntityDefinition, entity_id)
    if entity is None:
        raise EntityStorageError(f"Entity {entity_id} not found")

    if entity.status == "approved":
        return entity   # idempotent

    if entity.status != "proposed":
        raise EntityStorageError(
            f"Cannot approve entity in status '{entity.status}'"
        )

    entity.status = "approved"
    entity.approved_by = approved_by
    entity.approved_at = datetime.now(timezone.utc)
    db.flush()
    return entity


def reject_entity_definition(
    db: Session,
    entity_id: str,
    rejected_by: str,
    reason: str | None = None,
) -> EntityDefinition:
    """Move a proposed entity to rejected.
    Raises EntityStorageError if the entity is in a non-rejectable state."""
    entity = db.get(EntityDefinition, entity_id)
    if entity is None:
        raise EntityStorageError(f"Entity {entity_id} not found")

    if entity.status == "rejected":
        return entity   # idempotent

    if entity.status != "proposed":
        raise EntityStorageError(
            f"Cannot reject entity in status '{entity.status}'"
        )

    entity.status = "rejected"
    entity.rejected_by = rejected_by
    entity.rejected_at = datetime.now(timezone.utc)
    entity.rejected_reason = reason
    db.flush()
    return entity


def update_entity_definition(
    db: Session,
    entity_id: str,
    fields: dict,
) -> EntityDefinition:
    """Revise a proposed entity in place (ADR 0006: revisions are cheap).

    Only allowed on 'proposed' entities — you cannot edit an already-approved
    definition; instead you'd create a new one that supersedes it (future work).

    Accepts only these editable fields:
        name, display_name, description, rationale, confidence

    Other fields are silently ignored to keep this simple and explicit.
    """
    entity = db.get(EntityDefinition, entity_id)
    if entity is None:
        raise EntityStorageError(f"Entity {entity_id} not found")

    if entity.status != "proposed":
        raise EntityStorageError(
            f"Cannot edit entity in status '{entity.status}' — use supersession instead"
        )

    editable = {"name", "display_name", "description", "rationale", "confidence"}
    for key, value in fields.items():
        if key in editable:
            setattr(entity, key, value)

    db.flush()
    return entity
