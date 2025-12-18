"""
Tests for unified error schema.

Validates ErrorCode enum, APIError dataclass, and error factory functions.
"""

from __future__ import annotations

from app.models.errors import (
    APIError,
    ErrorCode,
    file_not_found_error,
    ffmpeg_not_found_error,
    internal_error,
    invalid_project_state_error,
    project_not_found_error,
    request_timeout_error,
    service_unavailable_error,
    session_expired_error,
    session_not_found_error,
    transcription_timeout_error,
    validation_error,
)


class TestErrorCode:
    """Test ErrorCode enum."""

    def test_all_error_codes_unique(self) -> None:
        """All error codes should have unique values."""
        codes = [e.value for e in ErrorCode]
        assert len(codes) == len(set(codes)), "Error codes must be unique"

    def test_error_codes_uppercase(self) -> None:
        """All error codes should be uppercase snake_case."""
        for code in ErrorCode:
            assert code.value.isupper(), f"Error code {code.value} should be uppercase"
            assert "_" in code.value or len(code.value.split("_")) == 1, (
                f"Error code {code.value} should use snake_case"
            )

    def test_error_code_count(self) -> None:
        """Verify we have all expected error codes."""
        # Update this count when adding new error codes
        expected_count = 19
        assert len(ErrorCode) == expected_count, (
            f"Expected {expected_count} error codes, found {len(ErrorCode)}"
        )


class TestAPIError:
    """Test APIError dataclass."""

    def test_minimal_error_creation(self) -> None:
        """Create error with only required fields."""
        error = APIError(code=ErrorCode.INTERNAL_ERROR, message="Something went wrong")
        assert error.code == ErrorCode.INTERNAL_ERROR
        assert error.message == "Something went wrong"
        assert error.detail is None
        assert error.hint is None
        assert error.retryable is False

    def test_full_error_creation(self) -> None:
        """Create error with all fields."""
        error = APIError(
            code=ErrorCode.TRANSCRIPTION_TIMEOUT,
            message="Operation timed out",
            detail="Timeout after 300 seconds",
            hint="Try a shorter video",
            retryable=True,
        )
        assert error.code == ErrorCode.TRANSCRIPTION_TIMEOUT
        assert error.message == "Operation timed out"
        assert error.detail == "Timeout after 300 seconds"
        assert error.hint == "Try a shorter video"
        assert error.retryable is True

    def test_to_dict_minimal(self) -> None:
        """Convert minimal error to dict."""
        error = APIError(code=ErrorCode.INTERNAL_ERROR, message="Something went wrong")
        result = error.to_dict()

        assert "error" in result
        error_dict = result["error"]

        assert error_dict["code"] == "INTERNAL_ERROR"
        assert error_dict["message"] == "Something went wrong"
        assert error_dict["retryable"] is False
        assert "detail" not in error_dict
        assert "hint" not in error_dict

    def test_to_dict_full(self) -> None:
        """Convert full error to dict."""
        error = APIError(
            code=ErrorCode.TRANSCRIPTION_TIMEOUT,
            message="Operation timed out",
            detail="Timeout after 300 seconds",
            hint="Try a shorter video",
            retryable=True,
        )
        result = error.to_dict()

        assert "error" in result
        error_dict = result["error"]

        assert error_dict["code"] == "TRANSCRIPTION_TIMEOUT"
        assert error_dict["message"] == "Operation timed out"
        assert error_dict["detail"] == "Timeout after 300 seconds"
        assert error_dict["hint"] == "Try a shorter video"
        assert error_dict["retryable"] is True

    def test_to_dict_with_detail_only(self) -> None:
        """Convert error with detail but no hint."""
        error = APIError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid input",
            detail="Field 'name' is required",
        )
        result = error.to_dict()

        error_dict = result["error"]
        assert "detail" in error_dict
        assert "hint" not in error_dict

    def test_to_dict_with_hint_only(self) -> None:
        """Convert error with hint but no detail."""
        error = APIError(
            code=ErrorCode.SESSION_EXPIRED,
            message="Session expired",
            hint="Start a new session",
        )
        result = error.to_dict()

        error_dict = result["error"]
        assert "hint" in error_dict
        assert "detail" not in error_dict


class TestErrorFactories:
    """Test predefined error factory functions."""

    def test_transcription_timeout_error(self) -> None:
        """Test transcription timeout error factory."""
        error = transcription_timeout_error(detail="After 300s")

        assert error.code == ErrorCode.TRANSCRIPTION_TIMEOUT
        assert "timed out" in error.message.lower()
        assert error.detail == "After 300s"
        assert error.hint is not None
        assert error.retryable is True

    def test_ffmpeg_not_found_error(self) -> None:
        """Test FFmpeg not found error factory."""
        error = ffmpeg_not_found_error()

        assert error.code == ErrorCode.FFMPEG_NOT_FOUND
        assert "ffmpeg" in error.message.lower()
        assert error.detail is not None
        assert error.hint is not None
        assert error.retryable is False

    def test_project_not_found_error(self) -> None:
        """Test project not found error factory."""
        error = project_not_found_error("proj-123")

        assert error.code == ErrorCode.PROJECT_NOT_FOUND
        assert error.message is not None
        assert "project" in error.message.lower()
        assert error.detail is not None
        assert "proj-123" in error.detail
        assert error.hint is not None
        assert error.retryable is False

    def test_invalid_project_state_error(self) -> None:
        """Test invalid project state error factory."""
        error = invalid_project_state_error(
            current_state="bootstrapping", required_state="active"
        )

        assert error.code == ErrorCode.INVALID_PROJECT_STATE
        assert error.message is not None
        assert "bootstrapping" in error.message.lower()
        assert "active" in error.message.lower()
        assert error.detail is not None
        assert error.hint is not None
        assert error.retryable is False

    def test_session_not_found_error(self) -> None:
        """Test session not found error factory."""
        error = session_not_found_error("sess-456")

        assert error.code == ErrorCode.SESSION_NOT_FOUND
        assert error.message is not None
        assert "session" in error.message.lower()
        assert error.detail is not None
        assert "sess-456" in error.detail
        assert error.hint is not None
        assert error.retryable is False

    def test_session_expired_error(self) -> None:
        """Test session expired error factory."""
        error = session_expired_error()

        assert error.code == ErrorCode.SESSION_EXPIRED
        assert "expired" in error.message.lower()
        assert error.detail is not None
        assert error.hint is not None
        assert error.retryable is False

    def test_validation_error(self) -> None:
        """Test validation error factory."""
        error = validation_error("email", "Invalid format")

        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "email" in error.message
        assert error.detail == "Invalid format"
        assert error.hint is not None
        assert error.retryable is False

    def test_service_unavailable_error(self) -> None:
        """Test service unavailable error factory."""
        error = service_unavailable_error(detail="Database connection failed")

        assert error.code == ErrorCode.SERVICE_UNAVAILABLE
        assert "unavailable" in error.message.lower()
        assert error.detail == "Database connection failed"
        assert error.hint is not None
        assert error.retryable is True

    def test_request_timeout_error(self) -> None:
        """Test request timeout error factory."""
        error = request_timeout_error(detail="After 60s")

        assert error.code == ErrorCode.REQUEST_TIMEOUT
        assert "timed out" in error.message.lower()
        assert error.detail == "After 60s"
        assert error.hint is not None
        assert error.retryable is True

    def test_internal_error(self) -> None:
        """Test internal error factory."""
        error = internal_error(detail="Unexpected exception")

        assert error.code == ErrorCode.INTERNAL_ERROR
        assert "internal" in error.message.lower()
        assert error.detail == "Unexpected exception"
        assert error.hint is not None
        assert error.retryable is True

    def test_file_not_found_error(self) -> None:
        """Test file not found error factory."""
        error = file_not_found_error("transcript.txt")

        assert error.code == ErrorCode.FILE_NOT_FOUND
        assert error.message is not None
        assert "file" in error.message.lower()
        assert error.detail is not None
        assert "transcript.txt" in error.detail
        assert error.hint is not None
        assert error.retryable is False


class TestErrorSchemaIntegration:
    """Test error schema integration scenarios."""

    def test_error_serialization_preserves_structure(self) -> None:
        """Ensure error dict can be JSON serialized."""
        error = APIError(
            code=ErrorCode.TRANSCRIPTION_FAILED,
            message="Transcription failed",
            detail="Audio format not supported",
            hint="Convert to mp3 or wav",
            retryable=False,
        )

        error_dict = error.to_dict()

        # Verify structure matches expected API response format
        assert isinstance(error_dict, dict)
        assert "error" in error_dict
        assert isinstance(error_dict["error"], dict)

        # Verify all values are JSON-serializable types
        for key, value in error_dict["error"].items():
            assert isinstance(value, (str, bool, int, float, type(None)))

    def test_retryable_flag_consistency(self) -> None:
        """Verify retryable flag is consistent with error types."""
        # Transient errors should be retryable
        transient_errors = [
            transcription_timeout_error(),
            service_unavailable_error(),
            request_timeout_error(),
            internal_error(),
        ]
        for error in transient_errors:
            assert error.retryable is True, (
                f"{error.code} should be retryable (transient error)"
            )

        # Permanent errors should not be retryable
        permanent_errors = [
            ffmpeg_not_found_error(),
            project_not_found_error("test"),
            session_not_found_error("test"),
            session_expired_error(),
            validation_error("field", "reason"),
            file_not_found_error("test.txt"),
        ]
        for error in permanent_errors:
            assert error.retryable is False, (
                f"{error.code} should not be retryable (permanent error)"
            )
