"""Tests for scopes storage functions.

Runs against the real app database with rollback-per-test isolation.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from src.models.snapshots import SchemaSnapshot as SchemaSnapshotORM
from src.storage.data_sources import create_data_source
from src.storage.scopes import (
    ScopeStorageError,
    create_scope,
    delete_scope,
    list_scopes,
    load_scope,
    update_scope,
    validate_included_schemas,
)

AVAILABLE = ["sales_cloud", "finance_mart", "product_analytics", "legacy_erp"]


# ----------------------------------------------------------------------
# validate_included_schemas (pure function, no db)
# ----------------------------------------------------------------------

class TestValidateIncludedSchemas:
    def test_passes_on_valid_subset(self) -> None:
        validate_included_schemas(["sales_cloud", "finance_mart"], AVAILABLE)

    def test_passes_on_full_set(self) -> None:
        validate_included_schemas(AVAILABLE, AVAILABLE)

    def test_raises_on_missing_schema(self) -> None:
        with pytest.raises(ScopeStorageError, match="not present in data source"):
            validate_included_schemas(["sales_cloud", "nonexistent"], AVAILABLE)

    def test_error_lists_all_missing(self) -> None:
        with pytest.raises(ScopeStorageError, match="foo.*bar|bar.*foo"):
            validate_included_schemas(["foo", "bar"], AVAILABLE)

    def test_raises_on_empty(self) -> None:
        with pytest.raises(ScopeStorageError, match="must not be empty"):
            validate_included_schemas([], AVAILABLE)

    def test_case_sensitive(self) -> None:
        with pytest.raises(ScopeStorageError, match="not present"):
            validate_included_schemas(["Sales_Cloud"], AVAILABLE)


# ----------------------------------------------------------------------
# create_scope
# ----------------------------------------------------------------------

class TestCreateScope:
    def test_creates_with_jsonb_roundtrip(self, db: Session) -> None:
        ds = create_data_source(db, name="DS", warehouse_type="postgres", connection_url="x")
        scope = create_scope(db, data_source_id=ds.id, name="Test",
                             included_schemas=["sales_cloud", "finance_mart"],
                             available_schemas=AVAILABLE)
        assert scope.id is not None
        assert scope.included_schemas == ["sales_cloud", "finance_mart"]
        assert scope.excluded_tables is None
        assert scope.data_source_id == ds.id

    def test_raises_on_missing_data_source(self, db: Session) -> None:
        with pytest.raises(ScopeStorageError, match="not found"):
            create_scope(db, data_source_id="nonexistent", name="S",
                         included_schemas=["public"], available_schemas=["public"])

    def test_raises_on_invalid_schema(self, db: Session) -> None:
        ds = create_data_source(db, name="DS", warehouse_type="postgres", connection_url="x")
        with pytest.raises(ScopeStorageError, match="not present"):
            create_scope(db, data_source_id=ds.id, name="Bad",
                         included_schemas=["nonexistent"],
                         available_schemas=AVAILABLE)


# ----------------------------------------------------------------------
# list_scopes
# ----------------------------------------------------------------------

class TestListScopes:
    def test_filtered_by_data_source(self, db: Session) -> None:
        ds1 = create_data_source(db, name="DS1", warehouse_type="postgres", connection_url="a")
        ds2 = create_data_source(db, name="DS2", warehouse_type="postgres", connection_url="b")
        create_scope(db, data_source_id=ds1.id, name="S1",
                     included_schemas=["sales_cloud"], available_schemas=AVAILABLE)
        create_scope(db, data_source_id=ds2.id, name="S2",
                     included_schemas=["finance_mart"], available_schemas=AVAILABLE)
        result = list_scopes(db, data_source_id=ds1.id)
        assert len(result) == 1
        assert result[0].name == "S1"


# ----------------------------------------------------------------------
# load_scope
# ----------------------------------------------------------------------

class TestLoadScope:
    def test_returns_none_for_missing(self, db: Session) -> None:
        assert load_scope(db, "00000000-0000-0000-0000-000000000000") is None


# ----------------------------------------------------------------------
# delete_scope
# ----------------------------------------------------------------------

class TestDeleteScope:
    def test_deletes_existing(self, db: Session) -> None:
        ds = create_data_source(db, name="DS", warehouse_type="postgres", connection_url="x")
        scope = create_scope(db, data_source_id=ds.id, name="Del",
                             included_schemas=["sales_cloud"], available_schemas=AVAILABLE)
        delete_scope(db, scope.id)
        assert load_scope(db, scope.id) is None

    def test_raises_on_missing(self, db: Session) -> None:
        with pytest.raises(ScopeStorageError, match="not found"):
            delete_scope(db, "nonexistent-id")

    def test_raises_when_snapshots_reference(self, db: Session) -> None:
        """Create a data source → scope → snapshot referencing the scope,
        then try to delete the scope. Should fail with a clear message."""
        from datetime import datetime, timezone

        ds = create_data_source(db, name="DS", warehouse_type="postgres", connection_url="x")
        scope = create_scope(db, data_source_id=ds.id, name="Blocked",
                             included_schemas=["sales_cloud"], available_schemas=AVAILABLE)
        # Manually insert a snapshot referencing this scope
        snap = SchemaSnapshotORM(
            captured_at=datetime.now(timezone.utc),
            source_database="test",
            scope_id=scope.id,
        )
        db.add(snap)
        db.flush()

        with pytest.raises(ScopeStorageError, match=r"1 snapshot\(s\)"):
            delete_scope(db, scope.id)


# ----------------------------------------------------------------------
# update_scope
# ----------------------------------------------------------------------

class TestUpdateScope:
    def test_updates_name_and_description(self, db: Session) -> None:
        ds = create_data_source(db, name="DS", warehouse_type="postgres", connection_url="x")
        scope = create_scope(db, data_source_id=ds.id, name="Original",
                             included_schemas=["sales_cloud"], available_schemas=AVAILABLE,
                             description="Old desc")
        updated = update_scope(db, scope.id, {"name": "Renamed", "description": "New desc"})
        assert updated.name == "Renamed"
        assert updated.description == "New desc"
        # included_schemas unchanged
        assert updated.included_schemas == ["sales_cloud"]

    def test_ignores_included_schemas(self, db: Session) -> None:
        ds = create_data_source(db, name="DS", warehouse_type="postgres", connection_url="x")
        scope = create_scope(db, data_source_id=ds.id, name="S",
                             included_schemas=["sales_cloud"], available_schemas=AVAILABLE)
        updated = update_scope(db, scope.id, {"included_schemas": ["hacked"], "name": "Ok"})
        assert updated.included_schemas == ["sales_cloud"]  # not changed
        assert updated.name == "Ok"  # name was in the allowlist

    def test_raises_on_missing(self, db: Session) -> None:
        with pytest.raises(ScopeStorageError, match="not found"):
            update_scope(db, "nonexistent", {"name": "x"})
