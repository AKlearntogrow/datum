# ADR 0002: Synthetic Messy Warehouse Design

**Date:** 2026-04-18
**Status:** Accepted

## Context

We need a realistic, messy test warehouse to build and demo Datum against. It must:

1. Be industry-agnostic — the sales-to-cash reconciliation problem is universal across B2B
2. Expose the real pains a semantic layer solves: disagreeing definitions, missing joins, inconsistent naming
3. Be small enough to inspect manually (~160 rows total) but complex enough that reconciliation is non-trivial
4. Be reproducible — regeneration with a fixed seed must produce the same data
5. Be deliberately undocumented — no column comments, so the LLM must infer meaning from names and sample data

## The Domain: Sales-to-Cash Reconciliation

Four sibling systems that should agree on "what did we earn?" but never do:

- **Sales** (CRM-like) — what the sales team committed
- **Accounting** (AR-like) — what was invoiced
- **Finance** (bank feed) — what actually hit the bank
- **FP&A** (forecast) — what was projected

This is the core business problem the demo solves: three departments, four numbers, nobody agrees, CFO spends hours every month reconciling.

## Schema

### Table 1: `sales_opportunities` (CRM)

| Column | Type | Notes |
|---|---|---|
| `opp_id` | VARCHAR PK | `OPP-00001` |
| `account_name` | VARCHAR | Free text, inconsistent casing |
| `owner_email` | VARCHAR | Sales rep |
| `stage` | VARCHAR | Prospecting / Qualification / Proposal / Closed Won / Closed Lost |
| `amount` | NUMERIC | Total deal value (contract size) |
| `contract_months` | INTEGER | Deal term. NULLABLE (reps forget) |
| `arr_committed` | NUMERIC | Sales-declared ARR. NULLABLE. **Deliberately inconsistent with `amount / contract_months × 12`** |
| `close_date` | DATE | Expected or actual close |
| `created_at` | TIMESTAMP | When opp was created |

### Table 2: `invoices` (Accounting)

| Column | Type | Notes |
|---|---|---|
| `inv_num` | VARCHAR PK | `INV-2026-0001` |
| `customer` | VARCHAR | Company name — different casing/spelling than `sales_opportunities.account_name` |
| `inv_date` | DATE | |
| `due_date` | DATE | Usually NET-30 |
| `subtotal` | NUMERIC | |
| `tax` | NUMERIC | |
| `total` | NUMERIC | `subtotal + tax` |
| `status` | VARCHAR | Draft / Sent / Paid / Overdue |

No foreign key to `sales_opportunities` — these systems don't talk.

### Table 3: `bank_transactions` (Finance)

| Column | Type | Notes |
|---|---|---|
| `txn_id` | VARCHAR PK | Bank reference |
| `posted_date` | DATE | When money moved |
| `description` | VARCHAR | Free text: `"PAYMENT ACME CORP REF INV2026001"` |
| `amount` | NUMERIC | Positive incoming, negative outgoing. **Column name collides with `sales_opportunities.amount` but means something different** |
| `type` | VARCHAR | ACH / Wire / Check |

No customer ID, no invoice reference. Linkage lives in the free-text description — just like real bank feeds.

### Table 4: `revenue_forecast` (FP&A)

| Column | Type | Notes |
|---|---|---|
| `forecast_month` | DATE PK (composite) | First day of month |
| `segment` | VARCHAR PK (composite) | Enterprise / Mid-Market / SMB — **dimension that exists nowhere else** |
| `forecasted_amount` | NUMERIC | |
| `ltv_estimate` | NUMERIC | Per-segment LTV prediction |
| `expected_churn_rate` | NUMERIC | Decimal (0.05 = 5%), assumption behind `ltv_estimate` |
| `owner` | VARCHAR | Analyst name |
| `notes` | VARCHAR | Free-text |

## The ARR Disagreement (intentional)

Within `sales_opportunities` alone, three implicit definitions of ARR:

- `arr_committed` — what the rep declared
- `amount × 12 / contract_months` — derived from deal terms
- (Cross-table) — `SUM(invoices.total)` for active customers over 12 months

These disagree for ~80% of accounts. The semantic layer's first real job is surfacing this and asking a human to pick a canonical definition.

## The LTV Disagreement (intentional)

- **Sales-implied:** `amount × (contract_months / 12)` extrapolated
- **Accounting-implied:** `SUM(invoices.total)` to date (backward-looking)
- **FP&A:** `ARR × (1 / expected_churn_rate)` — the SaaS formula, forward-looking

The forecast table encodes the FP&A definition via `ltv_estimate` and `expected_churn_rate`. The semantic layer must detect that no other system agrees with it.

## Deliberate Realistic Mess

The following are intentional data quality problems, not bugs:

1. Three customers exist in all systems with slightly different spellings (`ACME Corporation` / `Acme Corp.` / `acme corp`)
2. Two Closed Won deals were never invoiced (sales team oversight)
3. Three invoices were paid in two partial bank transactions
4. One customer paid the wrong amount; a credit was issued later
5. Q1 forecast is ~15% higher than actual closed revenue
6. One bank transaction is a refund (negative) with no corresponding invoice
7. ~10-15% of opportunities have NULL `contract_months` or `arr_committed`
8. The `segment` dimension (Enterprise/Mid-Market/SMB) exists only in forecast — not mapped to accounts anywhere

## Data Volume

- ~40 opportunities (~25 Closed Won)
- ~30 invoices
- ~50 bank transactions
- ~36 forecast rows (12 months × 3 segments)
- **Total: ~156 rows across 4 tables**

Small enough to inspect manually, complex enough to demonstrate reconciliation value.

## Technical Decisions

### Separate database, same Postgres instance
The messy warehouse lives in a database called `messy_warehouse`, separate from the `datum` app database. Both in the same Postgres container. This mimics the real-world "connect to an external warehouse" pattern cleanly without the complexity of a second container.

### Python + Faker for generation
Data is generated by `synthetic_data/generate.py` using Faker. Fixed random seed for reproducibility. Running the script wipes and regenerates the warehouse data, leaving schema intact.

### Schema in SQL, data in Python
`synthetic_data/schema.sql` contains `CREATE TABLE` statements. Runs on container startup via `docker-entrypoint-initdb.d`. `generate.py` populates the data after the schema exists.

### No column comments
Tables are created WITHOUT `COMMENT ON COLUMN` statements. This is the point: the semantic layer must infer meaning from column names, types, and sample data. Adding comments would trivialize the problem.

## Consequences

**Positive:**
- Every buyer immediately understands the pain without domain learning
- The LLM has real, non-trivial work to do
- Reconciliation mismatches are representative of actual B2B data
- Deterministic regeneration enables reliable demos

**Negative:**
- The demo is only as convincing as the realism of the mess — we'll need to iterate on Faker seed choices
- 156 rows is small; we may need to scale up to 1,000+ to test performance later

## Known limitations

These are known gaps in the synthetic data that we have accepted for v0 of the demo:

1. **No revenue recognition timing.** Opportunities record `amount` (total contract value) and `close_date`, but not how that revenue recognizes over the contract term. This means "Q1 actuals" measured as `SUM(amount) WHERE close_date in Q1` is not directly comparable to Q1 forecast, which represents per-month recognized revenue. The deliberate ~15% Q1 forecast overstatement is encoded in the forecast generator's multiplier, not derivable by comparing against the sales table. The LLM can still surface the pattern as "Q1 forecast appears inflated relative to Q1 pipeline activity" even without revenue-recognition math.

2. **Verification queries require fuzzy matching.** Because customer names deliberately vary in spelling across tables, exact-match joins return zero results. Any query verifying cross-table consistency must use fuzzy matching (e.g., `LEFT(UPPER(REGEXP_REPLACE(name, '[^A-Za-z]', '', 'g')), 4)`) until the semantic layer provides a canonical entity resolution.

3. **Bank description parsing is ad-hoc.** The invoice reference inside `bank_transactions.description` follows no strict format and isn't always present. Linking a bank transaction back to an invoice requires text parsing, not a structured join.

## Revisit when

- We have a paying customer whose real data stress-tests this design
- Demo feedback suggests the messiness isn't hitting the right pain points
- We need to add industry-specific columns (e.g., real estate leases, healthcare claims) for a specific vertical pitch
