"""Unit tests for the snapshot-to-Markdown renderer.

Pure function tests — no database, no LLM, no network. These test that
a given SchemaSnapshot produces the expected Markdown shape.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.connectors.types import TableRef
from src.ingestion.types import (
    ColumnSchema,
    DatumType,
    SchemaSnapshot,
    TableSchema,
)
from src.semantic.renderer import render_snapshot_for_prompt


def _make_column(
    name: str,
    datum_type: DatumType = DatumType.STRING,
    native_type: str = "character varying",
    is_nullable: bool = True,
    ordinal_position: int = 1,
    sample_values: tuple = (),
    distinct_sample_count: int = 0,
) -> ColumnSchema:
    return ColumnSchema(
        name=name,
        datum_type=datum_type,
        native_type=native_type,
        is_nullable=is_nullable,
        ordinal_position=ordinal_position,
        sample_values=sample_values,
        distinct_sample_count=distinct_sample_count,
    )


def _make_table(
    name: str,
    columns: tuple[ColumnSchema, ...],
    primary_key_columns: tuple[str, ...] = (),
    row_count_estimate: int | None = None,
    sample_truncated: bool = False,
) -> TableSchema:
    return TableSchema(
        ref=TableRef(database="test_db", schema="public", name=name),
        columns=columns,
        primary_key_columns=primary_key_columns,
        row_count_estimate=row_count_estimate,
        sample_rows_returned=len(columns[0].sample_values) if columns else 0,
        sample_truncated=sample_truncated,
    )


def _make_snapshot(tables: tuple[TableSchema, ...]) -> SchemaSnapshot:
    return SchemaSnapshot(
        id="fixed-id-for-tests",
        captured_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
        source_database="test_db",
        tables=tables,
    )


class TestEmptySnapshot:
    def test_empty_snapshot_renders_without_crashing(self) -> None:
        snap = _make_snapshot(tables=())
        out = render_snapshot_for_prompt(snap)
        assert "test_db" in out
        assert "No tables found" in out


class TestSingleTable:
    def test_table_heading_included(self) -> None:
        tbl = _make_table("orders", (_make_column("id"),))
        out = render_snapshot_for_prompt(_make_snapshot((tbl,)))
        assert "test_db.public.orders" in out

    def test_primary_key_rendered(self) -> None:
        tbl = _make_table(
            "orders",
            (_make_column("id"),),
            primary_key_columns=("id",),
        )
        out = render_snapshot_for_prompt(_make_snapshot((tbl,)))
        assert "Primary key" in out
        assert "`id`" in out

    def test_composite_primary_key_rendered(self) -> None:
        tbl = _make_table(
            "order_items",
            (_make_column("order_id"), _make_column("sku", ordinal_position=2)),
            primary_key_columns=("order_id", "sku"),
        )
        out = render_snapshot_for_prompt(_make_snapshot((tbl,)))
        assert "`order_id`" in out
        assert "`sku`" in out

    def test_row_count_estimate_shown(self) -> None:
        tbl = _make_table("orders", (_make_column("id"),), row_count_estimate=1234)
        out = render_snapshot_for_prompt(_make_snapshot((tbl,)))
        assert "1,234" in out

    def test_row_count_unknown_shown_honestly(self) -> None:
        tbl = _make_table("orders", (_make_column("id"),), row_count_estimate=None)
        out = render_snapshot_for_prompt(_make_snapshot((tbl,)))
        assert "unknown" in out.lower()

    def test_truncated_sample_flagged(self) -> None:
        tbl = _make_table(
            "orders", (_make_column("id", sample_values=(1, 2, 3)),),
            sample_truncated=True,
        )
        out = render_snapshot_for_prompt(_make_snapshot((tbl,)))
        assert "truncated" in out.lower() or "more rows" in out.lower()


class TestColumnRendering:
    def test_columns_table_has_header(self) -> None:
        tbl = _make_table("orders", (_make_column("id"),))
        out = render_snapshot_for_prompt(_make_snapshot((tbl,)))
        assert "Name" in out
        assert "Normalized type" in out
        assert "Sample values" in out

    def test_sample_values_rendered(self) -> None:
        tbl = _make_table(
            "orders",
            (_make_column("status", sample_values=("open", "closed"), distinct_sample_count=2),),
        )
        out = render_snapshot_for_prompt(_make_snapshot((tbl,)))
        assert "'open'" in out
        assert "'closed'" in out

    def test_null_values_rendered_as_null(self) -> None:
        tbl = _make_table(
            "orders",
            (_make_column("amount", sample_values=(100, None, 200)),),
        )
        out = render_snapshot_for_prompt(_make_snapshot((tbl,)))
        assert "NULL" in out

    def test_many_samples_truncated_in_display(self) -> None:
        tbl = _make_table(
            "orders",
            (_make_column("id", sample_values=tuple(range(10))),),
        )
        out = render_snapshot_for_prompt(_make_snapshot((tbl,)))
        # Default display limit is 5 — expect a "(+5 more)" hint
        assert "more" in out.lower()

    def test_nullability_shown(self) -> None:
        tbl = _make_table(
            "orders",
            (
                _make_column("id", is_nullable=False, ordinal_position=1),
                _make_column("note", is_nullable=True, ordinal_position=2),
            ),
        )
        out = render_snapshot_for_prompt(_make_snapshot((tbl,)))
        assert "yes" in out  # at least one nullable
        assert "no" in out   # at least one non-nullable

    def test_distinct_count_shown(self) -> None:
        tbl = _make_table(
            "orders",
            (_make_column("status", sample_values=("a", "b", "c"), distinct_sample_count=3),),
        )
        out = render_snapshot_for_prompt(_make_snapshot((tbl,)))
        assert "3" in out


class TestMultipleTables:
    def test_all_tables_rendered(self) -> None:
        t1 = _make_table("orders", (_make_column("id"),))
        t2 = _make_table("users", (_make_column("user_id"),))
        out = render_snapshot_for_prompt(_make_snapshot((t1, t2)))
        assert "orders" in out
        assert "users" in out
