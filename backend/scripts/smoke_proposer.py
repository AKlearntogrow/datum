"""End-to-end smoke test for the Proposer.

Run from project root:
    backend/.venv/Scripts/python backend/scripts/smoke_proposer.py

Connects to messy_warehouse, ingests the schema, calls the LLM,
prints the resulting ProposalSet. Will consume Anthropic API credits.
"""

from __future__ import annotations

import json
import os

from src.connectors import PostgresConnector
from src.ingestion import ingest
from src.semantic.proposer import Proposer

WAREHOUSE_URL = os.environ.get(
    "MESSY_WAREHOUSE_URL",
    "postgresql://datum:datum_dev_password@localhost:5432/messy_warehouse",
)


def main() -> None:
    print(f"Ingesting from: {WAREHOUSE_URL}")
    connector = PostgresConnector(WAREHOUSE_URL)
    snapshot = ingest(connector)
    print(f"  tables: {len(snapshot.tables)}")
    print(f"  snapshot id: {snapshot.id}")

    print()
    print("Calling Claude — this will use API credits...")
    proposer = Proposer()
    print(f"  model: {proposer.model}")
    print(f"  prompt version: {proposer.prompt_version}")

    proposals = proposer.propose(snapshot)

    print()
    print("=" * 70)
    print(f"Proposals produced: {proposals.total_proposals}")
    print("=" * 70)
    print(f"  entities           : {len(proposals.entities)}")
    print(f"  measures           : {len(proposals.measures)}")
    print(f"  dimensions         : {len(proposals.dimensions)}")
    print(f"  time_dimensions    : {len(proposals.time_dimensions)}")
    print(f"  relationships      : {len(proposals.relationships)}")
    print(f"  data_quality_flags : {len(proposals.data_quality_flags)}")
    print()

    # Print a compact summary of each proposal.
    for e in proposals.entities:
        print(f"ENTITY   ({e.confidence.value}): {e.display_name}")
        print(f"         sources: {[f'{s.table}.{s.column}' for s in e.source_columns]}")
    for m in proposals.measures:
        print(f"MEASURE  ({m.confidence.value}): {m.display_name}  [{m.aggregation.value}]")
        print(f"         sql: {m.sql_expression}")
        if m.filter_expression:
            print(f"         filter: {m.filter_expression}")
    for d in proposals.dimensions:
        print(f"DIM      ({d.confidence.value}): {d.display_name}  [{d.cardinality_hint.value}]")
        print(f"         source: {d.source_column.table}.{d.source_column.column}")
    for td in proposals.time_dimensions:
        print(f"TIME     ({td.confidence.value}): {td.display_name}  [{td.granularity_hint.value}]")
        print(f"         source: {td.source_column.table}.{td.source_column.column}")
    for r in proposals.relationships:
        print(f"REL      ({r.confidence.value}): {r.display_name}  [{r.relationship_type.value}]")
        print(f"         {r.from_table}.{r.from_column} ↔ {r.to_table}.{r.to_column}")
    for f in proposals.data_quality_flags:
        print(f"FLAG     [{f.severity.value}]: {f.title}")
        print(f"         {f.description}")
    print()

    # Save the full JSON so we can inspect it in detail.
    out_path = "proposer_smoke_output.json"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(proposals.model_dump_json(indent=2))
    print(f"Full JSON written to: {out_path}")


if __name__ == "__main__":
    main()
