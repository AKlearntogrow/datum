"""Unit tests for the structural-equivalence comparison.

Pure function tests — no database, no I/O. Covers the cases enumerated
in ADR 0008: same schema (equal), different column, different table,
different type, different nullability, different primary key, different
source database, different sample values (still equal).
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.connectors.types import TableRef
from src.ingestion.compare import snapshots_are_structurally_equivalent
from src.ingestion.types import (
    ColumnSchema,
    DatumType,
    SchemaSnapshot,
    TableSchema,
)


def _col(
    name: str,
    datum_type: DatumType = DatumType.STRING,
    native_type: str = "character varying",
    is_nullable: bool = True,
    ordinal: int = 1,
    samples: tuple = (),
    distinct: int = 0,
) -> ColumnSchema:
    return ColumnSchema(
        name=name,
        datum_type=datum_type,
        native_type=native_type,
        is_nullable=is_nullable,
        ordinal_position=ordinal,
        sample_values=samples,
        distinct_sample_count=distinct,
    )


def _table(
    name: str,
    columns: tuple[ColumnSchema, ...],
    primary_key_columns: tuple[str, ...] = (),
    row_count_estimate: int | None = None,
) -> TableSchema:
    return TableSchema(
        ref=TableRef(database="db", schema="public", name=name),
        columns=columns,
        primary_key_columns=primary_key_columns,
        row_count_estimate=row_count_estimate,
        sample_rows_returned=0,
        sample_truncated=False,
    )


def _snapshot(
    tables: tuple[TableSchema, ...],
    source_database: str = "db",
    snapshot_id: str = "id",
) -> SchemaSnapshot:
    return SchemaSnapshot(
        id=snapshot_id,
        captured_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
        source_database=source_database,
        tables=tables,
    )


class TestEquivalent:
    def test_identical_snapshots(self) -> None:
        tbl = _table("orders", (_col("id", ordinal=1, samples=(1, 2)),))
        a = _snapshot((tbl,))
        b = _snapshot((tbl,))
        assert snapshots_are_structurally_equivalent(a, b)

    def test_sample_values_differ_but_still_equal(self) -> None:
        """Sample values are intentionally ignored by the comparison."""
        a = _snapshot((_table("orders", (_col("id", samples=(1, 2, 3)),)),))
        b = _snapshot((_table("orders", (_col("id", samples=(99, 100)),)),))
        assert snapshots_are_structurally_equivalent(a, b)

    def test_row_counts_differ_but_still_equal(self) -> None:
        """Row count estimates are ignored by the comparison."""
        a = _snapshot((_table("orders", (_col("id"),), row_count_estimate=10),))
        b = _snapshot((_table("orders", (_col("id"),), row_count_estimate=100_000),))
        assert snapshots_are_structurally_equivalent(a, b)

    def test_different_snapshot_id_still_equal(self) -> None:
        """The snapshot UUID itself is part of identity, not structure."""
        tbl = _table("orders", (_col("id"),))
        a = _snapshot((tbl,), snapshot_id="aaa")
        b = _snapshot((tbl,), snapshot_id="bbb")
        assert snapshots_are_structurally_equivalent(a, b)

    def test_columns_in_different_list_order_if_same_ordinal_positions(self) -> None:
        """Column list is a set when compared — only the ordinal matters."""
        cols_a = (
            _col("id", ordinal=1),
            _col("name", ordinal=2),
        )
        cols_b = (
            _col("name", ordinal=2),
            _col("id", ordinal=1),
        )
        a = _snapshot((_table("orders", cols_a),))
        b = _snapshot((_table("orders", cols_b),))
        assert snapshots_are_structurally_equivalent(a, b)


class TestNotEquivalent:
    def test_different_source_database(self) -> None:
        tbl = _table("orders", (_col("id"),))
        a = _snapshot((tbl,), source_database="warehouse_a")
        b = _snapshot((tbl,), source_database="warehouse_b")
        assert not snapshots_are_structurally_equivalent(a, b)

    def test_different_tables(self) -> None:
        a = _snapshot((_table("orders", (_col("id"),)),))
        b = _snapshot((_table("users", (_col("id"),)),))
        assert not snapshots_are_structurally_equivalent(a, b)

    def test_added_column(self) -> None:
        a = _snapshot((_table("orders", (_col("id", ordinal=1),)),))
        b = _snapshot((_table("orders", (_col("id", ordinal=1), _col("name", ordinal=2))),))
        assert not snapshots_are_structurally_equivalent(a, b)

    def test_different_column_type(self) -> None:
        a = _snapshot((_table("orders", (_col("amount", datum_type=DatumType.INTEGER, native_type="integer"),)),))
        b = _snapshot((_table("orders", (_col("amount", datum_type=DatumType.NUMERIC, native_type="numeric"),)),))
        assert not snapshots_are_structurally_equivalent(a, b)

    def test_different_nullability(self) -> None:
        a = _snapshot((_table("orders", (_col("id", is_nullable=False),)),))
        b = _snapshot((_table("orders", (_col("id", is_nullable=True),)),))
        assert not snapshots_are_structurally_equivalent(a, b)

    def test_different_primary_key(self) -> None:
        a = _snapshot((_table("orders", (_col("id"),), primary_key_columns=("id",)),))
        b = _snapshot((_table("orders", (_col("id"),), primary_key_columns=()),))
        assert not snapshots_are_structurally_equivalent(a, b)

    def test_different_column_ordinal_position(self) -> None:
        """Column reordering is a schema change — flag it."""
        a = _snapshot((_table("orders", (_col("id", ordinal=1), _col("name", ordinal=2))),))
        b = _snapshot((_table("orders", (_col("id", ordinal=2), _col("name", ordinal=1))),))
        assert not snapshots_are_structurally_equivalent(a, b)
