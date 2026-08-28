"""
Centralised error handling for the Kuberbolt REST API.

Defines:
- ErrorResponse -- the structured JSON body returned for all error responses.
- InvalidPrivkeyError -- custom exception for invalid nostr private key parsing.
- register_exception_handlers(app) -- wires global exception handlers onto the
  FastAPI app so routers can simply raise Python exceptions instead of
  constructing HTTPException objects.
"""

from __future__ import annotations

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("kuberbolt.api")


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: dict | None = None


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class InvalidPrivkeyError(ValueError):
    """Raised when a nostr private key cannot be parsed."""
    pass


class RelayUnavailableError(ConnectionError):
    """Raised when a relay connection cannot be established."""
    pass


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on *app*."""

    @app.exception_handler(InvalidPrivkeyError)
    async def _invalid_privkey_handler(request: Request, exc: InvalidPrivkeyError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error_code="INVALID_PRIVKEY",
                message=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(ValueError)
    async def _value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error_code="VALIDATION_ERROR",
                message=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(TimeoutError)
    async def _timeout_handler(request: Request, exc: TimeoutError) -> JSONResponse:
        return JSONResponse(
            status_code=408,
            content=ErrorResponse(
                error_code="TIMEOUT",
                message=str(exc) or "Request timed out",
            ).model_dump(),
        )

    @app.exception_handler(RelayUnavailableError)
    async def _relay_unavailable_handler(request: Request, exc: RelayUnavailableError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                error_code="RELAY_UNAVAILABLE",
                message=str(exc) or "Relay connection failed",
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def _catch_all_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log the full traceback server-side …
        logger.error(
            "Unhandled exception on %s %s:\n%s",
            request.method,
            request.url.path,
            traceback.format_exc(),
        )
        # … but never leak internals to the client.
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error_code="INTERNAL_ERROR",
                message="An unexpected error occurred.",
            ).model_dump(),
        )
