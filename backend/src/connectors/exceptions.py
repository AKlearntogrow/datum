"""Exception types raised by warehouse connectors.

Every connector raises these (or subclasses of them), never raw driver
exceptions. The ingestion layer catches these and converts them into
user-visible errors; it should not have to know about psycopg, bigquery
client errors, etc.
"""


class ConnectorError(Exception):
    """Base class for all connector-raised errors."""


class ConnectionFailed(ConnectorError):
    """The connector could not reach the warehouse at all."""


class PermissionDenied(ConnectorError):
    """The connection succeeded but the credentials lack required privileges."""


class TableNotFound(ConnectorError):
    """A requested table does not exist or is not visible to the credentials."""


class UnsupportedOperation(ConnectorError):
    """The connector does not support an operation (e.g., sampling from a view)."""
