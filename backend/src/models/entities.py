"""ORM models for entity definitions.

An 'entity' is the first of six proposal categories (ADR 0005). Every
entity carries the full lifecycle metadata from ADR 0006 so the same
record type works for proposed, approved, rejected, and superseded states.

Subsequent slices will add measures, dimensions, etc. with the same
lifecycle columns — we keep the pattern uniform across categories.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.snapshots import SnapshotColumn


def _uuid() -> str:
    return str(uuid.uuid4())


# Status values: 'proposed', 'approved', 'rejected', 'superseded'.
# Enforced at the Pydantic layer; the DB stores as plain strings for
# flexibility as new states are added.


class EntityDefinition(Base):
    """A single entity proposal or approved entity definition."""

    __tablename__ = "entity_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    # Core content (mirrors EntityProposal)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON-encoded list[str]
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)

    # Lifecycle (ADR 0006)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed", index=True)
    proposed_by: Mapped[str] = mapped_column(String(64), nullable=False)  # "system" or "user:<id>"
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    supersedes_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("entity_definitions.id"), nullable=True
    )
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("entity_definitions.id"), nullable=True
    )

    # Provenance
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("schema_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    source_columns: Mapped[list["EntitySourceColumn"]] = relationship(
        back_populates="entity",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class EntitySourceColumn(Base):
    """Link from an entity definition to a specific snapshot column.

    Using snapshot_column_id (not a free-text table/column string) means
    the compatibility report logic (ADR 0006) can tell immediately when
    a referenced column disappears.
    """

    __tablename__ = "entity_source_columns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    entity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("entity_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_column_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("snapshot_columns.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    entity: Mapped["EntityDefinition"] = relationship(back_populates="source_columns")
    snapshot_column: Mapped["SnapshotColumn"] = relationship(lazy="selectin")
