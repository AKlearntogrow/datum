"""Raw data shapes exchanged between connectors and the ingestion layer.

These types are warehouse-agnostic in *shape* but reflect only what every
warehouse can give us natively — table names, columns, types, nullability,
and a limited sample of rows. They are NOT Datum's normalized internal
representation (that lives in src/ingestion/).

Keep this file free of SQL, LLM calls, or ORM imports. Pure dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TableRef:
    """Fully qualified reference to a table in a source warehouse.

    Using all three parts (database, schema, name) means this type works
    unchanged across Postgres, BigQuery (project.dataset.table),
    Snowflake (database.schema.table), and others.
    """

    database: str
    schema: str
    name: str

    @property
    def qualified(self) -> str:
        """Human-readable 'database.schema.table' form for logs and UI."""
        return f"{self.database}.{self.schema}.{self.name}"


@dataclass(frozen=True)
class RawColumn:
    """Column metadata as read directly from the warehouse's information schema.

    Deliberately minimal — only fields every mainstream warehouse exposes.
    Richer semantic inference (what the column *means*) happens in ingestion,
    not here.
    """

    name: str
    data_type: str           # native warehouse type string, e.g., "numeric", "varchar"
    is_nullable: bool
    ordinal_position: int    # 1-based position in the table
    comment: str | None = None  # native DB comment if any; usually None for our demo


@dataclass
class RawTableSchema:
    """The information a connector returns about a single table.

    `primary_key_columns` lists column names (not RawColumn objects) because
    that's how the warehouse reports it and we don't want to force a lookup.
    """

    ref: TableRef
    columns: list[RawColumn]
    primary_key_columns: list[str] = field(default_factory=list)
    row_count_estimate: int | None = None  # approximate count; None if too expensive to compute
    comment: str | None = None              # native DB comment on the table, if any


@dataclass
class SampleRows:
    """A sample of rows from a table, returned as plain dicts.

    Kept as dicts rather than typed records because different warehouses
    return different Python types for NUMERIC, TIMESTAMP, etc. — normalization
    is ingestion's job, not the connector's.
    """

    ref: TableRef
    rows: list[dict[str, Any]]
    requested_limit: int   # what we asked for
    truncated: bool = False  # True if the table had more rows than requested_limit
