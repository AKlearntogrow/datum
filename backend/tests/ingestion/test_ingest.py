"""Integration test for the full ingestion orchestrator.

Runs against the live messy_warehouse. Skips cleanly if the warehouse
is not reachable (same pattern as the connector tests).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest

from src.connectors import PostgresConnector
from src.ingestion import DatumType, SchemaSnapshot, ingest

EXPECTED_TABLES = {
    "bank_transactions",
    "invoices",
    "revenue_forecast",
    "sales_opportunities",
}

UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@pytest.fixture(scope="module")
def snapshot(messy_warehouse_url: str) -> SchemaSnapshot:
    """Produce one SchemaSnapshot per test module — reuse across tests."""
    connector = PostgresConnector(messy_warehouse_url)
    return ingest(connector)


class TestSnapshotStructure:
    def test_snapshot_is_correct_type(self, snapshot: SchemaSnapshot) -> None:
        assert isinstance(snapshot, SchemaSnapshot)

    def test_id_is_uuid(self, snapshot: SchemaSnapshot) -> None:
        assert UUID_PATTERN.match(snapshot.id) is not None

    def test_captured_at_is_utc(self, snapshot: SchemaSnapshot) -> None:
        assert isinstance(snapshot.captured_at, datetime)
        assert snapshot.captured_at.tzinfo == timezone.utc

    def test_source_database(self, snapshot: SchemaSnapshot) -> None:
        assert snapshot.source_database == "messy_warehouse"

    def test_all_expected_tables_present(self, snapshot: SchemaSnapshot) -> None:
        names = {t.ref.name for t in snapshot.tables}
        assert EXPECTED_TABLES.issubset(names), (
            f"Missing tables. Got: {names}. Expected at least: {EXPECTED_TABLES}"
        )


class TestNormalizedTypes:
    """Spot-check that known-good columns normalize to the expected DatumType.
    If any of these drift, either the generator changed, the connector changed,
    or the normalizer is wrong — all worth failing loudly."""

    def _col(self, snapshot: SchemaSnapshot, table: str, column: str):
        for t in snapshot.tables:
            if t.ref.name == table:
                for c in t.columns:
                    if c.name == column:
                        return c
        pytest.fail(f"{table}.{column} not found in snapshot")

    def test_string_column(self, snapshot: SchemaSnapshot) -> None:
        col = self._col(snapshot, "sales_opportunities", "account_name")
        assert col.datum_type == DatumType.STRING

    def test_numeric_column(self, snapshot: SchemaSnapshot) -> None:
        col = self._col(snapshot, "sales_opportunities", "amount")
        assert col.datum_type == DatumType.NUMERIC

    def test_integer_column(self, snapshot: SchemaSnapshot) -> None:
        col = self._col(snapshot, "sales_opportunities", "contract_months")
        assert col.datum_type == DatumType.INTEGER

    def test_date_column(self, snapshot: SchemaSnapshot) -> None:
        col = self._col(snapshot, "sales_opportunities", "close_date")
        assert col.datum_type == DatumType.DATE

    def test_timestamp_column(self, snapshot: SchemaSnapshot) -> None:
        col = self._col(snapshot, "sales_opportunities", "created_at")
        assert col.datum_type == DatumType.TIMESTAMP


class TestSampleCapture:
    """The LLM will key on sample values and distinct counts. Verify we're
    capturing what we claim."""

    def _table(self, snapshot: SchemaSnapshot, name: str):
        for t in snapshot.tables:
            if t.ref.name == name:
                return t
        pytest.fail(f"{name} not found")

    def test_sales_opportunities_has_samples(self, snapshot: SchemaSnapshot) -> None:
        sales = self._table(snapshot, "sales_opportunities")
        for col in sales.columns:
            assert len(col.sample_values) > 0, f"No samples for {col.name}"

    def test_enum_like_column_has_low_distinct(self, snapshot: SchemaSnapshot) -> None:
        """stage is an enum — sampling 10 rows should show very few distinct values."""
        sales = self._table(snapshot, "sales_opportunities")
        stage = next(c for c in sales.columns if c.name == "stage")
        assert stage.distinct_sample_count <= 5

    def test_id_column_has_high_distinct(self, snapshot: SchemaSnapshot) -> None:
        """opp_id is a primary key — every sample value should be unique."""
        sales = self._table(snapshot, "sales_opportunities")
        opp_id = next(c for c in sales.columns if c.name == "opp_id")
        # distinct should equal the number of sample values (all unique)
        assert opp_id.distinct_sample_count == len(opp_id.sample_values)

    def test_segment_is_orphan_dimension(self, snapshot: SchemaSnapshot) -> None:
        """`segment` should exist in revenue_forecast but nowhere else — this is
        a deliberate design from ADR 0002. Verifying keeps us honest as the demo evolves."""
        segment_tables = [
            t.ref.name for t in snapshot.tables
            if any(c.name == "segment" for c in t.columns)
        ]
        assert segment_tables == ["revenue_forecast"], (
            f"segment should only appear in revenue_forecast, found in: {segment_tables}"
        )


class TestCompositeKeys:
    def test_revenue_forecast_composite_pk(self, snapshot: SchemaSnapshot) -> None:
        forecast = next(t for t in snapshot.tables if t.ref.name == "revenue_forecast")
        assert forecast.primary_key_columns == ("forecast_month", "segment")
