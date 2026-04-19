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
from src.storage.snapshots import (
    persist_snapshot,
    load_snapshot,
    snapshot_column_id_for,
)

__all__ = [
    "persist_snapshot",
    "load_snapshot",
    "snapshot_column_id_for",
    "list_entity_definitions",
    "persist_entity_proposals",
    "load_entity_definition",
    "approve_entity_definition",
    "reject_entity_definition",
    "reopen_entity_definition",
    "update_entity_definition",
]
