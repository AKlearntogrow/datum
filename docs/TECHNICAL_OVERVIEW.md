# Datum — Technical Overview

**Status:** Early development, single-developer, no external users. Local-only demo.
**Last updated:** 2026-04-19

This document is for engineers joining the project, code reviewers, and future maintainers. It describes what exists, what doesn't, and where the current limitations are. For the product-facing view, see `PRODUCT_OVERVIEW.md`.

---

## What Datum is

An AI-assisted semantic layer for messy data warehouses. A user points Datum at their warehouse; Datum samples the schema, asks an LLM to propose a semantic model (entities, measures, dimensions, etc.), and presents those proposals in a web UI where a human reviews, approves, rejects, edits, or reopens them. Approved definitions are persisted with full audit trail and are intended to be consumed downstream by BI tools and AI agents.

The tracer-bullet product slice — connector → ingestion → LLM proposer → review UI — works end-to-end today for a single Postgres warehouse and one proposal category (entities). Other categories (measures, dimensions, time dimensions, relationships, data quality flags) are produced by the LLM but not yet persisted or rendered.

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                        Next.js UI                          │
│  (review workspace: list / approve / reject / reopen)      │
└────────────────────────────────┬───────────────────────────┘
                                 │ HTTP + JSON
┌────────────────────────────────┴───────────────────────────┐
│                      FastAPI backend                       │
│  /api/ingest       — run pipeline against a warehouse      │
│  /api/entities     — list/get/update/approve/reject/reopen │
│  /health, /health/db                                       │
└────┬───────────────────┬────────────────────┬──────────────┘
     │                   │                    │
     │ Connector         │ LLM Proposer       │ Storage
     ▼                   ▼                    ▼
┌──────────┐   ┌───────────────────┐   ┌─────────────────────┐
│ Target   │   │ Claude Sonnet 4.5 │   │ Postgres 16         │
│ warehouse│   │ (v0 prompt)       │   │ (+ pgvector 0.8.2)  │
│ (Postgres)│   └───────────────────┘   │ 6 app tables        │
└──────────┘                            └─────────────────────┘
```

**Everything runs locally** in Docker or on the developer's machine. There is no cloud deployment, no auth, no shared state.

---

## Stack

**Backend** — Python 3.11+, FastAPI, SQLAlchemy 2.0 (DeclarativeBase + `Mapped[T]`), pydantic v2, psycopg v3, Alembic. Testing via pytest.

**Frontend** — Next.js 16.2.4 (Turbopack), TypeScript, Tailwind. App Router. No component library — direct Tailwind.

**LLM** — Claude Sonnet 4.5 via Anthropic SDK with prompt caching on the system prompt. Model id: `claude-sonnet-4-5`. Prompt version: `v0`.

**App database** — Postgres 16 in Docker with pgvector extension (unused so far; reserved for future embedding-based features).

**Dev warehouse** — Second Postgres database in the same container, named `messy_warehouse`, seeded with ~156 rows of deliberately-realistic garbage (spelling variants, NULL contract_months, uninvoiced Closed Won deals, unattributed refunds, and a LTV formula with an intentional double-annualization bug).

---

## Repo layout

```
datum/
├── backend/
│   ├── src/
│   │   ├── api/              — FastAPI routers (entities.py, ingest.py, errors.py)
│   │   ├── connectors/       — Warehouse connector protocol + Postgres impl
│   │   ├── core/             — Settings (pydantic-settings), DB session
│   │   ├── ingestion/        — Snapshot builder + structural comparison
│   │   ├── models/           — SQLAlchemy ORM models
│   │   ├── schemas/          — Pydantic request/response models
│   │   ├── semantic/         — Proposer (LLM call), Pydantic proposal schemas, prompt templates
│   │   └── storage/          — Session-owning read/write functions
│   ├── tests/                — pytest, 115+ passing
│   ├── alembic/              — Migrations
│   └── scripts/              — Smoke tests against real Claude (cost ~$0.05 each)
├── frontend/
│   └── src/
│       ├── app/              — Next.js pages
│       ├── components/       — EntityCard, IngestButton
│       └── lib/              — Typed API client
├── synthetic_data/           — messy_warehouse generator
└── docs/decisions/           — 9 ADRs (architecture decision records)
```

---

## Pipeline

**POST /api/ingest** runs the full pipeline synchronously:

1. Opens a connector against the warehouse URL in the request
2. Walks schemas, samples 10 rows per table, builds an immutable `SchemaSnapshot` dataclass
3. **Structural comparison** — if the new snapshot is structurally identical to the last one for this source database AND the prompt version matches, skips the LLM call and returns a "no-op" response (ADR 0008)
4. Otherwise: persists the snapshot (3 shredded tables — snapshots, tables, columns), renders Markdown for the LLM prompt, calls Claude, parses the JSON response through Pydantic schemas
5. Persists entity proposals as `EntityDefinition` rows with `status=proposed`, `proposed_by=system`, and links to the originating snapshot columns
6. Returns counts for all six proposal categories

Typical timings: ~1 second for connect + sample, ~20 seconds for the LLM call, ~100ms for persistence. Skip path returns in ~100ms.

---

## Data model

Six tables in the `datum` database:

- `schema_snapshots`, `snapshot_tables`, `snapshot_columns` — immutable, shredded capture of the warehouse shape at one point in time
- `entity_definitions` — the first (and currently only) persisted proposal category; every row carries full lifecycle metadata (status, proposed_by, approved_by, rejected_by, reopened_at, supersedes_id, parent_id, prompt_version, model, source_snapshot_id) per ADR 0006
- `entity_source_columns` — link from entity definitions to specific `snapshot_columns` (not free-text table/column strings, so schema-change impact is queryable)
- `alembic_version`

Five other proposal categories (measures, dimensions, time_dimensions, relationships, data_quality_flags) have Pydantic shapes defined and are produced by the LLM, but no ORM models or persistence logic yet. Each will need its own table(s) following the same lifecycle pattern.

---

## Governance model (ADR 0003, 0006)

- LLM proposes, human approves. No auto-approval, ever.
- Every definition has a status: `proposed`, `approved`, `rejected`, `superseded`.
- Rejections and supersessions are never deleted; they remain as audit trail.
- Editing a `proposed` definition mutates it in place (revisions are cheap). Replacing an `approved` definition creates a new row with `supersedes_id` pointing at the old one (supersession is a governance event).
- User-authored definitions (not built yet) will use the same tables, distinguished only by `proposed_by=user:<id>`.
- Reopening an approved or rejected definition (ADR 0007) moves it back to `proposed` but preserves the prior approval/rejection timestamps for audit.

---

## Connector architecture (ADR 0004)

Connectors are thin. They do only three things: `list_tables()`, `describe_table()`, `sample_rows()`. All normalization, type mapping, and snapshot construction happens in the ingestion layer, not the connector. This means adding BigQuery or Snowflake is a matter of implementing the three methods; no downstream code changes required.

Datum types are a closed enum (`STRING`, `INTEGER`, `NUMERIC`, `BOOLEAN`, `DATE`, `TIMESTAMP`, `JSON`, `OTHER`). Native Postgres/BigQuery/Snowflake types map into this enum for cross-warehouse consistency in the prompt.

---

## Proposer (ADR 0005)

The system prompt (`backend/src/semantic/prompts/system.md`, ~140 lines) asks Claude to produce six categories of proposals against a rendered Markdown description of the warehouse. Borrows vocabulary from Cube (measure/dimension split). Tuned through five iterative rounds of schema-loosening as real LLM outputs revealed where our Pydantic schemas were too strict:

1. Markdown fence wrapping — parser now strips wrappers
2. Token truncation — `max_output_tokens` raised from 8192 to 16384
3. Null `to_column` on `unlinked_dimension` — schema relaxed
4. Integer sample_values + empty affected_columns — schema loosened
5. `unlinked_dimension` with populated target — validator accepts as informational hint

Schema-evolution principle, documented in ADR 0005: start permissive, tighten via observation. Strictness catches unknown enum values; it *doesn't* usefully catch legitimate LLM outputs we didn't anticipate.

Real Claude output is captured in `backend/tests/fixtures/proposals/messy_warehouse_v0.json` (51 proposals) and used as a test fixture so regression tests run in milliseconds without API cost.

---

## What's deliberately not built yet

Documented in ADRs, not forgotten:

- **Authentication.** No login, no users, no sessions. Everyone is `local_user`. ADR 0007.
- **Persistence of measures/dimensions/etc.** Only entities are stored. Six slices planned, entities is one. ADR 0007.
- **User-authored definitions from the UI.** Data model supports them (`proposed_by=user:<id>`); UI doesn't expose the authoring flow yet. ADR 0006.
- **Schema evolution handling.** New snapshots don't yet compare against old snapshots to flag broken definitions. The "compatibility report" from ADR 0006 is a v1 concern.
- **Data source and scope management.** Hardcoded warehouse URL today. ADR 0009 designed; implementation is the next step.
- **Cube/dbt export.** Approved definitions sit in Datum's DB with no downstream pathway.
- **Query API.** No way for external tools to query approved definitions.
- **Non-Postgres connectors.** BigQuery/Snowflake/Redshift will come later; the connector architecture is ready.
- **Encryption at rest.** v0 credentials are stored in plain text. Required before any non-local deployment.

---

## Known limitations (non-bugs)

- **Long LLM calls hold the uvicorn worker.** 20+ seconds of synchronous work per Ingest. Fine for single-user demo, needs a job queue for production.
- **Skip-check loads the previous snapshot on every Ingest.** Small database query. Will want a hash column or cache at scale.
- **Sample size is fixed at 10 rows.** Configurable per-connector eventually.
- **Prompt prompts the LLM to observe what it sees.** Sampling artifacts occasionally become fake data quality flags ("all 10 sampled invoices are Paid"). Prompt quality pass planned.
- **"Force re-run" not available.** If a user wants to bypass the skip-on-unchanged logic, they currently can't.

---

## ADRs

Canonical design record. Read in order for full context:

- `0001-initial-tech-stack.md`
- `0002-synthetic-warehouse-design.md`
- `0003-semantic-layer-governance-model.md`
- `0004-connector-architecture.md`
- `0005-semantic-proposal-prompt.md`
- `0006-definitions-lifecycle-and-user-authoring.md`
- `0007-ui-scope-and-build-order.md`
- `0008-skip-ingestion-when-unchanged.md`
- `0009-data-sources-scopes-and-admin-section.md`

---

## Tests and tooling

- **115+ tests**, pytest, ~2 seconds full run. Mix of unit (renderer, proposal parse, comparison) and integration (connector-against-real-Postgres, storage round-trip).
- **Zero network cost for tests.** The Proposer's unit tests use a fake Anthropic client that returns the captured fixture.
- **Smoke scripts** (`backend/scripts/smoke_*.py`) exercise the real pipeline end-to-end. Explicitly opt-in because they cost money.
- **Lint/type:** ruff for Python, TypeScript strict mode for frontend.
- **Migrations:** Alembic, autogenerate from the ORM models. Every migration reviewed before apply.

---

## Running locally

```bash
# Database
docker compose up -d

# Backend
cd backend
python -m venv .venv
.venv/Scripts/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn src.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Visit http://localhost:3000. Click "Run ingestion on messy_warehouse" to trigger the full pipeline.

Requires: `ANTHROPIC_API_KEY` in `backend/.env`.
