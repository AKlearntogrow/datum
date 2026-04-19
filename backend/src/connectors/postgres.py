"""Postgres implementation of the Connector protocol.

Uses psycopg (v3) to read schema metadata from information_schema and
sample data from the target tables. Knows only Postgres SQL — no Datum-
specific normalization logic.

See ADR 0004 (connector architecture).
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.connectors.exceptions import (
    ConnectionFailed,
    ConnectorError,
    PermissionDenied,
    TableNotFound,
)
from src.connectors.types import (
    RawColumn,
    RawTableSchema,
    SampleRows,
    TableRef,
)

# Schemas we always exclude — internal Postgres housekeeping, never business data.
_EXCLUDED_SCHEMAS = frozenset({
    "pg_catalog",
    "information_schema",
    "pg_toast",
})


class PostgresConnector:
    """Connector for Postgres databases (plain, RDS, Aurora, Neon, etc.).

    Construct cheaply with a connection URL. Network I/O happens only when
    methods are invoked. Each method opens and closes its own connection;
    there is no persistent state.
    """

    def __init__(self, connection_url: str) -> None:
        self._url = connection_url

    # --------------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------------

    def _connect(self) -> psycopg.Connection:
        """Open a new Postgres connection, translating driver errors
        into our ConnectorError hierarchy."""
        try:
            return psycopg.connect(self._url)
        except psycopg.OperationalError as exc:
            msg = str(exc).lower()
            if "authentication" in msg or "password" in msg or "role" in msg:
                raise PermissionDenied(f"Authentication failed: {exc}") from exc
            raise ConnectionFailed(f"Could not connect to Postgres: {exc}") from exc
        except psycopg.Error as exc:
            raise ConnectorError(f"Unexpected psycopg error: {exc}") from exc

    @staticmethod
    def _current_database(conn: psycopg.Connection) -> str:
        """Return the name of the database the connection is attached to."""
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            row = cur.fetchone()
            assert row is not None
            return str(row[0])

    # --------------------------------------------------------------
    # Connector protocol methods
    # --------------------------------------------------------------

    def list_tables(self) -> list[TableRef]:
        """Return every base table the current credentials can see.

        Excludes views, foreign tables, and system schemas. Ordered by
        schema then name for stable output.
        """
        sql = """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_schema != ALL(%s)
            ORDER BY table_schema, table_name
        """
        with self._connect() as conn:
            database = self._current_database(conn)
            with conn.cursor() as cur:
                cur.execute(sql, (list(_EXCLUDED_SCHEMAS),))
                rows = cur.fetchall()
        return [
            TableRef(database=database, schema=schema, name=name)
            for schema, name in rows
        ]

    def describe_table(self, ref: TableRef) -> RawTableSchema:
        """Return the full column list and PK info for a single table.

        Raises TableNotFound if the table doesn't exist or isn't visible.
        """
        column_sql = """
            SELECT
                column_name,
                data_type,
                is_nullable,
                ordinal_position,
                col_description(
                    format('%%I.%%I', table_schema, table_name)::regclass::oid,
                    ordinal_position
                ) AS column_comment
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        pk_sql = """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = %s
              AND tc.table_name = %s
            ORDER BY kcu.ordinal_position
        """
        table_comment_sql = """
            SELECT obj_description(c.oid, 'pg_class')
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s
        """
        rowcount_sql = """
            SELECT reltuples::bigint AS approx_rowcount
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s AND c.relkind = 'r'
        """

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(column_sql, (ref.schema, ref.name))
                column_rows = cur.fetchall()
                if not column_rows:
                    raise TableNotFound(
                        f"Table {ref.qualified} does not exist or is not visible"
                    )

                cur.execute(pk_sql, (ref.schema, ref.name))
                pk_rows = cur.fetchall()

                cur.execute(table_comment_sql, (ref.schema, ref.name))
                table_comment_row = cur.fetchone()

                cur.execute(rowcount_sql, (ref.schema, ref.name))
                rowcount_row = cur.fetchone()

        columns = [
            RawColumn(
                name=name,
                data_type=data_type,
                is_nullable=(is_nullable == "YES"),
                ordinal_position=ordinal,
                comment=comment,
            )
            for (name, data_type, is_nullable, ordinal, comment) in column_rows
        ]
        primary_key_columns = [r[0] for r in pk_rows]
        table_comment = table_comment_row[0] if table_comment_row else None
        # pg_class.reltuples returns -1 when ANALYZE has never run.
        # Treat that as "unknown" (None) rather than propagating the sentinel.
        if rowcount_row and rowcount_row[0] is not None and int(rowcount_row[0]) >= 0:
            row_estimate = int(rowcount_row[0])
        else:
            row_estimate = None

        return RawTableSchema(
            ref=ref,
            columns=columns,
            primary_key_columns=primary_key_columns,
            row_count_estimate=row_estimate,
            comment=table_comment,
        )

    def sample_rows(self, ref: TableRef, limit: int) -> SampleRows:
        """Return up to `limit` rows from the table.

        Uses a plain ORDER BY random() LIMIT query. For v0 this is fine —
        tables are small. A TABLESAMPLE-based strategy is a future optimization.

        Truncated flag reflects whether the table had more rows than the limit,
        based on the cheap pg_class estimate.
        """
        if limit <= 0:
            raise ValueError("limit must be positive")

        # Use format() for the identifier because parameters can't bind table names.
        # We've already validated the table exists via describe_table in normal flow,
        # but we still verify existence cheaply here.
        check_sql = """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s AND table_type = 'BASE TABLE'
        """
        sample_sql = (
            f'SELECT * FROM "{ref.schema}"."{ref.name}" '
            f"ORDER BY random() LIMIT %s"
        )

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(check_sql, (ref.schema, ref.name))
                if cur.fetchone() is None:
                    raise TableNotFound(
                        f"Table {ref.qualified} does not exist or is not a base table"
                    )

            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sample_sql, (limit,))
                rows: list[dict[str, Any]] = list(cur.fetchall())

            # Figure out truncation. pg_class.reltuples is cheap but returns -1
            # before ANALYZE has run. In that case, fall back to a bounded COUNT(*)
            # — bounded so we don't scan a billion-row table just to answer this.
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT reltuples::bigint
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = %s AND c.relname = %s
                    """,
                    (ref.schema, ref.name),
                )
                estimate_row = cur.fetchone()
                raw_estimate = int(estimate_row[0]) if estimate_row and estimate_row[0] is not None else -1

            if raw_estimate < 0:
                # ANALYZE never ran. Do a bounded count: look for one row beyond
                # the sample to confirm "more rows exist" without a full scan.
                probe_sql = (
                    f'SELECT 1 FROM "{ref.schema}"."{ref.name}" '
                    f"OFFSET %s LIMIT 1"
                )
                with conn.cursor() as cur:
                    cur.execute(probe_sql, (len(rows),))
                    truncated = cur.fetchone() is not None
            else:
                truncated = raw_estimate > len(rows)
        return SampleRows(
            ref=ref,
            rows=rows,
            requested_limit=limit,
            truncated=truncated,
        )
