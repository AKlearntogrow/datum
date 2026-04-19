-- Runs against the default database (datum) at container initialization.
-- Enables pgvector for Datum's semantic embeddings.

CREATE EXTENSION IF NOT EXISTS vector;
