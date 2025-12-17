"""
API Dependencies Tests.

Tests for the app/api/deps.py module including:
- Dependency providers
- Validation functions
- Validated path parameter classes
"""

import pytest
from fastapi import HTTPException


class TestValidationFunctions:
    """Tests for validation helper functions."""

    def test_validate_uuid_accepts_valid_uuid(self):
        """Test that validate_uuid accepts valid UUID v4."""
        from app.api.deps import validate_uuid

        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = validate_uuid(valid_uuid)
        assert result == valid_uuid

    def test_validate_uuid_rejects_invalid_uuid(self):
        """Test that validate_uuid rejects invalid UUID."""
        from app.api.deps import validate_uuid

        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("not-a-valid-uuid")

        assert exc_info.value.status_code == 400
        assert "UUID v4" in exc_info.value.detail

    def test_validate_uuid_rejects_empty_string(self):
        """Test that validate_uuid rejects empty string."""
        from app.api.deps import validate_uuid

        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("")

        assert exc_info.value.status_code == 400

    def test_validate_uuid_custom_field_name(self):
        """Test that validate_uuid uses custom field name in error."""
        from app.api.deps import validate_uuid

        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("invalid", field_name="session ID")

        assert "session ID" in exc_info.value.detail

    def test_validate_short_id_accepts_valid_id(self):
        """Test that validate_short_id accepts valid 8-char hex ID."""
        from app.api.deps import validate_short_id

        valid_id = "abcd1234"
        result = validate_short_id(valid_id)
        assert result == valid_id

    def test_validate_short_id_rejects_invalid_id(self):
        """Test that validate_short_id rejects invalid ID."""
        from app.api.deps import validate_short_id

        with pytest.raises(HTTPException) as exc_info:
            validate_short_id("not-valid!")

        assert exc_info.value.status_code == 400

    def test_validate_short_id_rejects_wrong_length(self):
        """Test that validate_short_id rejects wrong length."""
        from app.api.deps import validate_short_id

        with pytest.raises(HTTPException) as exc_info:
            validate_short_id("abc")  # Too short

        assert exc_info.value.status_code == 400

    def test_validate_short_id_custom_field_name(self):
        """Test that validate_short_id uses custom field name in error."""
        from app.api.deps import validate_short_id

        with pytest.raises(HTTPException) as exc_info:
            validate_short_id("invalid!", field_name="transcript ID")

        assert "transcript ID" in exc_info.value.detail


class TestValidatedSessionId:
    """Tests for ValidatedSessionId dependency class."""

    def test_validated_session_id_accepts_valid(self):
        """Test that ValidatedSessionId accepts valid UUID."""
        from app.api.deps import ValidatedSessionId

        validator = ValidatedSessionId()
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"

        result = validator(valid_uuid)
        assert result == valid_uuid

    def test_validated_session_id_rejects_invalid(self):
        """Test that ValidatedSessionId rejects invalid UUID."""
        from app.api.deps import ValidatedSessionId

        validator = ValidatedSessionId()

        with pytest.raises(HTTPException) as exc_info:
            validator("invalid-uuid")

        assert exc_info.value.status_code == 400
        assert "session ID" in exc_info.value.detail


class TestValidatedTranscriptId:
    """Tests for ValidatedTranscriptId dependency class."""

    def test_validated_transcript_id_accepts_valid(self):
        """Test that ValidatedTranscriptId accepts valid short ID."""
        from app.api.deps import ValidatedTranscriptId

        validator = ValidatedTranscriptId()
        valid_id = "abcd1234"

        result = validator(valid_id)
        assert result == valid_id

    def test_validated_transcript_id_rejects_invalid(self):
        """Test that ValidatedTranscriptId rejects invalid ID."""
        from app.api.deps import ValidatedTranscriptId

        validator = ValidatedTranscriptId()

        with pytest.raises(HTTPException) as exc_info:
            validator("invalid!")

        assert exc_info.value.status_code == 400
        assert "transcript ID" in exc_info.value.detail


class TestServiceProviders:
    """Tests for service dependency providers.

    These tests rely on the session-scoped conftest fixture that initializes
    services via services_lifespan. We do NOT create our own services_lifespan
    context here because exiting that context sets _services = None, which
    would break subsequent tests.
    """

    def test_get_session_service_returns_service(self):
        """Test that get_session_service returns SessionService."""
        from app.api.deps import get_session_service
        from app.services import SessionService

        service = get_session_service()
        assert isinstance(service, SessionService)

    def test_get_storage_service_returns_service(self):
        """Test that get_storage_service returns StorageService."""
        from app.api.deps import get_storage_service
        from app.services import StorageService

        service = get_storage_service()
        assert isinstance(service, StorageService)

    def test_get_transcription_service_returns_service(self):
        """Test that get_transcription_service returns TranscriptionService."""
        from app.api.deps import get_transcription_service
        from app.services import TranscriptionService

        service = get_transcription_service()
        assert isinstance(service, TranscriptionService)


class TestErrorHandling:
    """Tests for API error handling."""

    def test_handle_endpoint_error_passes_through_http_exception(self):
        """Test that handle_endpoint_error passes through HTTPException."""
        from app.api.errors import handle_endpoint_error

        original = HTTPException(status_code=404, detail="Not found")
        result = handle_endpoint_error(original, "test context")

        assert result is original

    def test_handle_endpoint_error_converts_timeout(self):
        """Test that handle_endpoint_error converts TimeoutError to 504."""
        from app.api.errors import handle_endpoint_error

        error = TimeoutError("Operation timed out")
        result = handle_endpoint_error(error, "test context")

        assert result.status_code == 504
        # Detail is now a dict with error schema
        assert isinstance(result.detail, dict)
        assert "error" in result.detail
        assert result.detail["error"]["code"] == "REQUEST_TIMEOUT"
        assert "timed out" in result.detail["error"]["message"].lower()

    def test_handle_endpoint_error_converts_closed_runtime_error(self):
        """Test that handle_endpoint_error converts closed session error to 410."""
        from app.api.errors import handle_endpoint_error

        error = RuntimeError("Session is closed")
        result = handle_endpoint_error(error, "test context")

        assert result.status_code == 410
        # Detail is now a dict with error schema
        assert isinstance(result.detail, dict)
        assert "error" in result.detail
        assert result.detail["error"]["code"] == "SESSION_EXPIRED"
        assert "expired" in result.detail["error"]["message"].lower()

    def test_handle_endpoint_error_converts_generic_to_500(self):
        """Test that handle_endpoint_error converts generic errors to 400 for ValueError."""
        from app.api.errors import handle_endpoint_error

        error = ValueError("Some internal error")
        result = handle_endpoint_error(error, "test context")

        # ValueError is now treated as validation error (400), not 500
        assert result.status_code == 400
        # Detail is now a dict with error schema
        assert isinstance(result.detail, dict)
        assert "error" in result.detail
        assert result.detail["error"]["code"] == "VALIDATION_ERROR"
        assert "Some internal error" in result.detail["error"]["message"]


class TestRequestModels:
    """Tests for request Pydantic models."""

    def test_chat_request_valid(self):
        """Test that ChatRequest accepts valid data."""
        from app.models.requests import ChatRequest

        request = ChatRequest(
            session_id="550e8400-e29b-41d4-a716-446655440000",
            message="Hello, world!",
        )

        assert request.session_id == "550e8400-e29b-41d4-a716-446655440000"
        assert request.message == "Hello, world!"

    def test_chat_request_strips_whitespace_from_message(self):
        """Test that ChatRequest strips whitespace from message."""
        from app.models.requests import ChatRequest

        request = ChatRequest(
            session_id="550e8400-e29b-41d4-a716-446655440000",
            message="  Hello, world!  ",
        )

        assert request.message == "Hello, world!"

    def test_chat_request_rejects_invalid_uuid(self):
        """Test that ChatRequest rejects invalid UUID."""
        from pydantic import ValidationError

        from app.models.requests import ChatRequest

        with pytest.raises(ValidationError):
            ChatRequest(
                session_id="not-a-valid-uuid",
                message="Hello",
            )

    def test_chat_request_rejects_empty_message(self):
        """Test that ChatRequest rejects empty message."""
        from pydantic import ValidationError

        from app.models.requests import ChatRequest

        with pytest.raises(ValidationError):
            ChatRequest(
                session_id="550e8400-e29b-41d4-a716-446655440000",
                message="   ",  # Only whitespace
            )

    def test_init_request_valid(self):
        """Test that InitRequest accepts valid data."""
        from app.models.requests import InitRequest

        request = InitRequest(session_id="550e8400-e29b-41d4-a716-446655440000")
        assert request.session_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_init_request_rejects_invalid_uuid(self):
        """Test that InitRequest rejects invalid UUID."""
        from pydantic import ValidationError

        from app.models.requests import InitRequest

        with pytest.raises(ValidationError):
            InitRequest(session_id="not-a-valid-uuid")
