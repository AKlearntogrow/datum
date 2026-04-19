# ADR 0003: Semantic Layer Governance Model

**Date:** 2026-04-18
**Status:** Accepted

## Context

A semantic layer is only valuable if it becomes the single source of truth for business definitions — what "ARR" means, what "active customer" means, what counts as "revenue." Without governance, it's just another query tool.

The product's core philosophical stance: **the LLM proposes, humans decide.** AI is great at surfacing disagreements across messy data. It is not qualified to make policy decisions about what a company means by "revenue." That's a business leader's decision.

## Decisions

### LLM proposes, humans decide
When Datum ingests a warehouse, the LLM produces *proposals* for metrics, entities, and relationships. Proposals are drafts, not definitions. They become real only after explicit human approval.

### Single approver for v0
Approval is a single-step workflow: `proposed → approved | rejected`. No multi-stage review, no approval chains. One authorized user clicks approve (or reject with a reason).

This matches what buyers actually want in an MVP. Full governance theater (reviewer → approver → publisher) is a v1+ enterprise feature. We build the hook for it but don't implement it yet.

### Approvals are explicit, tracked, and reversible
Every approval records:
- Who approved it (user ID)
- When (timestamp)
- The full approved definition (SQL + description + source tables)

Reversal means a new proposal can supersede an approved definition. The old version is kept (versioned), never deleted. This gives us an audit trail without immutability theater.

### Definitions support named variants
When the LLM detects genuine disagreement it cannot resolve (e.g., three legitimate definitions of ARR), it proposes named variants: "ARR (Sales)", "ARR (Billed)", "ARR (Collected)". The human approver can:
- Pick one as the canonical unnamed "ARR"
- Approve multiple as distinct named metrics
- Edit the SQL of any variant before approving
- Reject all and write their own

### Every definition has a human description
Not just SQL. A plain-language description ("ARR = committed annual contract value at deal close, per sales team") must accompany every approved definition. This is what new employees and AI agents read to understand the metric's intent.

### Versioning, not overwriting
When an approved definition is replaced, the old version is retained with its approval metadata. Historical BI reports that cite "ARR as of Q1 2026" can still be understood.

### Approval is a first-class workflow step
Not a checkbox. Proposals carry state. The UI makes the state visible. Unapproved proposals cannot be queried by downstream consumers (BI tools, agents).

## Data model implications

For the eventual metric definitions table (to be built in Step 9-10):

- `id`
- `name` (may include variant suffix, e.g., "ARR (Sales)")
- `description` (human-written, required)
- `sql_expression` (the actual query fragment)
- `source_tables` (array, for lineage)
- `status` (proposed / approved / rejected / superseded)
- `proposed_by` ("system" for LLM-generated, user_id for human-proposed)
- `proposed_at` (timestamp)
- `approved_by` (user_id, nullable)
- `approved_at` (timestamp, nullable)
- `rejected_reason` (text, nullable)
- `supersedes_id` (foreign key to prior version, nullable)
- `created_at`, `updated_at`

## User roles (conceptual, v0 simplified)

- **Definers** — authorized to approve/reject/edit definitions. CFO, Head of RevOps, Data Lead.
- **Reviewers** — can propose edits, cannot approve (v1+ feature, not in v0)
- **Consumers** — query approved definitions only. All employees, all AI agents.

In v0 we implement one role (Definer) because we have one user (the person demoing). RBAC is a v1 feature.

## Why this matters commercially

The approval workflow, versioning, and governance are the product's moat. A raw LLM can produce proposals; only a governed system can become a system of record. The buyer is a CFO or Head of RevOps, not a data engineer — they care about being able to say "at our company, ARR is defined this way, and I personally signed off on it."

## Consequences

**Positive:**
- Clear philosophical foundation guides every feature decision downstream
- Audit trail and versioning are enterprise-ready from day one
- The workflow maps directly onto how finance teams already think about policy decisions

**Negative:**
- Every proposal requires human time to approve. For large warehouses with hundreds of inferred metrics, this could be onerous — we'll need batch approval UI later
- Single-approver model will not satisfy regulated industries (banks, healthcare) who need multi-sig approvals

## Revisit when

- A customer demands multi-stage approval workflows
- A customer in a regulated industry requires immutable approval records
- Batch approval becomes necessary due to large warehouses
- RBAC with multiple user roles is needed (first enterprise deal)
