# ADR 0001: Initial Tech Stack

**Date:** 2026-04-18
**Status:** Accepted

## Context

We are building Datum, an AI-assisted semantic layer for messy data warehouses. The primary maintainer is not a strong coder. The project will eventually be handed off to engineers working on other projects. We need a stack that is:

1. Maintainable by a non-expert with AI coding assistance
2. Recognizable and conventional for professional engineers inheriting it later
3. Scalable enough to not require a rewrite when we get real customers
4. Boring — problems should be solvable by searching Stack Overflow

## Decisions

### Backend language: Python
Every data tool, LLM SDK, warehouse connector, and embedding library is Python-first. Fighting this is masochism.

### Backend framework: FastAPI
Modern, async, auto-generates OpenAPI docs, massive community. Django is overkill for an API-first service; Flask lacks modern async and type-hint support out of the box.

### Frontend: Next.js + TypeScript + Tailwind
The review UI is where non-technical users approve metric definitions — it has to feel like a product, not a demo. Next.js is the current default for serious web apps. TypeScript catches bugs at compile time. Tailwind avoids wasting time on CSS.

**Rejected alternative:** Streamlit. Faster to build v0, but looks like a demo forever. The "feels like a product" bar matters for this thesis.

### App database: Postgres
Boring, correct, scales for years before we need anything else.

### Vector store: pgvector (Postgres extension)
One less moving part — uses the same Postgres instance as the app database. Deliberate reversibility choice; easy to migrate to a dedicated vector DB (Pinecone, Weaviate, Qdrant) later if scale demands it.

### Target warehouse for v0: Postgres
BigQuery is where the real pain lives, but the auth/billing/service-account friction slows our tracer bullet significantly. Postgres with a realistic synthetic schema lets us build the entire pipeline end-to-end quickly. Connector architecture is designed so additional warehouses (BigQuery, Snowflake) can be added without changing anything downstream.

### LLM: Claude (Anthropic) with abstraction layer
Never hard-code to one provider. The abstraction lives in `backend/src/semantic/` and exposes a provider-agnostic interface.

### Orchestration: Plain Python scripts for now
No Airflow, Dagster, Temporal, or Celery yet. All overkill for v0. Add workflow orchestration when we have workflows that need it.

### Deployment: Docker + docker-compose locally; Railway or Render for staging
Not Kubernetes. Not raw AWS. Railway/Render is commit-to-URL in minutes. Production-grade cloud infrastructure is a year-one problem, not a day-one problem.

### Testing: pytest (backend), Vitest (frontend)
Standard tools. No novelty.

## Consequences

**Positive:**
- Every choice is conventional. New engineers recognize the stack immediately.
- Stack Overflow and documentation coverage is excellent for every component.
- No exotic dependencies that could become unmaintained.

**Negative:**
- Two languages in the repo (Python and TypeScript). Some context-switching overhead.
- pgvector has performance ceilings that dedicated vector DBs exceed — we accept this until it becomes a measured problem.
- Postgres-first for target warehouses means we cannot demo against real BigQuery data without additional work.

## Revisit when

- We have ≥3 paying customers and need to migrate staging → production infrastructure
- Vector search latency or quality becomes a measured bottleneck
- A target-customer conversation requires a non-Postgres warehouse connector before we're ready
