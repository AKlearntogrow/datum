# ADR 0004: Connector Architecture

**Date:** 2026-04-18
**Status:** Accepted

## Context

Datum must support multiple target warehouses — Postgres first, then BigQuery, Snowflake, Redshift, etc. The system's value is that the same semantic layer logic works regardless of which warehouse holds the data.

We need to decide where warehouse-specific logic lives and where warehouse-agnostic logic lives. This decision shapes every line of code downstream — ingestion, sampling, schema-aware prompting, query generation.

## Decision: Thin connector, fat ingestion

**Connectors** (`backend/src/connectors/`) expose only raw reads against a specific warehouse. They know SQL dialects, driver quirks, and authentication. They do not know anything about Datum's internal representation.

**Ingestion** (`backend/src/ingestion/`) orchestrates. It calls connectors to pull raw metadata and sample data, then shapes the result into Datum's standardized internal representation. It owns sampling strategy, normalization, and all warehouse-agnostic logic.

## The connector interface

Every connector implements the same narrow protocol:

- `list_tables() -> list[TableRef]` — return all tables the user has visibility into
- `describe_table(ref: TableRef) -> RawTableSchema` — return columns, types, nullability, PK info, and any available native comments
- `sample_rows(ref: TableRef, limit: int) -> list[dict]` — return up to `limit` rows as plain dicts

These signatures are warehouse-agnostic. The protocol is defined in `backend/src/connectors/base.py` as a Python `Protocol`.

`TableRef` identifies a table across warehouses (`database`, `schema`, `name`).

`RawTableSchema` is a light dataclass holding what every warehouse can give us — nothing more. It is *not* the normalized internal representation.

## What goes in ingestion

- Iterating over the connector's raw reads
- Normalizing types (Postgres `VARCHAR` and BigQuery `STRING` both map to Datum's `string`)
- Sampling policy (how many rows, random vs stratified, truncation of long values)
- Producing the internal `SchemaSnapshot` — the rich representation the LLM and review UI will consume
- Storing snapshots in the app database for versioning

## Alternatives considered

**Fat connector, thin ingestion.** Each connector directly produces the normalized representation. Rejected because:
- Every new warehouse requires reimplementing normalization logic
- Normalization decisions (type mapping, sampling) get duplicated and drift
- Connector contracts become bloated and hard to test

**Unified connector with strategy pattern.** One giant `Connector` class with warehouse-specific strategies injected. Rejected as over-engineering for v0; we have one warehouse type.

## Consequences

**Positive:**
- Adding a new warehouse means writing ~200 lines of SQL-specific code, not reinventing ingestion
- Connectors are individually testable without any Datum-specific context
- Ingestion logic evolves in one place; improvements benefit all warehouses
- The `Protocol` contract makes it obvious what a connector must do

**Negative:**
- Two layers of abstraction instead of one; marginally more code to read
- Raw and normalized representations must both exist, and we have to be disciplined about which layer owns which concern

## Revisit when

- A specific warehouse has semantics that genuinely cannot be expressed through the protocol (rare; if it happens, extend the protocol rather than leak it into ingestion)
- We find ourselves putting warehouse-specific logic in ingestion — that's a smell pointing at the protocol being too narrow
