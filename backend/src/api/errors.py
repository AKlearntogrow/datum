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
from src.storage.entities import EntityStorageError


def register_exception_handlers(app: FastAPI) -> None:
    """Register all our custom exception handlers on the FastAPI app.

    Called once from main.py. Centralizes error translation so route
    handlers never build HTTP responses for error cases themselves.
    """

    @app.exception_handler(EntityStorageError)
    async def _entity_storage_error(request: Request, exc: EntityStorageError) -> JSONResponse:
        message = str(exc)
        # Heuristic: 'not found' phrasing maps to 404; state-transition errors to 400
        if "not found" in message.lower():
            status = 404
        else:
            status = 400
        return JSONResponse(status_code=status, content={"error": message})

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
