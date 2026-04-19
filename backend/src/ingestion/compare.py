"""Structural comparison of SchemaSnapshots.

Two snapshots are structurally equivalent if they describe the same
database structure — same tables, same columns with the same types and
nullability, same primary keys. Sample values, row counts, and comments
are ignored. See ADR 0008 for rationale.
"""

from __future__ import annotations

from src.ingestion.types import SchemaSnapshot, TableSchema


def snapshots_are_structurally_equivalent(
    a: SchemaSnapshot, b: SchemaSnapshot
) -> bool:
    """Return True if two snapshots describe the same schema structure.

    See ADR 0008 for the precise definition of "structural equivalence".
    """
    if a.source_database != b.source_database:
        return False

    a_tables = {t.ref.qualified: t for t in a.tables}
    b_tables = {t.ref.qualified: t for t in b.tables}

    if set(a_tables.keys()) != set(b_tables.keys()):
        return False

    for qualified, a_table in a_tables.items():
        b_table = b_tables[qualified]
        if not _tables_are_structurally_equivalent(a_table, b_table):
            return False

    return True


def _tables_are_structurally_equivalent(a: TableSchema, b: TableSchema) -> bool:
    if set(a.primary_key_columns) != set(b.primary_key_columns):
        return False

    def _column_signature(cols) -> set[tuple]:
        return {
            (
                c.name,
                c.datum_type.value,
                c.native_type,
                c.is_nullable,
                c.ordinal_position,
            )
            for c in cols
        }

    return _column_signature(a.columns) == _column_signature(b.columns)
