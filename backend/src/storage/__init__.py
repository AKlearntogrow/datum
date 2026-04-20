"""Storage layer — functions that read/write ORM models.

Each function takes an SQLAlchemy Session and does one thing. Callers
own the transaction (commit/rollback). This keeps the storage layer
testable and lets multiple writes compose into one transaction.
"""

from src.storage.entities import (
    list_entity_definitions,
    persist_entity_proposals,
    load_entity_definition,
    approve_entity_definition,
    reject_entity_definition,
    reopen_entity_definition,
    update_entity_definition,
)
from src.storage.data_sources import (
    create_data_source,
    list_data_sources,
    load_data_source,
    delete_data_source,
)
from src.storage.snapshots import (
    persist_snapshot,
    load_snapshot,
    load_most_recent_snapshot,
    snapshot_column_id_for,
)

__all__ = [
    "create_data_source",
    "list_data_sources",
    "load_data_source",
    "delete_data_source",
    "persist_snapshot",
    "load_snapshot",
    "load_most_recent_snapshot",
    "snapshot_column_id_for",
    "list_entity_definitions",
    "persist_entity_proposals",
    "load_entity_definition",
    "approve_entity_definition",
    "reject_entity_definition",
    "reopen_entity_definition",
    "update_entity_definition",
]
