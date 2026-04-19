"""Manual smoke test for the ingestion orchestrator.

Run from project root:
    backend/.venv/Scripts/python backend/scripts/smoke_ingest.py

Points PostgresConnector at messy_warehouse, runs ingest(), and prints
the resulting SchemaSnapshot in human-readable form.
"""

from __future__ import annotations

import os

from src.connectors import PostgresConnector
from src.ingestion import ingest

WAREHOUSE_URL = os.environ.get(
    "MESSY_WAREHOUSE_URL",
    "postgresql://datum:datum_dev_password@localhost:5432/messy_warehouse",
)


def main() -> None:
    print(f"Ingesting from: {WAREHOUSE_URL}")
    print()

    connector = PostgresConnector(WAREHOUSE_URL)
    snapshot = ingest(connector)

    print("=" * 70)
    print(f"Snapshot id     : {snapshot.id}")
    print(f"Captured at     : {snapshot.captured_at.isoformat()}")
    print(f"Source database : {snapshot.source_database}")
    print(f"Tables          : {len(snapshot.tables)}")
    print("=" * 70)

    for table in snapshot.tables:
        print()
        print(f"TABLE: {table.ref.qualified}")
        print(f"  primary key   : {table.primary_key_columns}")
        print(f"  rows estimate : {table.row_count_estimate}")
        print(f"  sample rows   : {table.sample_rows_returned} (truncated={table.sample_truncated})")
        print(f"  columns       : {len(table.columns)}")
        for col in table.columns:
            null = "NULL" if col.is_nullable else "NOT NULL"
            samples_display = ", ".join(
                repr(v) for v in col.sample_values[:3]
            )
            if len(col.sample_values) > 3:
                samples_display += ", ..."
            print(
                f"    {col.ordinal_position:>2}. {col.name:<22} "
                f"{col.datum_type.value:<9} {null:<8} "
                f"distinct={col.distinct_sample_count:<3} "
                f"samples=[{samples_display}]"
            )

    print()
    print("Ingestion complete.")


if __name__ == "__main__":
    main()
