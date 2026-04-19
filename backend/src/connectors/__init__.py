"""Warehouse connectors. See ADR 0004 for architecture.

Each concrete connector (PostgresConnector, BigQueryConnector, ...) lives
in its own module. They share a single protocol defined in `base.py`.
"""

from src.connectors.base import Connector
from src.connectors.exceptions import (
    ConnectionFailed,
    ConnectorError,
    PermissionDenied,
    TableNotFound,
    UnsupportedOperation,
)
from src.connectors.postgres import PostgresConnector
from src.connectors.types import RawColumn, RawTableSchema, SampleRows, TableRef

__all__ = [
    "Connector",
    "ConnectorError",
    "ConnectionFailed",
    "PermissionDenied",
    "TableNotFound",
    "UnsupportedOperation",
    "PostgresConnector",
    "TableRef",
    "RawColumn",
    "RawTableSchema",
    "SampleRows",
]
