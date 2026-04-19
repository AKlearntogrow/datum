"""Integration tests for PostgresConnector.

Runs against the live messy_warehouse database populated by
synthetic_data/generate.py. Skips cleanly if the warehouse is not reachable.

These are integration tests by design — the connector's entire job is
talking to Postgres, so mocking the driver would prove nothing.
"""

from __future__ import annotations

import pytest

from src.connectors import (
    PostgresConnector,
    RawColumn,
    RawTableSchema,
    SampleRows,
    TableNotFound,
    TableRef,
)

# The four tables defined in ADR 0002. If this list drifts, the ADR is wrong
# or the schema is wrong — either way, tests should fail and force a review.
EXPECTED_TABLES = {
    "bank_transactions",
    "invoices",
    "revenue_forecast",
    "sales_opportunities",
}


@pytest.fixture(scope="module")
def connector(messy_warehouse_url: str) -> PostgresConnector:
    return PostgresConnector(messy_warehouse_url)


# --------------------------------------------------------------
# list_tables
# --------------------------------------------------------------

class TestListTables:
    def test_returns_all_expected_tables(self, connector: PostgresConnector) -> None:
        tables = connector.list_tables()
        names = {t.name for t in tables}
        assert EXPECTED_TABLES.issubset(names), (
            f"Missing expected tables. Got: {names}. Expected at least: {EXPECTED_TABLES}"
        )

    def test_excludes_system_schemas(self, connector: PostgresConnector) -> None:
        tables = connector.list_tables()
        schemas = {t.schema for t in tables}
        assert "pg_catalog" not in schemas
        assert "information_schema" not in schemas

    def test_all_tables_in_same_database(self, connector: PostgresConnector) -> None:
        tables = connector.list_tables()
        databases = {t.database for t in tables}
        assert databases == {"messy_warehouse"}, f"Unexpected databases: {databases}"

    def test_table_refs_are_frozen(self, connector: PostgresConnector) -> None:
        """TableRef is declared frozen=True. Confirm we cannot mutate it."""
        tables = connector.list_tables()
        if not tables:
            pytest.skip("No tables to test immutability against")
        with pytest.raises(Exception):
            tables[0].name = "hacked"  # type: ignore[misc]


# --------------------------------------------------------------
# describe_table
# --------------------------------------------------------------

class TestDescribeTable:
    @pytest.fixture
    def sales_ref(self, connector: PostgresConnector) -> TableRef:
        tables = connector.list_tables()
        for t in tables:
            if t.name == "sales_opportunities":
                return t
        pytest.fail("sales_opportunities not found")

    def test_returns_correct_type(
        self, connector: PostgresConnector, sales_ref: TableRef
    ) -> None:
        schema = connector.describe_table(sales_ref)
        assert isinstance(schema, RawTableSchema)
        assert schema.ref == sales_ref

    def test_returns_all_columns(
        self, connector: PostgresConnector, sales_ref: TableRef
    ) -> None:
        schema = connector.describe_table(sales_ref)
        column_names = {c.name for c in schema.columns}
        expected = {
            "opp_id", "account_name", "owner_email", "stage",
            "amount", "contract_months", "arr_committed",
            "close_date", "created_at",
        }
        assert column_names == expected

    def test_columns_are_ordered_by_position(
        self, connector: PostgresConnector, sales_ref: TableRef
    ) -> None:
        schema = connector.describe_table(sales_ref)
        positions = [c.ordinal_position for c in schema.columns]
        assert positions == sorted(positions)
        assert positions[0] == 1

    def test_nullability_detection(
        self, connector: PostgresConnector, sales_ref: TableRef
    ) -> None:
        schema = connector.describe_table(sales_ref)
        by_name = {c.name: c for c in schema.columns}
        assert by_name["opp_id"].is_nullable is False
        assert by_name["contract_months"].is_nullable is True
        assert by_name["arr_committed"].is_nullable is True

    def test_primary_key_detected(
        self, connector: PostgresConnector, sales_ref: TableRef
    ) -> None:
        schema = connector.describe_table(sales_ref)
        assert schema.primary_key_columns == ["opp_id"]

    def test_composite_primary_key(self, connector: PostgresConnector) -> None:
        """revenue_forecast has a composite PK (forecast_month, segment).
        Verify both columns are captured, in order."""
        tables = connector.list_tables()
        forecast = next(t for t in tables if t.name == "revenue_forecast")
        schema = connector.describe_table(forecast)
        assert schema.primary_key_columns == ["forecast_month", "segment"]

    def test_columns_are_raw_columns(
        self, connector: PostgresConnector, sales_ref: TableRef
    ) -> None:
        schema = connector.describe_table(sales_ref)
        assert all(isinstance(c, RawColumn) for c in schema.columns)

    def test_nonexistent_table_raises_table_not_found(
        self, connector: PostgresConnector
    ) -> None:
        bogus = TableRef(database="messy_warehouse", schema="public", name="does_not_exist_xyz")
        with pytest.raises(TableNotFound):
            connector.describe_table(bogus)


# --------------------------------------------------------------
# sample_rows
# --------------------------------------------------------------

class TestSampleRows:
    @pytest.fixture
    def sales_ref(self, connector: PostgresConnector) -> TableRef:
        tables = connector.list_tables()
        return next(t for t in tables if t.name == "sales_opportunities")

    def test_returns_correct_type(
        self, connector: PostgresConnector, sales_ref: TableRef
    ) -> None:
        sample = connector.sample_rows(sales_ref, limit=5)
        assert isinstance(sample, SampleRows)
        assert sample.ref == sales_ref
        assert sample.requested_limit == 5

    def test_respects_limit(
        self, connector: PostgresConnector, sales_ref: TableRef
    ) -> None:
        sample = connector.sample_rows(sales_ref, limit=3)
        assert len(sample.rows) <= 3

    def test_returns_rows_as_dicts(
        self, connector: PostgresConnector, sales_ref: TableRef
    ) -> None:
        sample = connector.sample_rows(sales_ref, limit=2)
        for row in sample.rows:
            assert isinstance(row, dict)
            assert "opp_id" in row

    def test_truncated_flag_when_table_larger_than_sample(
        self, connector: PostgresConnector, sales_ref: TableRef
    ) -> None:
        """sales_opportunities has 40 rows; sampling 3 should set truncated=True."""
        sample = connector.sample_rows(sales_ref, limit=3)
        assert sample.truncated is True

    def test_limit_zero_raises(
        self, connector: PostgresConnector, sales_ref: TableRef
    ) -> None:
        with pytest.raises(ValueError):
            connector.sample_rows(sales_ref, limit=0)

    def test_nonexistent_table_raises(self, connector: PostgresConnector) -> None:
        bogus = TableRef(database="messy_warehouse", schema="public", name="does_not_exist_xyz")
        with pytest.raises(TableNotFound):
            connector.sample_rows(bogus, limit=3)
