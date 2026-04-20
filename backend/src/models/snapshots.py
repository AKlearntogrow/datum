"""ORM models for schema snapshots.

Shreds the ingestion SchemaSnapshot into relational tables so we can
join `entity_source_columns` (and future definition→column links) to
specific captured columns without deserializing JSON.

See ADR 0006: every Definition references a source_snapshot_id so
schema evolution comparisons are straightforward.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class SchemaSnapshot(Base):
    """One ingestion run against one warehouse."""

    __tablename__ = "schema_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_database: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("scopes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    scope: Mapped["Scope"] = relationship()
    tables: Mapped[list["SnapshotTable"]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class SnapshotTable(Base):
    """One table inside a snapshot."""

    __tablename__ = "snapshot_tables"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "schema_name", "table_name", name="uq_snapshot_table"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("schema_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    database_name: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_name: Mapped[str] = mapped_column(String(255), nullable=False)
    table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_key_columns: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded list
    row_count_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    snapshot: Mapped["SchemaSnapshot"] = relationship(back_populates="tables")
    columns: Mapped[list["SnapshotColumn"]] = relationship(
        back_populates="table",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def qualified_name(self) -> str:
        return f"{self.schema_name}.{self.table_name}"


class SnapshotColumn(Base):
    """One column inside a snapshot table."""

    __tablename__ = "snapshot_columns"
    __table_args__ = (
        UniqueConstraint("table_id", "column_name", name="uq_snapshot_column"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    table_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("snapshot_tables.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    datum_type: Mapped[str] = mapped_column(String(32), nullable=False)
    native_type: Mapped[str] = mapped_column(String(255), nullable=False)
    is_nullable: Mapped[bool] = mapped_column(nullable=False)
    ordinal_position: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_values_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    distinct_sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    table: Mapped["SnapshotTable"] = relationship(back_populates="columns")
