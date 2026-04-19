"""HTTP route for running the full ingestion pipeline.

POST /api/ingest runs: connect -> ingest -> propose -> persist (entities
only in v0). Synchronous — the client waits for the LLM call. We'll make
it async with a job queue in v1.

The other proposal categories (measures, dimensions, etc.) are generated
by the LLM but not yet persisted; they'll be added in later slices per
ADR 0007's tracer-bullet plan.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.connectors import PostgresConnector
from src.core.db import get_db
from src.ingestion import ingest
from src.schemas.ingest import IngestRequest, IngestResponse
from src.semantic.proposer import Proposer
from src.storage import persist_entity_proposals, persist_snapshot

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
def run_ingest(body: IngestRequest, db: Session = Depends(get_db)) -> IngestResponse:
    """Run one full ingestion pipeline against the given warehouse.

    Steps:
    1. Connect to the warehouse (Postgres only for v0)
    2. Walk schemas, sample columns, build a SchemaSnapshot
    3. Persist the snapshot in the app database
    4. Call Claude via the Proposer to produce a ProposalSet
    5. Persist the entity proposals (only entities in v0)

    Returns counts for everything proposed and everything persisted.
    """
    connector = PostgresConnector(body.warehouse_url)
    snapshot = ingest(connector)

    persist_snapshot(db, snapshot)
    db.flush()

    proposer = Proposer()
    proposals = proposer.propose(snapshot)

    new_entity_ids = persist_entity_proposals(
        db,
        snapshot_id=snapshot.id,
        proposals=proposals.entities,
        prompt_version=proposer.prompt_version,
        model=proposer.model,
    )

    db.commit()

    columns_count = sum(len(t.columns) for t in snapshot.tables)

    return IngestResponse(
        snapshot_id=snapshot.id,
        source_database=snapshot.source_database,
        tables_ingested=len(snapshot.tables),
        columns_ingested=columns_count,
        entities_proposed=len(proposals.entities),
        measures_proposed=len(proposals.measures),
        dimensions_proposed=len(proposals.dimensions),
        time_dimensions_proposed=len(proposals.time_dimensions),
        relationships_proposed=len(proposals.relationships),
        data_quality_flags_proposed=len(proposals.data_quality_flags),
        entities_persisted=len(new_entity_ids),
    )
