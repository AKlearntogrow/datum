# Datum

An AI-assisted semantic layer for messy data warehouses.

**The pitch:** You don't need a data engineer to define your metrics. Point Datum at your warehouse and it drafts the semantic layer for you to review.

## Status

🚧 Early development. Tracer bullet phase. Not ready for use.

## Architecture

- **Backend:** Python + FastAPI
- **Frontend:** Next.js + TypeScript + Tailwind
- **App database:** Postgres with pgvector
- **Target warehouse (v0):** Postgres (BigQuery/Snowflake to follow)
- **LLM:** Claude (Anthropic), with provider-agnostic abstraction

See `docs/decisions/` for architecture decision records explaining why.

## Project structure

```
datum/
├── backend/          Python FastAPI app
│   ├── src/
│   │   ├── api/          HTTP routes
│   │   ├── core/         Config, settings, logging
│   │   ├── connectors/   Warehouse connectors
│   │   ├── ingestion/    Schema crawling & data sampling
│   │   ├── semantic/     LLM-assisted metric/entity proposal
│   │   ├── review/       Human approval workflow
│   │   ├── query/        Semantic definition → SQL
│   │   ├── models/       SQLAlchemy ORM models
│   │   └── schemas/      Pydantic request/response schemas
│   ├── tests/
│   └── alembic/          Database migrations
├── frontend/         Next.js review UI
├── synthetic_data/   Scripts to generate messy test warehouses
└── docs/
    └── decisions/    Architecture decision records (ADRs)
```

## Getting started

TODO — will fill in as we build.

## License

TBD
