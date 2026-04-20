"""Tests for data_sources storage functions.

Runs against the real app database with rollback-per-test isolation.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from src.storage.data_sources import (
    DataSourceStorageError,
    create_data_source,
    delete_data_source,
    list_data_sources,
    load_data_source,
)
from src.storage.scopes import create_scope


class TestCreateDataSource:
    def test_creates_with_populated_id(self, db: Session) -> None:
        ds = create_data_source(db, name="Test", warehouse_type="postgres",
                                connection_url="postgresql://x@localhost/test")
        assert ds.id is not None
        assert len(ds.id) == 36  # UUID format
        assert ds.name == "Test"
        assert ds.warehouse_type == "postgres"
        assert ds.connection_url == "postgresql://x@localhost/test"
        assert ds.created_by == "local_user"
        assert ds.created_at is not None

    def test_description_defaults_to_none(self, db: Session) -> None:
        ds = create_data_source(db, name="T", warehouse_type="postgres",
                                connection_url="postgresql://x@localhost/t")
        assert ds.description is None

    def test_custom_created_by(self, db: Session) -> None:
        ds = create_data_source(db, name="T", warehouse_type="postgres",
                                connection_url="x", created_by="admin")
        assert ds.created_by == "admin"


class TestListDataSources:
    def test_returns_results(self, db: Session) -> None:
        """Verify list_data_sources returns created data sources.
        Ordering within a single transaction is indeterminate because
        server_default=now() produces the same timestamp, so we just
        verify both appear."""
        ds1 = create_data_source(db, name="First", warehouse_type="postgres", connection_url="a")
        ds2 = create_data_source(db, name="Second", warehouse_type="postgres", connection_url="b")
        result = list_data_sources(db)
        ids = {d.id for d in result}
        assert ds1.id in ids
        assert ds2.id in ids


class TestLoadDataSource:
    def test_returns_none_for_missing(self, db: Session) -> None:
        assert load_data_source(db, "00000000-0000-0000-0000-000000000000") is None


class TestDeleteDataSource:
    def test_deletes_existing(self, db: Session) -> None:
        ds = create_data_source(db, name="Del", warehouse_type="postgres", connection_url="x")
        delete_data_source(db, ds.id)
        assert load_data_source(db, ds.id) is None

    def test_raises_on_missing(self, db: Session) -> None:
        with pytest.raises(DataSourceStorageError, match="not found"):
            delete_data_source(db, "nonexistent-id")

    def test_raises_with_count_when_scopes_exist(self, db: Session) -> None:
        ds = create_data_source(db, name="Has Scopes", warehouse_type="postgres",
                                connection_url="x")
        create_scope(db, data_source_id=ds.id, name="S1",
                     included_schemas=["public"], available_schemas=["public"])
        with pytest.raises(DataSourceStorageError, match=r"1 scope\(s\) still reference it"):
            delete_data_source(db, ds.id)
