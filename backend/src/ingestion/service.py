"""Ingestion orchestrator.

Takes a Connector, walks every table it exposes, and produces a normalized
SchemaSnapshot suitable for LLM consumption and UI rendering.

This is the ONLY place where warehouse-native type names are translated into
Datum's normalized DatumType enum. Keeping that logic here (not in connectors)
means a new connector author does not need to know our type system.

See ADR 0004.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src.connectors import (
    Connector,
    RawColumn,
    RawTableSchema,
    SampleRows,
)
from src.connectors.types import TableRef
from src.ingestion.types import (
    ColumnSchema,
    DatumType,
    SchemaSnapshot,
    TableSchema,
)

# -----------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------

DEFAULT_SAMPLE_LIMIT = 10
"""Rows to sample per table. Small enough to fit comfortably into LLM
prompts, large enough to surface realistic value patterns."""


# -----------------------------------------------------------------
# Type normalization
# -----------------------------------------------------------------

# Ordered matters: earlier entries win. Broader patterns go later.
# Pattern matching is substring-based against the lowercased native type.
_TYPE_MAPPING: tuple[tuple[tuple[str, ...], DatumType], ...] = (
    # Integers (check before numeric — "integer" could match loosely)
    (("smallint", "integer", "bigint", "int2", "int4", "int8", "serial"), DatumType.INTEGER),
    # Numerics with fractional precision
    (("numeric", "decimal", "real", "double", "float", "money"), DatumType.NUMERIC),
    # Booleans
    (("boolean", "bool"), DatumType.BOOLEAN),
    # Dates and timestamps — date check must precede timestamp to avoid mis-match
    (("timestamp", "datetime"), DatumType.TIMESTAMP),
    (("date",), DatumType.DATE),
    # JSON
    (("json", "jsonb"), DatumType.JSON),
    # Strings (catch-all for textual types)
    (("character", "varchar", "char", "text", "uuid"), DatumType.STRING),
)


def _normalize_datum_type(native_type: str) -> DatumType:
    """Map a warehouse-native type string onto Datum's normalized enum.

    Unknown types fall through to DatumType.UNKNOWN. The original native
    string is preserved on ColumnSchema.native_type for auditing.
    """
    lowered = native_type.lower().strip()
    for patterns, datum_type in _TYPE_MAPPING:
        if any(p in lowered for p in patterns):
            return datum_type
    return DatumType.UNKNOWN


# -----------------------------------------------------------------
# Sample extraction
# -----------------------------------------------------------------

def _extract_column_samples(
    raw_column: RawColumn,
    sample_rows: Iterable[dict[str, Any]],
    max_values: int = DEFAULT_SAMPLE_LIMIT,
) -> tuple[tuple[Any, ...], int]:
    """Given the raw column metadata and the table's sample rows, return
    (sample_values, distinct_count) for this column.

    Values are returned in insertion order up to max_values. NULLs are
    included — they're informative (high NULL rate signals data quality issues).
    """
    values: list[Any] = []
    distinct: set[Any] = set()

    for row in sample_rows:
        if raw_column.name not in row:
            continue
        v = row[raw_column.name]
        if len(values) < max_values:
            values.append(v)
        try:
            distinct.add(v)
        except TypeError:
            # Unhashable (e.g. dict from jsonb). Count via string repr as a fallback.
            distinct.add(repr(v))

    return tuple(values), len(distinct)


# -----------------------------------------------------------------
# Per-table ingestion
# -----------------------------------------------------------------

def _ingest_table(
    connector: Connector,
    ref: TableRef,
    sample_limit: int,
) -> TableSchema:
    """Read one table's schema and sample, return a normalized TableSchema."""
    raw_schema: RawTableSchema = connector.describe_table(ref)
    sample: SampleRows = connector.sample_rows(ref, limit=sample_limit)

    columns: list[ColumnSchema] = []
    for raw_col in raw_schema.columns:
        sample_values, distinct_count = _extract_column_samples(
            raw_col, sample.rows, max_values=sample_limit
        )
        columns.append(
            ColumnSchema(
                name=raw_col.name,
                datum_type=_normalize_datum_type(raw_col.data_type),
                native_type=raw_col.data_type,
                is_nullable=raw_col.is_nullable,
                ordinal_position=raw_col.ordinal_position,
                comment=raw_col.comment,
                sample_values=sample_values,
                distinct_sample_count=distinct_count,
            )
        )

    return TableSchema(
        ref=ref,
        columns=tuple(columns),
        primary_key_columns=tuple(raw_schema.primary_key_columns),
        row_count_estimate=raw_schema.row_count_estimate,
        row_count_is_estimate=True,
        sample_rows_returned=len(sample.rows),
        sample_truncated=sample.truncated,
        comment=raw_schema.comment,
    )


# -----------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------

def ingest(
    connector: Connector,
    sample_limit: int = DEFAULT_SAMPLE_LIMIT,
) -> SchemaSnapshot:
    """Walk every visible table on the connector and produce a SchemaSnapshot.

    This is the single entry point used by Step 9 (LLM proposals) and
    Step 10 (review UI). Everything downstream consumes SchemaSnapshot.
    """
    tables_refs = connector.list_tables()
    if not tables_refs:
        return SchemaSnapshot.new(source_database="", tables=[])

    source_database = tables_refs[0].database
    tables = [_ingest_table(connector, ref, sample_limit) for ref in tables_refs]
    return SchemaSnapshot.new(source_database=source_database, tables=tables)
