"""Persistence for SchemaSnapshot and its shredded tables/columns.

Public API:
    persist_snapshot(db, snapshot) -> str         # returns snapshot id
    load_snapshot(db, snapshot_id) -> SchemaSnapshot | None
    snapshot_column_id_for(db, snapshot_id, table_qualified, column) -> str | None

The persist function flattens the in-memory SchemaSnapshot into three
tables. Round-tripping is intentional: load_snapshot reconstructs the
same dataclass so downstream code doesn't care whether a snapshot came
from a fresh ingestion or from storage.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.connectors.types import TableRef
from src.ingestion.types import (
    ColumnSchema,
    DatumType,
    SchemaSnapshot as SchemaSnapshotDC,
    TableSchema,
)
from src.models.snapshots import (
    SchemaSnapshot as SchemaSnapshotORM,
    SnapshotColumn,
    SnapshotTable,
)


def persist_snapshot(db: Session, snapshot: SchemaSnapshotDC) -> str:
    """Write a SchemaSnapshot dataclass to the database. Returns the snapshot id.

    The snapshot's own UUID is reused — we don't generate a new one.
    This keeps the in-memory and persisted IDs identical, which is what
    downstream code (proposals, UI) expects.
    """
    snap_row = SchemaSnapshotORM(
        id=snapshot.id,
        captured_at=snapshot.captured_at,
        source_database=snapshot.source_database,
    )
    db.add(snap_row)

    for tbl in snapshot.tables:
        table_row = SnapshotTable(
            snapshot_id=snapshot.id,
            database_name=tbl.ref.database,
            schema_name=tbl.ref.schema,
            table_name=tbl.ref.name,
            primary_key_columns=json.dumps(list(tbl.primary_key_columns)) if tbl.primary_key_columns else None,
            row_count_estimate=tbl.row_count_estimate,
            comment=tbl.comment,
        )
        db.add(table_row)
        db.flush()  # populate table_row.id for child rows

        for col in tbl.columns:
            col_row = SnapshotColumn(
                table_id=table_row.id,
                column_name=col.name,
                datum_type=col.datum_type.value,
                native_type=col.native_type,
                is_nullable=col.is_nullable,
                ordinal_position=col.ordinal_position,
                comment=col.comment,
                sample_values_json=_encode_sample_values(col.sample_values),
                distinct_sample_count=col.distinct_sample_count,
            )
            db.add(col_row)

    db.flush()
    return snapshot.id


def load_snapshot(db: Session, snapshot_id: str) -> SchemaSnapshotDC | None:
    """Rebuild a SchemaSnapshot dataclass from the database.

    Returns None if the snapshot doesn't exist.
    """
    snap_row = db.get(SchemaSnapshotORM, snapshot_id)
    if snap_row is None:
        return None

    tables: list[TableSchema] = []
    for tbl in snap_row.tables:
        columns = tuple(
            ColumnSchema(
                name=c.column_name,
                datum_type=DatumType(c.datum_type),
                native_type=c.native_type,
                is_nullable=c.is_nullable,
                ordinal_position=c.ordinal_position,
                comment=c.comment,
                sample_values=tuple(_decode_sample_values(c.sample_values_json)),
                distinct_sample_count=c.distinct_sample_count,
            )
            for c in sorted(tbl.columns, key=lambda x: x.ordinal_position)
        )
        pk = (
            tuple(json.loads(tbl.primary_key_columns))
            if tbl.primary_key_columns
            else ()
        )
        tables.append(
            TableSchema(
                ref=TableRef(
                    database=tbl.database_name,
                    schema=tbl.schema_name,
                    name=tbl.table_name,
                ),
                columns=columns,
                primary_key_columns=pk,
                row_count_estimate=tbl.row_count_estimate,
                row_count_is_estimate=True,
                sample_rows_returned=0,   # not round-tripped; not needed downstream
                sample_truncated=False,
                comment=tbl.comment,
            )
        )

    return SchemaSnapshotDC(
        id=snap_row.id,
        captured_at=snap_row.captured_at,
        source_database=snap_row.source_database,
        tables=tuple(tables),
    )


def snapshot_column_id_for(
    db: Session,
    snapshot_id: str,
    table_qualified: str,
    column_name: str,
) -> str | None:
    """Resolve a (snapshot, "schema.table", column) triple to a SnapshotColumn.id.

    Used by the entity-persistence flow to turn LLM-proposed source_columns
    (which come as strings like "messy_warehouse.public.invoices.customer")
    into concrete foreign keys.

    Accepts both "schema.table" and "database.schema.table" forms.
    """
    parts = table_qualified.split(".")
    if len(parts) == 3:
        _database, schema_name, table_name = parts
    elif len(parts) == 2:
        schema_name, table_name = parts
    else:
        return None

    stmt = (
        select(SnapshotColumn.id)
        .join(SnapshotTable, SnapshotTable.id == SnapshotColumn.table_id)
        .where(SnapshotTable.snapshot_id == snapshot_id)
        .where(SnapshotTable.schema_name == schema_name)
        .where(SnapshotTable.table_name == table_name)
        .where(SnapshotColumn.column_name == column_name)
    )
    return db.execute(stmt).scalar_one_or_none()


# ----------------------------------------------------------------------
# Sample value encoding — keeps type fidelity across Text storage.
# ----------------------------------------------------------------------

def _encode_sample_values(values: tuple) -> str | None:
    """Encode sample values as JSON. Non-JSON-serializable values become strings."""
    if not values:
        return None
    return json.dumps([_jsonable(v) for v in values], default=str)


def _decode_sample_values(text: str | None) -> list:
    """Decode sample values back from JSON; returns [] for NULL text."""
    if text is None:
        return []
    return json.loads(text)


def _jsonable(v):
    """Coerce values that json.dumps can't handle natively into strings.

    Decimals, dates, datetimes all stringify cleanly and the string form
    is what the LLM sees anyway (via _format_sample_values in the renderer).
    """
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)
