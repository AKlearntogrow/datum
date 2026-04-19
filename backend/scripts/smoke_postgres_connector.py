"""Manual smoke test for PostgresConnector.

Run from project root:
    backend/.venv/Scripts/python -m backend.scripts.smoke_postgres_connector

Connects to the messy_warehouse database and exercises every protocol method.
Prints human-readable output so you can eyeball the result.

This is NOT a real test — it's a smoke test for manual verification.
Real tests live in backend/tests/connectors/ (added in Step 8b-ii).
"""

from __future__ import annotations

import os

from src.connectors import PostgresConnector, TableRef

WAREHOUSE_URL = os.environ.get(
    "MESSY_WAREHOUSE_URL",
    "postgresql://datum:datum_dev_password@localhost:5432/messy_warehouse",
)


def main() -> None:
    print(f"Connecting to: {WAREHOUSE_URL}")
    print()

    connector = PostgresConnector(WAREHOUSE_URL)

    print("=" * 70)
    print("list_tables()")
    print("=" * 70)
    tables = connector.list_tables()
    for t in tables:
        print(f"  {t.qualified}")
    print(f"\nFound {len(tables)} tables.")

    if not tables:
        print("No tables found — aborting deeper checks.")
        return

    # Pick sales_opportunities if present, else the first table.
    target = next(
        (t for t in tables if t.name == "sales_opportunities"),
        tables[0],
    )

    print()
    print("=" * 70)
    print(f"describe_table({target.qualified})")
    print("=" * 70)
    schema = connector.describe_table(target)
    print(f"  rows (estimate): {schema.row_count_estimate}")
    print(f"  primary key   : {schema.primary_key_columns}")
    print(f"  table comment : {schema.comment!r}")
    print(f"  columns ({len(schema.columns)}):")
    for col in schema.columns:
        nullable = "NULL" if col.is_nullable else "NOT NULL"
        comment = f"  -- {col.comment}" if col.comment else ""
        print(f"    {col.ordinal_position:>2}. {col.name:<25} {col.data_type:<15} {nullable}{comment}")

    print()
    print("=" * 70)
    print(f"sample_rows({target.qualified}, limit=3)")
    print("=" * 70)
    sample = connector.sample_rows(target, limit=3)
    print(f"  requested_limit: {sample.requested_limit}")
    print(f"  returned rows  : {len(sample.rows)}")
    print(f"  truncated      : {sample.truncated}")
    for i, row in enumerate(sample.rows, 1):
        print(f"  row {i}:")
        for k, v in row.items():
            print(f"    {k}: {v!r}")

    print()
    print("=" * 70)
    print("Negative test: describe_table on a nonexistent table")
    print("=" * 70)
    bogus = TableRef(database=target.database, schema="public", name="does_not_exist_xyz")
    try:
        connector.describe_table(bogus)
        print("  UNEXPECTED: no exception raised")
    except Exception as exc:
        print(f"  got expected exception: {type(exc).__name__}: {exc}")

    print()
    print("Smoke test complete.")


if __name__ == "__main__":
    main()
