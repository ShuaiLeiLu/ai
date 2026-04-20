"""Global exception handlers for the FastAPI application.

Ensures that all unhandled exceptions return a consistent JSON response
matching the ``{"success": false, "data": null, "detail": ...}`` contract.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach global exception handlers to *app*."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "data": None, "detail": exc.detail},
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(_request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"success": False, "data": None, "detail": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "data": None, "detail": "服务器内部错误，请稍后重试"},
        )
