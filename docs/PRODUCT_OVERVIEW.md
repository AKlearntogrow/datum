# Datum — Product Overview

## The problem

Every data-driven company hits the same wall: their warehouse grows messier every quarter, and no single person can answer a question like "what's our ARR?" without a data engineer spending an afternoon reconciling conflicting definitions in different tables.

The standard fix is a **semantic layer** — a layer between the raw warehouse and the tools people use (Tableau, Looker, dashboards, AI agents), where business metrics are defined once and served consistently everywhere.

The problem with existing semantic layer tools (Cube, dbt metrics, LookML) is that *a data engineer still has to write all the definitions by hand*. That means a CFO who wants to know their ARR is still dependent on an engineer who has time to model it. And at most companies, that engineer is already booked for the next six weeks.

## What Datum does

Datum proposes the semantic layer for you. You point it at your warehouse. It analyzes your schema, looks at sample data, and drafts an initial semantic model — entities, metrics, dimensions, time ranges, relationships, and a list of data quality issues it noticed.

You don't write the definitions. You **review** them. Approve the ones that look right. Reject the ones that don't. Edit the ones that are close. Datum presents each proposal with the LLM's reasoning and evidence so you can trust (or challenge) the suggestion.

The pitch in one line: **point at your warehouse, review the proposals, get a semantic layer without needing a data engineer to write it.**

## Who it's for

The buyer is the person asking "what's our ARR?" and not getting a straight answer — typically a CFO, a Head of Data, a RevOps lead, or a founder running a growing SaaS company. Not a data engineer. Datum is designed to be usable by someone who can read SQL but doesn't want to write it all day.

The existing market (Cube and its peers) targets the data engineer. We target the business leader who's currently stuck waiting for that data engineer.

## What's different about Datum

**1. AI-drafted, human-approved.** Every definition starts as an LLM proposal, with visible reasoning and evidence. Every definition is explicitly reviewed before it becomes part of your semantic layer. Nothing is silently approved.

**2. It reads messy data and tells you the truth.** Datum is designed for real-world warehouses — the ones with inconsistent spelling, NULL fields, mismatched identifiers across tables, and bugs in legacy calculations. Rather than pretending your data is clean, Datum surfaces the mess as data quality flags alongside its proposals.

**3. Full governance trail from day one.** Every approval, rejection, and revision is recorded. If your board asks who defined ARR and when, you can answer in one click. Metrics can be reopened for reconsideration, edited, or superseded — and every prior decision stays visible in the audit trail.

**4. Compatible with the tools you already use.** Our approved definitions are designed to flow outward — to Cube, to dbt, to BI tools, to AI agents. We aren't trying to replace your BI stack. We're the piece that's missing from it.

## How it works, from the user's perspective

**1. Connect your warehouse.** Add a Data Source in the Admin section — your Postgres, BigQuery, or Snowflake credentials, stored privately.

**2. Pick the parts that matter.** Most warehouses are full of data that isn't business-relevant — engineering telemetry, legacy dumps, staging tables. You tell Datum which schemas to actually look at, using a simple checkbox UI. This is called a Scope.

**3. Run analysis.** Datum samples your data, sends a structured description to Claude (Anthropic's LLM), and gets back proposals across six categories: entities, metrics, dimensions, time ranges, relationships, and data quality flags.

**4. Review.** You see each proposal as a card with full reasoning: what Claude thought the metric means, why it thinks so, what evidence it saw in your data. Approve, reject, or edit each one.

**5. Consume.** Your approved definitions become available to downstream tools — BI platforms, AI agents, custom integrations — through an API.

## What it can do today

- Connects to Postgres databases
- Analyzes your schema and samples real data
- Drafts proposals for entities (customers, invoices, opportunities, etc.) with LLM reasoning
- Lets you approve, reject, edit, or reopen each proposal through a clean web interface
- Records every decision with full audit trail (who approved what, when, and why)
- Skips redundant analysis when your warehouse hasn't structurally changed, keeping costs down

## What's coming next

In rough priority order:

- **Data source management.** Persistent named warehouse connections; multiple warehouses; saved scope selections for different business domains.
- **Review and approval for all six proposal categories.** Currently only entities are persisted; metrics, dimensions, time ranges, relationships, and data quality flags will follow.
- **Downstream integration.** Export to Cube-compatible format for companies that already have a Cube deployment. Direct query API for BI tools and AI agents. LookML and dbt metric exports as demand emerges.
- **BigQuery and Snowflake connectors.** Architecture is in place; each new warehouse type is an additive effort.
- **Schema evolution handling.** When your warehouse changes — new tables, renamed columns — Datum will tell you which of your existing metrics are affected, rather than silently breaking them.
- **Team access.** Role-based approvals, multi-user workflows, audit logs surfaced for compliance reviews.

## What it's NOT trying to be

- **Not a BI tool.** Datum doesn't build dashboards. It feeds the tools that do.
- **Not a data warehouse.** Datum reads your warehouse; it doesn't replace or move it.
- **Not magic.** The LLM proposes; the human approves. No definition is live in your business without explicit sign-off.
- **Not a replacement for data engineers.** They still matter for the hard work — data pipelines, warehouse design, complex custom modeling. Datum handles the specific bottleneck of "someone who understands the business, proposing good metric definitions they'd sign their name to."

## Where the name comes from

"Datum" is the singular of "data." The unit. The one thing you can actually point at and say "this means ARR." A semantic layer is made of definitions, not just data — individual, named, approved, consistent. One at a time.

## Status

Early development. Running locally. No external users yet. Built over the course of one intensive week in April 2026 by Akhil, with architectural support from a Claude-based pair programming workflow.

Codebase at: https://github.com/AKlearntogrow/datum
