"""Map internal exceptions to HTTP responses.

Keeps route handlers focused on the happy path. Each handler just raises
the semantic exception; the registered handlers below turn them into
properly-coded HTTP responses.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from src.connectors.exceptions import (
    ConnectionFailed,
    ConnectorError,
    PermissionDenied,
    TableNotFound,
)
from src.storage.data_sources import DataSourceStorageError
from src.storage.entities import EntityStorageError
from src.storage.scopes import ScopeStorageError


def _storage_error_status(message: str) -> int:
    """Map a storage error message to an HTTP status code.

    Shared heuristic used by all three storage-error handlers:
    - "not found" → 404
    - "Cannot delete" (FK conflict) → 409 Conflict
    - Everything else → 400
    """
    lower = message.lower()
    if "not found" in lower:
        return 404
    if "cannot delete" in lower:
        return 409
    return 400


def register_exception_handlers(app: FastAPI) -> None:
    """Register all our custom exception handlers on the FastAPI app.

    Called once from main.py. Centralizes error translation so route
    handlers never build HTTP responses for error cases themselves.
    """

    @app.exception_handler(EntityStorageError)
    async def _entity_storage_error(request: Request, exc: EntityStorageError) -> JSONResponse:
        message = str(exc)
        return JSONResponse(status_code=_storage_error_status(message), content={"error": message})

    @app.exception_handler(DataSourceStorageError)
    async def _data_source_storage_error(request: Request, exc: DataSourceStorageError) -> JSONResponse:
        message = str(exc)
        return JSONResponse(status_code=_storage_error_status(message), content={"error": message})

    @app.exception_handler(ScopeStorageError)
    async def _scope_storage_error(request: Request, exc: ScopeStorageError) -> JSONResponse:
        message = str(exc)
        return JSONResponse(status_code=_storage_error_status(message), content={"error": message})

    @app.exception_handler(ConnectionFailed)
    async def _connection_failed(request: Request, exc: ConnectionFailed) -> JSONResponse:
        return JSONResponse(status_code=502, content={"error": f"Warehouse connection failed: {exc}"})

    @app.exception_handler(PermissionDenied)
    async def _permission_denied(request: Request, exc: PermissionDenied) -> JSONResponse:
        return JSONResponse(status_code=502, content={"error": f"Warehouse permission denied: {exc}"})

    @app.exception_handler(TableNotFound)
    async def _table_not_found(request: Request, exc: TableNotFound) -> JSONResponse:
        return JSONResponse(status_code=502, content={"error": f"Warehouse table not found: {exc}"})

    @app.exception_handler(ConnectorError)
    async def _connector_error(request: Request, exc: ConnectorError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"error": f"Warehouse error: {exc}"})
