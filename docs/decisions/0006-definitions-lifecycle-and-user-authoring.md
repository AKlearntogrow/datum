# ADR 0006: Definitions Lifecycle and User Authoring

**Date:** 2026-04-19
**Status:** Accepted

## Context

Datum's promise is "you don't need a data engineer." That promise only holds if the system gracefully handles three things after initial approval:

1. Users who want to add metrics the LLM never proposed
2. Schema evolution — new tables, new columns, new data sources
3. Revisions and supersession of approved definitions over time

ADR 0003 established the governance model (LLM proposes, human approves, single approver, versioned). ADR 0005 established the proposal shape. This ADR establishes how those proposals evolve into approved, user-editable, and user-authored definitions — and how the system handles change over time.

## Core insight: one data model for everything

Machine-proposed definitions, user-authored definitions, and approved definitions are all the same thing. They share tables. They differ by metadata fields, not by structure.

A single `Definition` row captures any of:
- "Claude proposed this, it's waiting for review" (`status=proposed`, `proposed_by=system`)
- "The CFO wrote this from scratch" (`status=proposed`, `proposed_by=user:{id}`)
- "The CFO edited Claude's proposal, here's the edited version" (`status=approved`, `parent_id=<original>`, `proposed_by=user:{id}`)
- "Someone replaced this definition last quarter with an updated one" (`status=superseded`, `supersedes_id=<new>`)

This symmetry is load-bearing. Without it, user-authored metrics become a second-class feature with a separate code path — the kind of rot that slowly makes a product worse over time.

## The lifecycle states

Every definition is in exactly one of these states at any time:

- `proposed` — drafted (by LLM or user), awaiting review
- `approved` — reviewed and accepted; live and queryable
- `rejected` — reviewed and explicitly declined; preserved for audit
- `superseded` — was approved, replaced by a newer definition

State transitions:
proposed -> approved    (human clicks approve)
proposed -> rejected    (human clicks reject)
approved -> superseded  (a new approved definition supersedes this)

Rejected and superseded definitions are never deleted. Audit trail.

## The definition record shape

One database table per category (entities, measures, dimensions, time_dimensions, relationships, data_quality_flags), each with shared metadata columns:

- `id` — UUID primary key
- `kind` — one of: entity | measure | dimension | time_dimension | relationship | data_quality_flag (may be implicit if separate tables)
- `name`, `display_name`, `description` — as per ADR 0005
- Category-specific payload fields (same as the Pydantic proposal models)
- `status` — proposed | approved | rejected | superseded
- `proposed_by` — `"system"` for LLM-generated, `"user:<id>"` for human-authored
- `proposed_at` — timestamp
- `approved_by`, `approved_at` — nullable until approved
- `rejected_by`, `rejected_at`, `rejected_reason` — nullable until rejected
- `supersedes_id` — nullable; if set, this definition replaces a previous one
- `parent_id` — nullable; if set, this definition is an edit of another (preserves the original rationale and evidence from Claude)
- `prompt_version` — if `proposed_by=system`, which prompt version produced it
- `model` — if `proposed_by=system`, which model produced it
- `source_snapshot_id` — which `SchemaSnapshot` this definition was created against

## User authoring

Users can create definitions directly. The UI (Step 10+) provides a form matching the same fields as the proposal schema. On save:

- The system creates a `Definition` row with `status=proposed`, `proposed_by=user:<id>`
- The definition goes through the same approval workflow as LLM proposals
- Self-approval is permitted for v0 (single-approver model from ADR 0003)

User-authored definitions use the same storage, same approval mechanism, same query pipeline, same everything. The only difference is provenance.

## Schema evolution

Every `Definition` references a `source_snapshot_id` — the schema snapshot it was created against.

When a new ingestion run produces a new `SchemaSnapshot`, the system:

1. Stores the new snapshot (snapshots are immutable and versioned).
2. Compares the new snapshot's table/column inventory against the source_snapshot of every approved definition.
3. For each approved definition whose source tables or columns have changed, produces a **Compatibility Report**:
   - `compatible` — all referenced tables and columns still exist with the same types
   - `needs_review` — a referenced column's type changed, or a table was renamed (heuristic match)
   - `broken` — a referenced table or column no longer exists
4. Flags affected definitions in the UI. No automatic migration; the user decides what to do.

**Nothing is broken without human review.** If the CFO's "ARR (Sales Committed)" definition referenced `sales_opportunities.arr_committed` and that column is gone, the definition stays approved but is marked as `broken`. Queries against it fail with a clear error. The CFO fixes or supersedes it on their own schedule.

This is the **"stable contracts, graceful change"** principle. The underlying data is allowed to change; the user's definitions are not silently rewritten.

## LLM re-run on new snapshots

When a new snapshot is ingested, the system optionally re-runs the Proposer. New proposals are stored alongside existing approved definitions (not replacing them).

The review UI surfaces "Claude looked at your updated warehouse and proposes these new metrics" as a separate queue. Existing approved definitions remain unchanged unless the user explicitly supersedes them.

This is deliberately additive rather than destructive. We never auto-replace a human-approved definition with a new machine proposal.

## Revisions vs supersession

Two distinct operations, both valid:

- **Revision (edit):** the user clicks "edit" on a `proposed` definition before approving it. The edited version replaces the proposed one (same row, mutated) but preserves the original rationale/evidence in a `proposal_origin` JSON field for audit. This is lightweight — an unapproved proposal is a draft, drafts are meant to be edited.

- **Supersession:** the user creates a new definition that replaces an already-approved one. This is a real state change. The old definition becomes `superseded`; the new one becomes `approved` with `supersedes_id=<old>`. Queries against the old definition's name resolve to the new one going forward, but historical queries (e.g., "what was ARR as of March?") can still reference the superseded version by id.

Revisions are cheap and expected. Supersession is a governance event and surfaces in the audit log.

## What this enables (product features that fall out for free)

- "Show me the approval history of ARR" — just filter the definitions table by name and sort by time.
- "Who last approved the Revenue metric?" — `approved_by` on the current approved version.
- "What did the CFO change from Claude's original proposal?" — diff against `parent_id`.
- "Export our semantic layer to Cube YAML" — iterate `status=approved`, render each.
- "What metrics are broken after the warehouse restructure?" — filter by compatibility report flag.

All of these come from a single unified data model rather than special cases.

## Consequences

**Positive:**
- User-authored metrics are a first-class citizen, not a second-class "also we support this" feature.
- The audit trail for governance (ADR 0003) is automatic — every approval, edit, and replacement leaves a row.
- Schema evolution is graceful: nothing silently breaks, and the user is told what changed.
- Future features (versioned queries, Cube export, RBAC) can layer on without restructuring the core model.

**Negative:**
- More database tables and relationships than a naive design would have. Worth it for the symmetry.
- The compatibility-report logic for schema evolution is genuinely non-trivial. We'll build the simplest possible version for v0 ("broken if a referenced table/column doesn't exist in the new snapshot") and refine from there.
- Requiring `source_snapshot_id` on every definition means users can't create definitions before ingesting a warehouse. Acceptable — ingestion is cheap and comes before any user activity anyway.

## Revisit when

- We need multi-user approval workflows (enterprise deals)
- We need branching — where a user wants to try a new definition "in parallel" with the existing one
- We need bulk operations — approving or rejecting many proposals at once
- We observe that schema evolution frequently requires renames, triggering a need for heuristic column matching (LLM-assisted column linking)
