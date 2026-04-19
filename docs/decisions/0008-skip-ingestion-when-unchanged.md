# ADR 0008: Skip Ingestion When Warehouse Is Structurally Unchanged

**Date:** 2026-04-19
**Status:** Accepted

## Context

Step 10c-i exposed a UX problem: every click of the Ingest button creates a new snapshot and a full set of entity proposals, even when the underlying warehouse hasn't changed. After three clicks the user has 12 near-identical Customer proposals to wade through.

This is wasteful on three axes — API cost (~$0.05 per run), reviewer attention, and database growth — and it's epistemically wrong: if the data hasn't changed, there's no new insight for Claude to offer.

We want the product to behave the way a thoughtful analyst would: "If nothing changed, I have nothing new to tell you."

## Decision

`POST /api/ingest` performs the LLM call only when **either** of these is true:

1. The new snapshot is **structurally different** from the most recent snapshot for the same source database, OR
2. The current prompt version differs from the prompt version used on the most recent snapshot

If both are unchanged, the endpoint returns a "no-op" response without calling Claude or creating a new snapshot.

## What "structurally different" means

Two snapshots are structurally equivalent if and only if:

- They reference the same source database name
- They contain the same set of (schema_name, table_name) pairs
- For each table, the set of (column_name, datum_type, native_type, is_nullable, ordinal_position) tuples matches
- For each table, the primary_key_columns list matches

Explicitly **ignored** in the comparison:

- Row count estimates (can drift without meaning)
- Sample values (random sampling → different values between runs)
- Distinct sample counts (derived from sampling)
- Table/column comments (cosmetic; changes rarely matter semantically)
- Snapshot UUID and captured_at timestamp (by definition always different)
- Sample truncation flag (operational detail, not schema)

The comparison is symmetric and order-independent — set-based, not list-based — because column ordinal position changes are real schema changes, but column list insertion order from `information_schema` is not.

## The skip response

When the endpoint skips, it returns HTTP 200 with this shape:

```json
{
  "skipped": true,
  "reason": "warehouse structurally unchanged since last run",
  "last_snapshot_id": "<uuid>",
  "last_snapshot_captured_at": "2026-04-19T...",
  "source_database": "messy_warehouse",
  "tables_ingested": 0,
  "columns_ingested": 0,
  "entities_proposed": 0,
  "... (all other counts zero)"
}
```

The UI renders this as a non-alarming info note: "No changes detected since the last ingestion on [date]. Nothing to propose."

## Why structural, not strict or lax

**Strict** (byte-level) would never skip because sample values drift. It would be equivalent to "always run" and defeat the purpose.

**Lax** (name-only) would miss real changes: a column changing from VARCHAR to INTEGER has different semantic implications. The LLM would propose against stale type info.

**Structural** matches the mental model "my schema is the same" — which is the right trigger for "no new insights possible."

## The prompt version interaction

When we improve the prompt (v0 → v1), existing approved proposals are not invalidated (ADR 0006). But fresh proposals against the same warehouse under the new prompt may legitimately differ — perhaps the new prompt surfaces something v0 missed. We want those runs to happen, even if the snapshot is identical.

So the skip check is: structural identity AND prompt_version identity. Either difference triggers a full run.

## What we're explicitly NOT doing

- **Snapshot diffing in the UI.** "Here's what changed since last time" is a nice feature but not v0.
- **Forcing a re-run.** A user who wants to force Claude to re-analyze can't today. If we hear this request, we'll add a "Force re-run" toggle. Until then, this edge case isn't worth the complexity.
- **Partial re-runs.** If one table changes, we currently re-run the whole Proposer against the whole snapshot. Per-table incremental proposals are a future optimization.

## Consequences

**Positive:**
- Repeated clicks of Ingest on an unchanged warehouse cost nothing (no LLM call) and add nothing to the database
- The demo doesn't accumulate clutter when a user clicks the button out of curiosity
- API credits are conserved during development

**Negative:**
- A user who expects "click this to get fresh proposals" may be surprised. The skip response must be clear about why nothing happened.
- Comparing snapshots requires loading the previous snapshot from the database — one extra query per Ingest call. Cheap, but worth naming.
- If Claude's output is non-deterministic enough that re-running on the same snapshot would produce meaningfully different proposals, we're masking that variance. For v0 we accept this; if it becomes a quality concern we'll revisit.

## Revisit when

- Users want a manual "Force re-run" option
- Partial (per-table) re-runs become valuable for warehouses with hundreds of tables
- We add measures/dimensions/etc. persistence — the same skip logic needs to apply across categories
