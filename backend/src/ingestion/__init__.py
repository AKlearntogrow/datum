"""Ingestion layer. Orchestrates connectors and produces normalized
SchemaSnapshots. See ADR 0004 for architecture."""

from src.ingestion.service import DEFAULT_SAMPLE_LIMIT, ingest
from src.ingestion.types import (
    ColumnSchema,
    DatumType,
    SchemaSnapshot,
    TableSchema,
)

__all__ = [
    "ColumnSchema",
    "DatumType",
    "SchemaSnapshot",
    "TableSchema",
    "ingest",
    "DEFAULT_SAMPLE_LIMIT",
]
