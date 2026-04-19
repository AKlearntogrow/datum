# ADR 0005: The Semantic Proposal Prompt

**Date:** 2026-04-19
**Status:** Accepted (v2, supersedes the initial version from the same day)

## Context

The core of Datum is a prompt. The connectors and ingestion pipeline exist only to produce input for this prompt; the review UI and downstream consumers exist only to process its output. If the prompt is well-designed, the product feels like a thoughtful analyst. If it's poorly designed, it feels like confident nonsense.

This ADR fixes the design of the prompt and its expected output. Step 9b implements it; Step 10 builds the UI around the output shape defined here.

This is v2 of the ADR. The initial v1 (same day) had a generic `metrics` category. After reviewing Cube.dev's published data modeling conventions — the most mature semantic layer in the industry, with years of production UX testing behind their choices — we adopted the industry-standard **measure / dimension** split. Doing this before code depends on the shape is cheaper than retrofitting later.

## Vocabulary (borrowed from established semantic-layer practice)

- **Entity** — A real-world business object that rows in the data represent. "Customer", "Invoice", "Opportunity". May span multiple tables when the same entity appears with different names across source systems.
- **Measure** — A value that gets aggregated: count, sum, average, max, etc. "Total revenue", "Number of Closed Won deals", "Average contract length". Measures are typically numeric and are the numbers people *calculate*.
- **Dimension** — A value used to slice, group, or filter measures. "Customer name", "Sales rep", "Product category". Dimensions are the things people *group by*.
- **Time dimension** — A special dimension used for trend analysis: dates and timestamps. Called out separately because every finance-oriented question has a time dimension, and BI tools treat them specially.
- **Relationship** — A link between two tables, strict (FK) or fuzzy (name match).
- **Data quality flag** — A pattern in the data the human should know about before trusting metrics built from it.

These five categories are what the prompt asks the LLM to produce.

## Design principles

1. **The LLM proposes; humans decide.** (ADR 0003) The prompt must enumerate options rather than pick winners.
2. **Strictly grounded.** The LLM must only propose items that reference tables, columns, and values actually present in the provided snapshot. No inventing fields.
3. **Structured output.** The LLM returns JSON conforming to a schema defined below.
4. **Verbose rationales.** Every proposal carries a rationale, evidence, and confidence level.
5. **Schema-anchored evidence.** Evidence references concrete tables, columns, and sample values from the snapshot — not generalities.
6. **Snake case everywhere for machine identifiers.** Display strings stay human-readable.

## Naming conventions

Every proposal has two names:

- `name` — snake_case machine identifier, e.g., `arr_sales`, `closed_won_amount`, `customer`
- `display_name` — human-readable label, e.g., `"ARR (Sales)"`, `"Closed-Won Amount"`, `"Customer"`

The machine name is how the metric is referenced in SQL, APIs, and downstream tools. The display name is what a CFO sees in the review UI and in every BI tool that consumes Datum's output.

Naming rules for the LLM:
- Machine names: snake_case, ASCII only, start with a letter, no trailing numbers unless semantically meaningful.
- When multiple legitimate variants of the same concept exist, suffix the machine name with the source context: `arr_sales`, `arr_billed`, `arr_collected`.
- Display names may include spaces, parentheses, and punctuation for clarity.

## The input

The prompt receives a rendered form of a `SchemaSnapshot`. Rendering is ingestion's responsibility (to be built in Step 9b). The rendered form includes:

- The source database name
- For each table: qualified name, primary key columns, estimated row count, sample truncation flag, optional table comment
- For each column: ordinal position, name, normalized `DatumType`, original `native_type`, nullability, optional comment, a small set of sample values, and the distinct-value count within the sample

The prompt itself adds:

- A role statement framing the LLM as a "semantic layer analyst"
- Definitions of the five categories (entities, measures, dimensions, time dimensions, relationships, data quality flags) with examples
- The strict grounding rule
- The output JSON schema with inline explanations
- One canonical worked example showing well-formed output

## The output schema

The LLM returns a single JSON object with six arrays:

```json
{
  "entities": [
    {
      "name": "customer",
      "display_name": "Customer",
      "description": "A business customer referenced across sales and accounting systems.",
      "source_columns": [
        {"table": "public.sales_opportunities", "column": "account_name"},
        {"table": "public.invoices", "column": "customer"}
      ],
      "rationale": "Both columns hold free-text company names. Sample values overlap when normalized for casing and punctuation (e.g., 'Acme Corp.' and 'ACME CORP').",
      "evidence": [
        "sales_opportunities.account_name samples: ['Acme Corporation', 'Soylent Group']",
        "invoices.customer samples: ['Acme Corp.', 'Soylent Grp']"
      ],
      "confidence": "high"
    }
  ],

  "measures": [
    {
      "name": "arr_sales",
      "display_name": "ARR (Sales)",
      "description": "Annual recurring revenue as declared by the sales team at deal close.",
      "aggregation": "sum",
      "sql_expression": "SUM(arr_committed)",
      "source_tables": ["public.sales_opportunities"],
      "filter_expression": "stage = 'Closed Won'",
      "format_hint": "currency_usd",
      "rationale": "The arr_committed column directly represents sales's declared ARR. Filtering to Closed Won aligns with the business definition of 'won' revenue.",
      "evidence": [
        "sales_opportunities has columns (amount, contract_months, arr_committed)",
        "arr_committed sample values include 20265.36, 80000.00, 240000.00"
      ],
      "confidence": "high",
      "caveats": [
        "arr_committed is NULL for approximately 12% of opportunities",
        "arr_committed sometimes differs from (amount * 12 / contract_months) by up to 20%"
      ]
    }
  ],

  "dimensions": [
    {
      "name": "deal_stage",
      "display_name": "Deal Stage",
      "description": "The pipeline stage of a sales opportunity.",
      "source_column": {"table": "public.sales_opportunities", "column": "stage"},
      "cardinality_hint": "low",
      "sample_values": ["Prospecting", "Qualification", "Closed Won", "Closed Lost"],
      "rationale": "Column has 4 distinct sampled values that read as pipeline stages. Typical CRM deal lifecycle vocabulary.",
      "evidence": [
        "sales_opportunities.stage distinct=4 samples: ['Closed Won', 'Qualification', 'Proposal']"
      ],
      "confidence": "high"
    }
  ],

  "time_dimensions": [
    {
      "name": "close_date",
      "display_name": "Deal Close Date",
      "description": "Date an opportunity was (or is expected to be) closed.",
      "source_column": {"table": "public.sales_opportunities", "column": "close_date"},
      "granularity_hint": "day",
      "rationale": "Date-typed column named close_date in a sales opportunities table. Standard CRM vocabulary.",
      "evidence": [
        "sales_opportunities.close_date samples: [datetime.date(2025, 10, 5), datetime.date(2025, 11, 19)]"
      ],
      "confidence": "high"
    }
  ],

  "relationships": [
    {
      "name": "sales_to_invoices_via_customer_name",
      "display_name": "Sales ↔ Invoices (by customer name)",
      "description": "Opportunities link to invoices through customer name, but requires fuzzy matching due to spelling variance.",
      "from_table": "public.sales_opportunities",
      "from_column": "account_name",
      "to_table": "public.invoices",
      "to_column": "customer",
      "relationship_type": "fuzzy_match",
      "rationale": "Both fields hold free-text customer names with inconsistent casing and punctuation across systems. No foreign key exists.",
      "evidence": [
        "sales_opportunities.account_name: 'Acme Corporation'",
        "invoices.customer: 'Acme Corp.'"
      ],
      "confidence": "medium"
    }
  ],

  "data_quality_flags": [
    {
      "severity": "warning",
      "title": "High NULL rate in contract_months",
      "description": "About 12% of sales opportunities have no contract term recorded, making ARR derivation impossible for those rows.",
      "affected_columns": [
        {"table": "public.sales_opportunities", "column": "contract_months"}
      ],
      "rationale": "Sample showed NULLs in contract_months; business metrics depending on contract length will silently exclude these rows or return incorrect values.",
      "evidence": [
        "sales_opportunities.contract_months sample: [24, 24, 12, None, None]"
      ]
    }
  ]
}
```

### Field requirements

- **confidence** values: `"low"`, `"medium"`, `"high"`. No other values permitted.
- **severity** values: `"info"`, `"warning"`, `"error"`.
- **aggregation** values: `"count"`, `"count_distinct"`, `"sum"`, `"avg"`, `"min"`, `"max"`, `"custom"`. When `"custom"`, the `sql_expression` must be a complete expression.
- **cardinality_hint** values: `"low"` (<=10 distinct), `"medium"` (11-100), `"high"` (101-10k), `"very_high"` (>10k or identifier-like).
- **granularity_hint** values: `"day"`, `"week"`, `"month"`, `"quarter"`, `"year"`. For timestamps, the finest practical grain the data supports.
- **relationship_type** values: `"exact_match"`, `"fuzzy_match"`, `"derived"`, `"one_to_many"`, `"many_to_many"`, `"unlinked_dimension"`.
- **format_hint** values (measures only): `"integer"`, `"decimal"`, `"percent"`, `"currency_usd"`, `"currency_unknown"`, `"duration_days"`. UI hint only; never a hard rule.
- **filter_expression** on measures is optional; if present, it's applied as a WHERE clause when computing the measure.
- **evidence** entries must be short strings referencing concrete data from the snapshot.
- Every `source_columns` / `source_column` / `affected_columns` / `from_table` / `to_table` entry must refer to a table present in the input snapshot. The LLM may not invent tables or columns.
- `sql_expression` should be ANSI SQL where possible. Humans will review and edit.

### Empty arrays are valid

If the snapshot is too small or too messy to produce meaningful proposals in a category, the LLM returns an empty array for that category. Explicitly encouraged by the prompt.

### When the LLM is uncertain between interpretations

Emit multiple proposals, each with its own name, rationale, and confidence. Do not pick one over another. Example: if ARR could plausibly mean three things, emit three separate `measures` entries (`arr_sales`, `arr_billed`, `arr_implied_from_contract`), each with its own evidence and caveats.

## The prompt structure

The full prompt has three parts:

1. **System prompt** — static role framing, defines the six categories, enforces the output schema, establishes the strict grounding rule. Cacheable (Anthropic prompt caching).
2. **User prompt** — dynamic, contains the rendered snapshot.
3. **Assistant scaffold** (optional) — may begin the assistant's turn with `{` to nudge JSON output, though we prefer Anthropic's tool-use / structured-output API to enforce it.

The system prompt is a fixed artifact versioned alongside the code. It lives at `backend/src/semantic/prompts/system.md` (v0). Future versions get suffixes like `system_v2.md` — never overwritten, always versioned, so A/B comparison and regression investigation are always possible.

## Prompt caching

The system prompt never changes between runs (only the snapshot does). We enable Anthropic prompt caching on the system prompt to reduce cost and latency. Cache savings on the repeated portion are ~10x on cost and ~2x on latency after the first call. See https://docs.claude.com/en/docs/build-with-claude/prompt-caching

## Model choice

- **Development:** `claude-sonnet-4-5`. Sufficient capability for structured extraction, roughly 1/5 the cost of Opus, faster.
- **Production default:** same, unless quality gaps emerge.
- **Upgrade path:** model string is configurable via `ANTHROPIC_MODEL` env var, falling back to `claude-sonnet-4-5`. One-line change to switch.

## Versioning the prompt itself

Every proposal stored in the app database records:

- The prompt version that generated it (e.g., `"v0"`)
- The model string used (e.g., `"claude-sonnet-4-5"`)
- The snapshot id it was generated from

When we tune the prompt, old proposals remain traceable to the prompt version that produced them. Audit trail for governance (ADR 0003).

## What we are explicitly NOT doing in v0

- **Multi-turn refinement.** The LLM gets one shot per snapshot.
- **Inferring column meaning from names alone.** The LLM must use sample values, not just rename-matching.
- **Generating Cube-compatible YAML.** That's Step 11. v0 produces our internal JSON proposal shape only.
- **Multi-language support.** English only.
- **Hierarchies between dimensions.** Country → State → City is a real thing but out of scope for v0.
- **Row-level security or access policies.** Also out of scope.

## Consequences

**Positive:**
- Measure/dimension split aligns with 20+ years of BI practice and every semantic-layer tool on the market. New users and new engineers will recognize the vocabulary instantly.
- Naming conventions (snake_case machine name + display_name) prevent a whole class of "what do I call this thing?" debates.
- Structured output with confidence and evidence fields enables UX like "sort by confidence" and "filter to high-confidence only."
- Prompt caching keeps development cost-sustainable.

**Negative:**
- The JSON schema is rigid. If we discover a category we didn't anticipate, we'll need an ADR to extend it.
- Verbose rationales inflate output tokens; a typical full response may run 3-5k output tokens.
- Asking the LLM to produce six categories instead of four in v1 means more for it to reason about per snapshot. Watch for quality degradation.

## Revisit when

- A specific customer's warehouse consistently produces empty proposals — signals the prompt is too strict.
- The JSON output is frequently malformed — signals we should switch to Anthropic's tool-use API for enforced structure.
- Users ask for hierarchy support or derived-column proposals (explicitly excluded from v0).
- We need to emit Cube-compatible or dbt-compatible output (Step 11 and beyond).
- We need to support a non-analytical source like a document store or event stream.
