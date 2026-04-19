"""HTTP route for running the full ingestion pipeline.

Skips the LLM call and returns early when the warehouse is structurally
identical to the last run (ADR 0008).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.connectors import PostgresConnector
from src.core.db import get_db
from src.ingestion import ingest
from src.ingestion.compare import snapshots_are_structurally_equivalent
from src.schemas.ingest import IngestRequest, IngestResponse
from src.semantic.proposer import PROMPT_VERSION, Proposer
from src.storage import (
    load_most_recent_snapshot,
    persist_entity_proposals,
    persist_snapshot,
)

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
def run_ingest(body: IngestRequest, db: Session = Depends(get_db)) -> IngestResponse:
    """Run one full ingestion pipeline against the given warehouse.

    Skips the LLM call if the warehouse is structurally identical to the
    last run AND the current prompt version matches — see ADR 0008.
    """
    connector = PostgresConnector(body.warehouse_url)
    new_snapshot = ingest(connector)

    # Check whether we should skip.
    previous = load_most_recent_snapshot(db, new_snapshot.source_database)
    if previous is not None:
        previous_snapshot, previous_prompt_version = previous
        structurally_equal = snapshots_are_structurally_equivalent(
            previous_snapshot, new_snapshot
        )
        prompt_equal = previous_prompt_version == PROMPT_VERSION

        if structurally_equal and prompt_equal:
            return IngestResponse(
                skipped=True,
                reason="warehouse structurally unchanged since last run",
                last_snapshot_id=previous_snapshot.id,
                last_snapshot_captured_at=previous_snapshot.captured_at,
                source_database=new_snapshot.source_database,
            )

    # Proceed with a full run.
    persist_snapshot(db, new_snapshot)
    db.flush()

    proposer = Proposer()
    proposals = proposer.propose(new_snapshot)

    new_entity_ids = persist_entity_proposals(
        db,
        snapshot_id=new_snapshot.id,
        proposals=proposals.entities,
        prompt_version=proposer.prompt_version,
        model=proposer.model,
    )

    db.commit()

    columns_count = sum(len(t.columns) for t in new_snapshot.tables)

    return IngestResponse(
        skipped=False,
        snapshot_id=new_snapshot.id,
        source_database=new_snapshot.source_database,
        tables_ingested=len(new_snapshot.tables),
        columns_ingested=columns_count,
        entities_proposed=len(proposals.entities),
        measures_proposed=len(proposals.measures),
        dimensions_proposed=len(proposals.dimensions),
        time_dimensions_proposed=len(proposals.time_dimensions),
        relationships_proposed=len(proposals.relationships),
        data_quality_flags_proposed=len(proposals.data_quality_flags),
        entities_persisted=len(new_entity_ids),
    )
