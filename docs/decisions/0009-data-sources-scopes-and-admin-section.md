# ADR 0009: Data Sources, Scopes, and the Admin Section

**Date:** 2026-04-19
**Status:** Accepted

## Context

Datum's current answer to "which warehouse do you analyze?" is embarrassing: a hardcoded connection string in the frontend pointing at our synthetic `messy_warehouse`. That works for a self-contained demo; it collapses the moment a real user shows up.

Real warehouses — BigQuery, Snowflake, a company's production Postgres — are cluttered. A typical company BigQuery might have 40+ schemas mixing engineering telemetry, product analytics, marketing data, sales data, finance data, and legacy dumps nobody has the authority to delete. Pointing Datum at such a warehouse without scoping would drown the LLM in irrelevant tables, produce hundreds of meaningless proposals, and burn API credits.

Before Datum can credibly claim to work against real data, it needs two new concepts the product currently lacks:

1. **Data Sources** — persistent, named warehouse connections managed in an Admin section
2. **Scopes** — saved selections of which schemas/tables within a data source to actually analyze

Every snapshot, every proposal, and every approved definition going forward will reference a Scope. This makes the scope the organizing unit of the semantic layer, not just the ingestion pipeline.

## Decisions

### Data Source

A Data Source is a named, persistent warehouse connection. It has:

- A human-readable name (e.g., "Acme Company BigQuery")
- A warehouse type (v0: `postgres` only; v1+: `bigquery`, `snowflake`, `redshift`)
- Connection credentials (connection URL or structured fields)
- Audit fields: created_by, created_at
- Optional description

Multiple scopes can point at the same data source. Connecting the same warehouse twice is legitimate (e.g., for two different organizational views).

### Scope

A Scope is a saved selection within a Data Source. It has:

- A human-readable name (e.g., "Finance + Sales")
- A reference to a Data Source (FK)
- A list of schemas to include (e.g., `["sales_cloud", "finance_mart"]`)
- Optional excluded tables within those schemas (e.g., `["sales_cloud.audit_log"]`)
- Audit fields: created_by, created_at

Scopes are immutable in their analysis intent but editable in their selection. If a user changes a scope from "sales only" to "sales + marketing", the next ingestion sees the new selection; prior snapshots and definitions remain linked to the scope but reflect the state at the time they were captured.

### Every semantic artifact carries scope_id

This is the design decision that makes scopes the organizing unit:

- `schema_snapshots` gets a `scope_id` column (FK to scopes)
- `entity_definitions` gets a `scope_id` column (and measures, dimensions, etc. when added)
- API endpoints that list definitions accept a `scope_id` filter
- The UI can show "Finance semantic layer" vs "Product semantic layer" as distinct views over the same warehouse

This symmetry matters. Without it, scopes are just pre-flight filters; with it, scopes become first-class product objects around which governance, approval, and export all organize.

### Schema selection UI for v0: checkboxes

When a user adds a new Data Source and creates a Scope, Datum connects to the warehouse and enumerates its schemas (and optionally row counts and table counts per schema). The UI presents these as a checkbox list, sorted by schema name. The user ticks the schemas they want included, optionally unchecks individual tables within each, and saves the Scope.

This is deliberately dumb. It works, it's testable, and it respects the user's judgment rather than trying to be clever about what "business-relevant" means.

v1+ will add smart pre-selection: a lightweight LLM pass over just the schema names that suggests "these three look like business-domain data; these forty look like infrastructure/telemetry." The user still confirms. We defer this because over-eager LLM suggestion at the scoping step is where trust dies fastest — if Datum decides which schemas matter before the user has seen any proposals, and it picks the wrong ones, the user has no basis to correct it.

### Admin section

Data Source and Scope management is administrative work, not review work. Separating it reflects the eventual reality that the person who connects the warehouse (a data engineer or IT admin) is often not the person who approves metric definitions (a CFO or RevOps lead).

Admin lives at `/admin/*` in the frontend. The current main page stays at `/` and remains the review workspace. The two have distinct navigation and distinct purposes.

**Admin is not access-controlled in v0.** There is no login, no admin role, no gatekeeping. Anyone with the URL can configure data sources. This is honest: we don't pretend to have access control we haven't built. When auth lands in v1, `/admin/*` becomes the natural gate point.

We do NOT build fake access gates in v0 (e.g., a cosmetic "admin mode toggle"). Fake gates are worse than no gates — they confuse non-technical users and read as bullshit to engineers.

### Credentials storage for v0: plain text + visible warning

Connection URLs are stored in plain text in the `data_sources` table. The UI displays a prominent warning on every data source page: "⚠️ Credentials are stored unencrypted in this local database. Do not use this instance for credentials you cannot afford to leak."

This is blunt and correct. Users who understand the warning will use throwaway credentials during evaluation; users who don't understand it are still informed. Hiding the limitation would be worse.

**v1 must encrypt at rest before any deployment outside the developer's machine.** Candidate approach: `cryptography.fernet` with a key loaded from an environment variable. The ADR that addresses this will be ADR 00XX when we get there.

### No auto-seeding

Even our development `messy_warehouse` gets added as a user-created Data Source through the real UX flow. We do not short-circuit that step even though we're the only users.

Reason: dogfooding. If the add-source flow has friction, we feel it immediately. A one-click "Demo Mode" seed button would let us skip our own UX bugs, which is exactly what we don't want to do.

### The existing hardcoded pipeline

Our current `POST /api/ingest` accepts a `warehouse_url` in the request body and pointed at a single hardcoded Postgres URL from the frontend. Under this ADR:

- `POST /api/ingest` no longer takes a `warehouse_url`
- It takes a `scope_id` instead
- The endpoint resolves the scope → data source → credentials → schema list
- It connects, snapshots only the included schemas/tables, and proceeds as before

Existing ingestion tests either migrate to reference a test scope or use the internal ingestion service directly (no HTTP).

## Data model

Two new tables:

**data_sources**
id                uuid primary key
name              text not null
warehouse_type    text not null    -- 'postgres' for v0
connection_url    text not null    -- plain text in v0; encrypted in v1
description       text
created_by        text not null    -- 'local_user' in v0
created_at        timestamptz not null

**scopes**
id                uuid primary key
data_source_id    uuid not null references data_sources(id)
name              text not null
included_schemas  text not null    -- JSON array
excluded_tables   text             -- JSON array, optional
description       text
created_by        text not null
created_at        timestamptz not null

Existing tables get new nullable columns (to be backfilled or defaulted during migration):

- `schema_snapshots.scope_id` — FK to `scopes.id`
- `entity_definitions.scope_id` — FK to `scopes.id`
- (And measures/dimensions/etc. when added)

## API surface

New endpoints, all under `/api/admin/*` to mirror the UI structure:

- `POST /api/admin/data-sources` — create a data source (connects to validate)
- `GET /api/admin/data-sources` — list all data sources
- `GET /api/admin/data-sources/{id}` — get one data source
- `DELETE /api/admin/data-sources/{id}` — remove a data source (fails if scopes reference it)
- `POST /api/admin/data-sources/{id}/schemas` — list schemas/tables visible with these credentials (for the scope-creation UI)
- `POST /api/admin/scopes` — create a scope
- `GET /api/admin/scopes` — list all scopes
- `GET /api/admin/scopes/{id}` — get one scope
- `PATCH /api/admin/scopes/{id}` — update included/excluded selections
- `DELETE /api/admin/scopes/{id}` — remove a scope (fails if definitions reference it)

Modified endpoint:

- `POST /api/ingest` now takes `{"scope_id": "..."}` instead of `{"warehouse_url": "..."}`

Modified list endpoints (eventually):

- `GET /api/entities` gains an optional `?scope_id=` filter

## Frontend routing

- `/` — Review workspace (current page, renamed in nav)
- `/admin` — Admin landing / dashboard
- `/admin/data-sources` — list data sources, add new
- `/admin/data-sources/[id]` — edit one, view its scopes
- `/admin/scopes` — list scopes
- `/admin/scopes/new` — create a new scope against a chosen data source
- `/admin/scopes/[id]` — view/edit one scope

The review page gains a scope selector at the top — the user picks "which scope am I reviewing right now" — and the entity list filters accordingly.

## Implementation plan

- **11a**: Data model — Alembic migrations, ORM models for `data_sources` and `scopes`, add `scope_id` columns to existing tables
- **11b**: Storage functions for sources and scopes, validator that a scope's `included_schemas` are a subset of what the data source actually exposes
- **11c**: Admin API endpoints
- **11d**: Admin UI — add source, list sources, create scope (with checkbox schema picker), list scopes
- **11e**: Update `POST /api/ingest` to use `scope_id`, update frontend to pick scope before running
- **11f**: Migrate the review page — scope selector at top, list filters by scope
- **11g**: Replace the hardcoded `messy_warehouse` dev flow with instructions to add it as a real data source
- **11h**: Expand the synthetic warehouse — 30-50 tables across sales, finance, product, engineering, legacy — to stress-test the scoping UX

Each step is its own commit at minimum, with verification before moving to the next.

## Consequences

**Positive:**
- Datum can be pointed at a real, cluttered warehouse without collapsing
- Scopes become the organizational primitive for the entire semantic layer — governance, approval, export all inherit this structure
- The Admin/Review split reflects how the product will eventually be used by two distinct personas
- Dogfooding the add-source flow means we find UX problems before customers do
- BigQuery and Snowflake connectors become additive work on top of this foundation instead of requiring another model redesign

**Negative:**
- This is the largest architectural change since the initial data model. Five-ish sessions of work.
- Existing entity definitions in dev databases will need to be wiped or manually associated with a scope on migration. Acceptable since nobody but us has dev data yet.
- Plain-text credentials are a meaningful security debt. Must be paid off before any non-developer deployment.
- The checkbox schema picker feels primitive. It's deliberately so — smart pre-selection is v1 work.

## Revisit when

- First non-Postgres connector lands (BigQuery likely) — tests whether the Data Source abstraction holds up across warehouse types
- First external user adds a real warehouse — likely first real UX feedback
- Encryption-at-rest is implemented — triggers a new ADR on credential management
- LLM-assisted schema pre-selection becomes desirable — significant UX rewrite
- A real RBAC story is needed — Admin becomes a gated area, not just a URL
