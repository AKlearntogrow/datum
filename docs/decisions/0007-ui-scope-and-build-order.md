# ADR 0007: UI Scope and Build Order

**Date:** 2026-04-19
**Status:** Accepted

## Context

Step 9 produced a working end-to-end pipeline that turns a messy warehouse into 51 validated proposals. Step 10 is the review UI — the step where the product becomes a product. Before building, we need to commit to scope and sequence, because "the review UI" is a category of feature that can sprawl into months of work.

ADR 0003 (governance), ADR 0005 (proposal shape), and ADR 0006 (definitions lifecycle) established what the UI must eventually support. This ADR decides what v0 of that UI looks like and in what order we build it.

## Decisions

### v0 has no authentication

The app assumes a single unauthenticated user. No login screen, no users table, no sessions. All endpoints are open from any origin that CORS allows.

This is explicitly a laptop-demo product in v0. When the first external user wants to try it, we add lightweight local login (v1). When the first company wants to deploy it, we add SSO/OAuth (v2+).

**Why not build auth now:** auth correctly done is a week of work (password hashing, sessions, CSRF, rate limiting). Done sloppily, it's a security liability. Neither is a fit for this phase. Skipping it is legitimate because our threat model is "Akhil's laptop during development and demos."

**What we DO build that matters for later:** every `Definition` record carries `proposed_by` and `approved_by`. For v0, both are hardcoded to `"local_user"`. When we add real auth, these fields are already in place. No schema change needed.

### v0 builds tracer bullets by proposal category

We do NOT build the full UI for all six proposal categories at once. We build one category end-to-end — database, backend endpoints, UI rendering, approve/reject — then move to the next.

**First slice: entities.** Chosen because:
- Smallest proposal shape (simplest UI card)
- The cross-table Customer entity is the single most visually striking demo moment
- Approve/reject is the minimum workflow — no SQL to edit, no aggregation to pick
- Getting something in a browser within a few sessions matters for momentum and for starting customer conversations

**Subsequent slices, in order:** measures → dimensions → time_dimensions → relationships → data_quality_flags.

Measures come second because they're the most commercially important — ARR, revenue, pipeline — and because the added complexity (SQL expression, aggregation, filter, caveats) stresses the UI design in useful ways.

### Each slice is full-stack

A slice is not "the database table for entities." A slice is:

1. Alembic migration adding the table(s) for that category
2. SQLAlchemy models matching the Pydantic proposal schema
3. An ingest-and-store workflow: run Proposer, persist proposals with `status=proposed`
4. FastAPI endpoints: list proposals, approve, reject, edit
5. Next.js page rendering the proposals with approve/reject buttons
6. Wire-up and at least one manual end-to-end pass
7. Tests at each layer

Each slice ends with a user being able to load the app, see the proposals, and click Approve or Reject on at least one, with the result persisted and reflected in the database.

### Hard exclusions for v0 of the UI

The following are explicitly out of scope and go to v1 or beyond:

- Multi-user support, permissions, roles
- User-authored proposals from the UI (the data model supports it, but the UI doesn't yet expose it)
- Rich inline editing of SQL expressions (v0 edit is a plain textarea; no syntax highlighting or validation)
- Supersession of already-approved definitions (v0 only handles proposed → approved | rejected)
- Schema evolution handling (new snapshots overwrite old ones for v0; ADR 0006's compatibility report is a v1 concern)
- LLM re-run from the UI (Proposer runs only via CLI script in v0)
- Diff views comparing an edited definition to its original proposal
- Export to Cube YAML or any other downstream format
- Search, filter, bulk actions

Every item above is a legitimate feature. None of them are in the v0 UI.

### v0 UI visual scope

The UI is a single page. Not a dashboard app with routing and layout. One page showing the current proposal queue, grouped by category, with approve/reject buttons and an edit textarea. Professional-looking, not pretty. Tailwind defaults.

When a second view is genuinely needed (e.g., "list of approved definitions"), we add a second route. Until then, one page is enough.

## Build order — the concrete slice plan

Each item is roughly one session's worth of work:

- **10a**: Database models, migrations, and the first proposal storage — snapshots + entities only
- **10b**: Backend API for the entities slice — list, approve, reject, edit
- **10c**: Frontend UI for the entities slice — page, proposal cards, action buttons
- **10d**: Wire it together, manual end-to-end test, commit first demo
- **10e**: Repeat 10a-10d for measures
- ... and so on per category

Each slice ends with a git cap message documenting what's demo-able after that slice.

## Consequences

**Positive:**
- A demo-able artifact after slice 10a-10d, likely within a few sessions
- Each slice is small enough that UX problems surface before they've been replicated six times
- The hard exclusions are explicit, so scope creep is easy to notice and push back on
- No auth in v0 means no security debt from half-done auth — we either have real auth or we don't

**Negative:**
- Six separate slices means some repeated scaffolding (endpoint patterns, UI card patterns) — acceptable because we'll refactor after slice 2 or 3 when the repetition is obvious
- Deferring user authoring from the UI means early customer demos won't showcase one of our real differentiators — acceptable because approve/reject is the more common workflow and showcases governance adequately

## Revisit when

- After slice 3 (dimensions): reassess whether the per-category structure still makes sense or if a more unified UI pattern has emerged
- When someone outside you wants to try the app in a browser they control — triggers v1 auth
- When the first customer conversation asks "can I add my own metric from the UI?" — triggers user-authoring UI work
