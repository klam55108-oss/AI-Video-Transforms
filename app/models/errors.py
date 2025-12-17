"""
Unified error schema for the VideoAgent API.

Provides consistent error codes, messages, and hints for all API responses.
All errors include retryability information and optional debugging details.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCode(str, Enum):
    """Standardized error codes for API responses."""

    # Transcription errors (TRANSCRIPTION_*)
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    FFMPEG_NOT_FOUND = "FFMPEG_NOT_FOUND"
    TRANSCRIPTION_FAILED = "TRANSCRIPTION_FAILED"
    TRANSCRIPTION_TIMEOUT = "TRANSCRIPTION_TIMEOUT"

    # Knowledge Graph errors (KG_*)
    BOOTSTRAP_FAILED = "BOOTSTRAP_FAILED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    INVALID_PROJECT_STATE = "INVALID_PROJECT_STATE"

    # Session errors (SESSION_*)
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_CLOSED = "SESSION_CLOSED"

    # Resource errors (RESOURCE_*)
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"

    # Validation errors (VALIDATION_*)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_FORMAT = "INVALID_FORMAT"

    # Rate limiting and capacity errors
    RATE_LIMITED = "RATE_LIMITED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    REQUEST_TIMEOUT = "REQUEST_TIMEOUT"

    # Generic errors
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass
class APIError:
    """
    Structured error response for API endpoints.

    Attributes:
        code: Standardized error code from ErrorCode enum
        message: Human-readable error message
        detail: Optional technical details for debugging
        hint: Optional suggestion for resolving the error
        retryable: Whether the client should retry the request
    """

    code: ErrorCode
    message: str
    detail: str | None = None
    hint: str | None = None
    retryable: bool = False

    def to_dict(self) -> dict[str, dict[str, str | bool]]:
        """
        Convert error to dictionary format for JSON responses.

        Returns:
            Dictionary with 'error' key containing error details
        """
        error_dict: dict[str, str | bool] = {
            "code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
        }

        if self.detail is not None:
            error_dict["detail"] = self.detail

        if self.hint is not None:
            error_dict["hint"] = self.hint

        return {"error": error_dict}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Predefined Error Factories
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def transcription_timeout_error(detail: str | None = None) -> APIError:
    """Create error for transcription timeout."""
    return APIError(
        code=ErrorCode.TRANSCRIPTION_TIMEOUT,
        message="Transcription operation timed out",
        detail=detail,
        hint="Try again with a shorter video or audio file",
        retryable=True,
    )


def ffmpeg_not_found_error() -> APIError:
    """Create error for missing FFmpeg."""
    return APIError(
        code=ErrorCode.FFMPEG_NOT_FOUND,
        message="FFmpeg is not installed or not found in PATH",
        detail="Audio extraction requires FFmpeg",
        hint="Install FFmpeg to enable video transcription",
        retryable=False,
    )


def project_not_found_error(project_id: str) -> APIError:
    """Create error for missing KG project."""
    return APIError(
        code=ErrorCode.PROJECT_NOT_FOUND,
        message="Knowledge graph project not found",
        detail=f"Project ID: {project_id}",
        hint="Check the project ID or create a new project",
        retryable=False,
    )


def invalid_project_state_error(current_state: str, required_state: str) -> APIError:
    """Create error for invalid project state."""
    return APIError(
        code=ErrorCode.INVALID_PROJECT_STATE,
        message=f"Project is in '{current_state}' state, expected '{required_state}'",
        detail=f"Current state: {current_state}, Required: {required_state}",
        hint="Wait for the current operation to complete or check project status",
        retryable=False,
    )


def session_not_found_error(session_id: str) -> APIError:
    """Create error for missing session."""
    return APIError(
        code=ErrorCode.SESSION_NOT_FOUND,
        message="Session not found",
        detail=f"Session ID: {session_id}",
        hint="The session may have expired. Start a new session.",
        retryable=False,
    )


def session_expired_error() -> APIError:
    """Create error for expired session."""
    return APIError(
        code=ErrorCode.SESSION_EXPIRED,
        message="Session has expired",
        detail="Sessions expire after 1 hour of inactivity",
        hint="Click 'New Chat' to start a fresh conversation",
        retryable=False,
    )


def validation_error(field: str, reason: str) -> APIError:
    """Create error for validation failures."""
    return APIError(
        code=ErrorCode.VALIDATION_ERROR,
        message=f"Validation failed for field: {field}",
        detail=reason,
        hint="Check the input format and try again",
        retryable=False,
    )


def service_unavailable_error(detail: str | None = None) -> APIError:
    """Create error for service unavailability."""
    return APIError(
        code=ErrorCode.SERVICE_UNAVAILABLE,
        message="Service temporarily unavailable",
        detail=detail,
        hint="Please try again in a moment",
        retryable=True,
    )


def request_timeout_error(detail: str | None = None) -> APIError:
    """Create error for request timeout."""
    return APIError(
        code=ErrorCode.REQUEST_TIMEOUT,
        message="Request timed out",
        detail=detail,
        hint="Please try again",
        retryable=True,
    )


def internal_error(detail: str | None = None) -> APIError:
    """Create generic internal error."""
    return APIError(
        code=ErrorCode.INTERNAL_ERROR,
        message="An internal error occurred",
        detail=detail,
        hint="Please try again. If the problem persists, contact support.",
        retryable=True,
    )


def file_not_found_error(filename: str) -> APIError:
    """Create error for missing file."""
    return APIError(
        code=ErrorCode.FILE_NOT_FOUND,
        message="File not found",
        detail=f"Filename: {filename}",
        hint="The file may have been deleted or moved",
        retryable=False,
    )
