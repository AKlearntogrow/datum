"""HTTP routes for entity definitions.

Routes do not open sessions or call Anthropic. They:
  1. Take inputs (path params, request bodies)
  2. Call storage functions with the session dependency
  3. Convert ORM results to response shapes
  4. Commit the transaction

Every error translates to an HTTP code via the handlers in api/errors.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.core.db import get_db
from src.schemas.entities import (
    EntityApproveRequest,
    EntityListResponse,
    EntityRejectRequest,
    EntityResponse,
    EntityUpdateRequest,
    entity_to_response,
)
from src.storage import (
    approve_entity_definition,
    list_entity_definitions,
    load_entity_definition,
    reject_entity_definition,
    update_entity_definition,
)
from src.storage.entities import EntityStorageError

# v0 has no auth; the server substitutes this as the actor on writes.
_LOCAL_USER = "local_user"

router = APIRouter(prefix="/api/entities", tags=["entities"])


@router.get("", response_model=EntityListResponse)
def list_entities(
    status: str | None = Query(
        None,
        description="Filter by status: proposed | approved | rejected | superseded",
    ),
    db: Session = Depends(get_db),
) -> EntityListResponse:
    """List entity definitions, optionally filtered by status.

    Ordered by proposed_at descending (newest first).
    """
    entities = list_entity_definitions(db, status=status)
    items = [entity_to_response(e) for e in entities]
    return EntityListResponse(items=items, total=len(items))


@router.get("/{entity_id}", response_model=EntityResponse)
def get_entity(entity_id: str, db: Session = Depends(get_db)) -> EntityResponse:
    entity = load_entity_definition(db, entity_id)
    if entity is None:
        raise EntityStorageError(f"Entity {entity_id} not found")
    return entity_to_response(entity)


@router.patch("/{entity_id}", response_model=EntityResponse)
def update_entity(
    entity_id: str,
    body: EntityUpdateRequest,
    db: Session = Depends(get_db),
) -> EntityResponse:
    """Revise a proposed entity in place (ADR 0006: revisions are cheap).

    Only allowed on 'proposed' entities. Fields not included in the request
    are left unchanged. confidence is normalized from its enum form.
    """
    fields = body.model_dump(exclude_unset=True)
    if "confidence" in fields and fields["confidence"] is not None:
        fields["confidence"] = fields["confidence"].value
    entity = update_entity_definition(db, entity_id, fields)
    db.commit()
    db.refresh(entity)
    return entity_to_response(entity)


@router.post("/{entity_id}/approve", response_model=EntityResponse)
def approve_entity(
    entity_id: str,
    body: EntityApproveRequest | None = None,
    db: Session = Depends(get_db),
) -> EntityResponse:
    """Move a proposed entity to approved.

    v0: no auth. If the client supplies approved_by we honour it, otherwise
    the server substitutes 'local_user'. When real auth lands, the server
    will ignore the request's approved_by and use the authenticated user.
    """
    approved_by = (body.approved_by if body else None) or _LOCAL_USER
    entity = approve_entity_definition(db, entity_id, approved_by=approved_by)
    db.commit()
    db.refresh(entity)
    return entity_to_response(entity)


@router.post("/{entity_id}/reject", response_model=EntityResponse)
def reject_entity(
    entity_id: str,
    body: EntityRejectRequest | None = None,
    db: Session = Depends(get_db),
) -> EntityResponse:
    """Move a proposed entity to rejected. Optional reason is preserved."""
    rejected_by = (body.rejected_by if body else None) or _LOCAL_USER
    reason = body.reason if body else None
    entity = reject_entity_definition(
        db, entity_id, rejected_by=rejected_by, reason=reason
    )
    db.commit()
    db.refresh(entity)
    return entity_to_response(entity)
