"""Tests for the admin API endpoints (data sources + scopes).

Uses FastAPI's TestClient against the real app and database.
Tests that mutate state use rollback isolation via the db fixture.
Tests that need a real warehouse connection use the messy_warehouse_url fixture.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app

MESSY_WAREHOUSE_URL_DEFAULT = (
    "postgresql://datum:datum_dev_password@localhost:5432/messy_warehouse"
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ----------------------------------------------------------------------
# Data source endpoints
# ----------------------------------------------------------------------

class TestDataSourceCreate:
    def test_creates_and_returns(self, client: TestClient) -> None:
        r = client.post("/api/admin/data-sources", json={
            "name": "Test PG",
            "warehouse_type": "postgres",
            "connection_url": "postgresql://x@localhost/test",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Test PG"
        assert body["warehouse_type"] == "postgres"
        assert body["connection_url"] == "postgresql://x@localhost/test"
        assert body["id"] is not None
        assert body["created_by"] == "local_user"
        # Cleanup: delete so we don't pollute
        client.delete(f"/api/admin/data-sources/{body['id']}")


class TestDataSourceList:
    def test_returns_list(self, client: TestClient) -> None:
        r = client.post("/api/admin/data-sources", json={
            "name": "ListTest",
            "warehouse_type": "postgres",
            "connection_url": "postgresql://x@localhost/test",
        })
        ds_id = r.json()["id"]
        r = client.get("/api/admin/data-sources")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 1
        assert any(d["id"] == ds_id for d in body["items"])
        client.delete(f"/api/admin/data-sources/{ds_id}")


class TestDataSourceGet:
    def test_unknown_id_returns_404(self, client: TestClient) -> None:
        r = client.get("/api/admin/data-sources/nonexistent-id")
        assert r.status_code == 404


class TestDataSourceDelete:
    def test_unknown_id_returns_404(self, client: TestClient) -> None:
        r = client.delete("/api/admin/data-sources/nonexistent-id")
        assert r.status_code == 404

    def test_with_dependent_scope_returns_409(self, client: TestClient, messy_warehouse_url: str) -> None:
        # Create a data source pointing at the real warehouse
        r = client.post("/api/admin/data-sources", json={
            "name": "BlockedDelete",
            "warehouse_type": "postgres",
            "connection_url": messy_warehouse_url,
        })
        ds_id = r.json()["id"]
        # Create a scope on it
        r = client.post("/api/admin/scopes", json={
            "data_source_id": ds_id,
            "name": "Blocking Scope",
            "included_schemas": ["sales_cloud"],
        })
        scope_id = r.json()["id"]
        # Try to delete the data source — should fail with 409
        r = client.delete(f"/api/admin/data-sources/{ds_id}")
        assert r.status_code == 409
        assert "scope" in r.json()["error"].lower()
        # Cleanup
        client.delete(f"/api/admin/scopes/{scope_id}")
        client.delete(f"/api/admin/data-sources/{ds_id}")


# ----------------------------------------------------------------------
# Scope endpoints
# ----------------------------------------------------------------------

class TestScopeCreate:
    def test_success_path(self, client: TestClient, messy_warehouse_url: str) -> None:
        """Full success: create data source → create scope with real schema validation."""
        r = client.post("/api/admin/data-sources", json={
            "name": "Scope Test DS",
            "warehouse_type": "postgres",
            "connection_url": messy_warehouse_url,
        })
        ds_id = r.json()["id"]
        r = client.post("/api/admin/scopes", json={
            "data_source_id": ds_id,
            "name": "Sales Only",
            "included_schemas": ["sales_cloud"],
        })
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Sales Only"
        assert body["included_schemas"] == ["sales_cloud"]
        assert body["data_source_id"] == ds_id
        # Cleanup
        client.delete(f"/api/admin/scopes/{body['id']}")
        client.delete(f"/api/admin/data-sources/{ds_id}")

    def test_invalid_schema_returns_400(self, client: TestClient, messy_warehouse_url: str) -> None:
        r = client.post("/api/admin/data-sources", json={
            "name": "Invalid Schema DS",
            "warehouse_type": "postgres",
            "connection_url": messy_warehouse_url,
        })
        ds_id = r.json()["id"]
        r = client.post("/api/admin/scopes", json={
            "data_source_id": ds_id,
            "name": "Bad",
            "included_schemas": ["nonexistent_schema"],
        })
        assert r.status_code == 400
        assert "nonexistent_schema" in r.json()["error"]
        client.delete(f"/api/admin/data-sources/{ds_id}")

    def test_unknown_data_source_returns_404(self, client: TestClient) -> None:
        r = client.post("/api/admin/scopes", json={
            "data_source_id": "nonexistent-ds-id",
            "name": "S",
            "included_schemas": ["public"],
        })
        assert r.status_code == 404


class TestScopeUpdate:
    def test_updates_name_only(self, client: TestClient, messy_warehouse_url: str) -> None:
        r = client.post("/api/admin/data-sources", json={
            "name": "Update DS",
            "warehouse_type": "postgres",
            "connection_url": messy_warehouse_url,
        })
        ds_id = r.json()["id"]
        r = client.post("/api/admin/scopes", json={
            "data_source_id": ds_id,
            "name": "Before",
            "included_schemas": ["sales_cloud"],
        })
        scope_id = r.json()["id"]
        r = client.patch(f"/api/admin/scopes/{scope_id}", json={"name": "After"})
        assert r.status_code == 200
        assert r.json()["name"] == "After"
        assert r.json()["included_schemas"] == ["sales_cloud"]  # unchanged
        # Cleanup
        client.delete(f"/api/admin/scopes/{scope_id}")
        client.delete(f"/api/admin/data-sources/{ds_id}")


class TestScopeDelete:
    def test_unknown_id_returns_404(self, client: TestClient) -> None:
        r = client.delete("/api/admin/scopes/nonexistent-id")
        assert r.status_code == 404
