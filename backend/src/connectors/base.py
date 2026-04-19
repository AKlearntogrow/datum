"""The Connector protocol — the contract every warehouse adapter must fulfill.

Uses `typing.Protocol` rather than an abstract base class so implementations
don't need to inherit from a common parent. A connector is anything that
exposes these method signatures.

See ADR 0004 (connector architecture) for the reasoning. In short:
connectors stay thin — they expose raw reads only. Normalization,
sampling policy, and all warehouse-agnostic logic belong in the
ingestion layer, not here.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.connectors.types import RawTableSchema, SampleRows, TableRef


@runtime_checkable
class Connector(Protocol):
    """Every warehouse connector must provide exactly these operations.

    Implementations should:
    - Raise subclasses of `ConnectorError` for any failure — never leak
      driver-specific exceptions.
    - Be safe to construct without immediately connecting. Actual network
      I/O should happen inside the methods below, not in `__init__`.
    - Be stateless with respect to cursors — each call opens and closes
      its own connection (or uses a pool).
    """

    def list_tables(self) -> list[TableRef]:
        """Return every table the current credentials can see.

        Excludes views by default (v0 scope). System schemas like
        `information_schema` and `pg_catalog` are also excluded.
        """
        ...

    def describe_table(self, ref: TableRef) -> RawTableSchema:
        """Return the full column list and PK info for a single table.

        Raises `TableNotFound` if the table does not exist or is not visible.
        """
        ...

    def sample_rows(self, ref: TableRef, limit: int) -> SampleRows:
        """Return up to `limit` rows from the table.

        The connector decides the sampling strategy internally (random,
        top-N, etc.) — that's a connector-specific detail. The caller only
        guarantees that `limit` will be small (typically ≤ 100).

        `SampleRows.truncated` is True if the table had more rows than
        `limit`, False otherwise.
        """
        ...
