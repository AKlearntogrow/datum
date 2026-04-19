"""Normalized internal schema representation.

These are Datum's warehouse-agnostic types. Every connector's RawTableSchema
gets translated into these shapes by the ingestion orchestrator (service.py).
The LLM (Step 9) and the review UI (Step 10) consume only these — never the
raw connector types.

Stays free of SQL, LLM calls, and ORM imports. Pure dataclasses and enums.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.connectors.types import TableRef


class DatumType(str, Enum):
    """Normalized type categories. Every warehouse-native type maps to one
    of these. Covers ~95% of real-world columns; rare types fall back to UNKNOWN
    with the native type preserved for debugging.
    """

    STRING = "string"
    INTEGER = "integer"
    NUMERIC = "numeric"         # decimal, float, double — anything with fractional precision
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"     # with or without timezone
    JSON = "json"               # json, jsonb, structured blobs
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ColumnSchema:
    """A single column, normalized and enriched with sample values.

    `native_type` preserves the warehouse-specific type string (e.g.,
    "character varying", "NUMERIC(12,2)") for debugging and audit. Ingestion
    decisions should use `datum_type` instead.
    """

    name: str
    datum_type: DatumType
    native_type: str
    is_nullable: bool
    ordinal_position: int
    comment: str | None = None
    sample_values: tuple[Any, ...] = ()    # small set of real values, for LLM context
    distinct_sample_count: int = 0         # how many distinct values seen in the sample


@dataclass(frozen=True)
class TableSchema:
    """A single table: its reference, columns, sample context."""

    ref: TableRef
    columns: tuple[ColumnSchema, ...]
    primary_key_columns: tuple[str, ...] = ()
    row_count_estimate: int | None = None
    row_count_is_estimate: bool = True   # False only if we did a real COUNT(*)
    sample_rows_returned: int = 0
    sample_truncated: bool = False
    comment: str | None = None


@dataclass(frozen=True)
class SchemaSnapshot:
    """The full output of one ingestion run against one warehouse.

    A snapshot is immutable. New ingestion runs produce new snapshots with
    fresh IDs; versioning comes for free. See ADR 0003 for governance.
    """

    id: str                          # UUID; auto-generated
    captured_at: datetime            # UTC; auto-generated
    source_database: str             # database name as reported by the connector
    tables: tuple[TableSchema, ...]

    @classmethod
    def new(
        cls,
        source_database: str,
        tables: list[TableSchema] | tuple[TableSchema, ...],
    ) -> SchemaSnapshot:
        """Factory that stamps id and captured_at automatically.

        Using a factory (rather than requiring callers to pass id/captured_at)
        means there's exactly one place in the codebase that decides how
        snapshots are identified and timestamped.
        """
        return cls(
            id=str(uuid.uuid4()),
            captured_at=datetime.now(timezone.utc),
            source_database=source_database,
            tables=tuple(tables),
        )
