"""
Centralized exception handling for API endpoints.

Provides handlers for validation errors and runtime exceptions,
ensuring consistent error responses across all endpoints using
the unified APIError schema.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.models.errors import (
    APIError,
    ErrorCode,
    internal_error,
    request_timeout_error,
    session_expired_error,
    validation_error,
)

logger = logging.getLogger(__name__)


async def validation_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Return 422 with structured validation error details using APIError schema.

    Args:
        request: The incoming HTTP request
        exc: The validation exception (must be RequestValidationError)

    Returns:
        JSONResponse with validation error details
    """
    if not isinstance(exc, RequestValidationError):
        raise exc

    # Get first validation error for consistent error response
    errors = exc.errors()
    if errors:
        first_error = errors[0]
        field = ".".join(str(loc) for loc in first_error["loc"])
        message = first_error["msg"]

        api_error = validation_error(field=field, reason=message)
        return JSONResponse(status_code=422, content=api_error.to_dict())

    # Fallback for empty errors list
    api_error = APIError(
        code=ErrorCode.VALIDATION_ERROR,
        message="Validation failed",
        hint="Check the request format and try again",
    )
    return JSONResponse(status_code=422, content=api_error.to_dict())


def handle_endpoint_error(e: Exception, context: str) -> HTTPException:
    """
    Convert exceptions to safe HTTP responses with structured error details.

    Logs full error details server-side but returns safe messages to clients
    using the APIError schema to prevent information leakage.

    Args:
        e: The exception that occurred
        context: Description of the endpoint context for logging

    Returns:
        HTTPException with appropriate status code and APIError-formatted detail
    """
    # Pass through existing HTTPExceptions unchanged
    if isinstance(e, HTTPException):
        return e

    # Map common exceptions to APIError responses
    api_error: APIError

    if isinstance(e, TimeoutError):
        logger.warning(f"{context}: Timeout - {e}")
        api_error = request_timeout_error(detail=str(e))
        return HTTPException(status_code=504, detail=api_error.to_dict())

    if isinstance(e, RuntimeError):
        error_msg = str(e).lower()
        if "closed" in error_msg:
            logger.warning(f"{context}: Session closed - {e}")
            api_error = session_expired_error()
            return HTTPException(status_code=410, detail=api_error.to_dict())

    if isinstance(e, FileNotFoundError):
        logger.warning(f"{context}: File not found - {e}")
        from app.models.errors import file_not_found_error

        api_error = file_not_found_error(str(e))
        return HTTPException(status_code=404, detail=api_error.to_dict())

    if isinstance(e, ValueError):
        logger.warning(f"{context}: Value error - {e}")
        # Check for specific ValueError patterns
        error_str = str(e).lower()
        if "not found" in error_str:
            api_error = APIError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=str(e),
                hint="Verify the resource ID and try again",
            )
            return HTTPException(status_code=404, detail=api_error.to_dict())

        # Generic validation error for other ValueErrors
        api_error = APIError(
            code=ErrorCode.VALIDATION_ERROR,
            message=str(e),
            hint="Check the input parameters and try again",
        )
        return HTTPException(status_code=400, detail=api_error.to_dict())

    # Log full error details but don't expose to client
    logger.error(f"{context}: {type(e).__name__}: {e}", exc_info=True)
    api_error = internal_error(detail=type(e).__name__)
    return HTTPException(status_code=500, detail=api_error.to_dict())


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register exception handlers on the FastAPI app.

    Args:
        app: The FastAPI application instance
    """
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
