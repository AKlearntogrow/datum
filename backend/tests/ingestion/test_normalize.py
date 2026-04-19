"""Unit tests for the type normalization and sample extraction helpers.

These are pure functions — no database, no I/O. They should run in
milliseconds and never be skipped.
"""

from __future__ import annotations

import pytest

from src.connectors.types import RawColumn
from src.ingestion.service import _extract_column_samples, _normalize_datum_type
from src.ingestion.types import DatumType


class TestNormalizeDatumType:
    """Every warehouse-native type must map to a known DatumType, or UNKNOWN
    if we genuinely don't recognize it. Add cases here when adding a connector."""

    # Postgres
    @pytest.mark.parametrize("native,expected", [
        ("character varying", DatumType.STRING),
        ("varchar(50)", DatumType.STRING),
        ("text", DatumType.STRING),
        ("uuid", DatumType.STRING),
        ("smallint", DatumType.INTEGER),
        ("integer", DatumType.INTEGER),
        ("bigint", DatumType.INTEGER),
        ("serial", DatumType.INTEGER),
        ("numeric", DatumType.NUMERIC),
        ("numeric(12,2)", DatumType.NUMERIC),
        ("decimal", DatumType.NUMERIC),
        ("real", DatumType.NUMERIC),
        ("double precision", DatumType.NUMERIC),
        ("money", DatumType.NUMERIC),
        ("boolean", DatumType.BOOLEAN),
        ("bool", DatumType.BOOLEAN),
        ("date", DatumType.DATE),
        ("timestamp", DatumType.TIMESTAMP),
        ("timestamp without time zone", DatumType.TIMESTAMP),
        ("timestamp with time zone", DatumType.TIMESTAMP),
        ("json", DatumType.JSON),
        ("jsonb", DatumType.JSON),
    ])
    def test_postgres_types(self, native: str, expected: DatumType) -> None:
        assert _normalize_datum_type(native) == expected

    # BigQuery / Snowflake forward-compatibility — these should also map correctly
    # even though we haven't written those connectors yet. Catches the bug where
    # someone adds a connector that returns types we don't normalize.
    @pytest.mark.parametrize("native,expected", [
        ("STRING", DatumType.STRING),           # BQ
        ("INT64", DatumType.INTEGER),           # BQ — matches via "int"
        ("FLOAT64", DatumType.NUMERIC),         # BQ — matches via "float"
        ("DATETIME", DatumType.TIMESTAMP),      # BQ
        ("VARCHAR2(255)", DatumType.STRING),    # Oracle/Snowflake
        ("NUMBER", DatumType.NUMERIC),          # Snowflake — matches via "number"? NO — intentional miss
    ])
    def test_other_warehouse_types(self, native: str, expected: DatumType) -> None:
        # This test documents BOTH passes and expected misses. If the assertion fails,
        # it means we should extend _TYPE_MAPPING — not that the test is wrong.
        result = _normalize_datum_type(native)
        # "NUMBER" is not yet in our mapping — we expect UNKNOWN, not NUMERIC
        if native == "NUMBER":
            assert result == DatumType.UNKNOWN, (
                "Snowflake NUMBER should be UNKNOWN until we add Snowflake support. "
                "If this fails because we added it, update the test to expect NUMERIC."
            )
        else:
            assert result == expected

    def test_unknown_type_returns_unknown(self) -> None:
        assert _normalize_datum_type("geometry") == DatumType.UNKNOWN
        assert _normalize_datum_type("hstore") == DatumType.UNKNOWN
        assert _normalize_datum_type("") == DatumType.UNKNOWN

    def test_case_insensitive(self) -> None:
        assert _normalize_datum_type("INTEGER") == DatumType.INTEGER
        assert _normalize_datum_type("Varchar") == DatumType.STRING
        assert _normalize_datum_type("BoOlEaN") == DatumType.BOOLEAN

    def test_whitespace_tolerant(self) -> None:
        assert _normalize_datum_type("  integer  ") == DatumType.INTEGER


class TestExtractColumnSamples:
    """Sample extraction reads the same column across a list of row dicts
    and returns a tuple of values plus a distinct count."""

    def _col(self, name: str) -> RawColumn:
        """Minimal RawColumn for tests — only `name` matters for this helper."""
        return RawColumn(
            name=name,
            data_type="varchar",
            is_nullable=True,
            ordinal_position=1,
        )

    def test_basic_extraction(self) -> None:
        col = self._col("status")
        rows = [{"status": "open"}, {"status": "closed"}, {"status": "open"}]
        values, distinct = _extract_column_samples(col, rows)
        assert values == ("open", "closed", "open")
        assert distinct == 2

    def test_respects_max_values(self) -> None:
        col = self._col("id")
        rows = [{"id": i} for i in range(100)]
        values, distinct = _extract_column_samples(col, rows, max_values=5)
        assert len(values) == 5
        assert values == (0, 1, 2, 3, 4)
        # But distinct count reflects ALL rows, not just the kept values
        assert distinct == 100

    def test_includes_nulls(self) -> None:
        """NULLs are informative — high NULL rate signals data quality issues."""
        col = self._col("contract_months")
        rows = [{"contract_months": 12}, {"contract_months": None}, {"contract_months": 24}]
        values, distinct = _extract_column_samples(col, rows)
        assert None in values
        assert distinct == 3  # 12, None, 24

    def test_missing_column_in_row_is_skipped(self) -> None:
        col = self._col("amount")
        rows = [{"amount": 100}, {"other": "x"}, {"amount": 200}]
        values, distinct = _extract_column_samples(col, rows)
        assert values == (100, 200)
        assert distinct == 2

    def test_empty_rows(self) -> None:
        col = self._col("x")
        values, distinct = _extract_column_samples(col, [])
        assert values == ()
        assert distinct == 0

    def test_unhashable_values_fallback(self) -> None:
        """Dicts (e.g., from JSONB columns) are unhashable. The helper
        should not crash — it falls back to using repr() for distinct counting."""
        col = self._col("meta")
        rows = [{"meta": {"a": 1}}, {"meta": {"a": 1}}, {"meta": {"b": 2}}]
        values, distinct = _extract_column_samples(col, rows)
        assert len(values) == 3
        # Distinct via repr: {"a": 1} and {"a": 1} have same repr, {"b": 2} different
        assert distinct == 2
