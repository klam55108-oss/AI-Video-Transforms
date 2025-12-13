"""
Centralized exception handling for API endpoints.

Provides handlers for validation errors and runtime exceptions,
ensuring consistent error responses across all endpoints.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def validation_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Return 422 with structured validation error details.

    Args:
        request: The incoming HTTP request
        exc: The validation exception (must be RequestValidationError)

    Returns:
        JSONResponse with validation error details
    """
    if not isinstance(exc, RequestValidationError):
        raise exc
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({"field": field, "message": error["msg"]})

    return JSONResponse(
        status_code=422, content={"detail": "Validation error", "errors": errors}
    )


def handle_endpoint_error(e: Exception, context: str) -> HTTPException:
    """
    Convert exceptions to safe HTTP responses.

    Logs full error details server-side but returns
    generic messages to clients to prevent information leakage.

    Args:
        e: The exception that occurred
        context: Description of the endpoint context for logging

    Returns:
        HTTPException with appropriate status code and safe message
    """
    if isinstance(e, HTTPException):
        return e

    if isinstance(e, TimeoutError):
        logger.warning(f"{context}: Timeout - {e}")
        return HTTPException(
            status_code=504, detail="Request timed out. Please try again."
        )

    if isinstance(e, RuntimeError):
        error_msg = str(e).lower()
        if "closed" in error_msg:
            logger.warning(f"{context}: Session closed - {e}")
            return HTTPException(status_code=410, detail="Session is closed")

    # Log full error details but don't expose to client
    logger.error(f"{context}: {type(e).__name__}: {e}", exc_info=True)
    return HTTPException(
        status_code=500, detail="An internal error occurred. Please try again."
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register exception handlers on the FastAPI app.

    Args:
        app: The FastAPI application instance
    """
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
