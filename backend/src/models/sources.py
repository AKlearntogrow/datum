"""ORM models for data sources and scopes.

A DataSource is a named, persistent warehouse connection.
A Scope is a saved selection of schemas/tables within a DataSource.

See ADR 0009 for the full design. These tables are created in 11a-i;
scope_id columns on existing tables (snapshots, entities) come in 11a-ii.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class DataSource(Base):
    """A named, persistent warehouse connection."""

    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    warehouse_type: Mapped[str] = mapped_column(Text, nullable=False)
    connection_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(Text, nullable=False, server_default="local_user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    scopes: Mapped[list["Scope"]] = relationship(
        back_populates="data_source",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Scope(Base):
    """A saved selection of schemas/tables within a DataSource."""

    __tablename__ = "scopes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    data_source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("data_sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    included_schemas: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    excluded_tables: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(Text, nullable=False, server_default="local_user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    data_source: Mapped["DataSource"] = relationship(back_populates="scopes")
