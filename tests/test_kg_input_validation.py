"""
Knowledge Graph Input Validation Tests (Phase 2A).

Tests for input sanitization and session validation:
- Node ID validation (8 chars, alphanumeric)
- Entity name max length enforcement
- Control character stripping
- Session ID format validation (UUID v4)

These tests validate the security hardening from Council Recommendations.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.api.deps import get_kg_service
from app.kg.domain import KGProject, ProjectState
from app.kg.resolution import MergeHistory
from app.models.requests import (
    CONTROL_CHAR_PATTERN,
    MAX_ENTITY_NAME_LENGTH,
    MergeEntitiesRequest,
    sanitize_entity_name,
)


# ============================================================================
# TEST: Node ID Validation
# ============================================================================


class TestNodeIdValidation:
    """Test node ID validation in MergeEntitiesRequest.

    Node IDs in the KG system are 12 lowercase hex characters (uuid4().hex[:12]).
    """

    def test_valid_node_id_hex(self) -> None:
        """Test valid 12-character hex node IDs."""
        request = MergeEntitiesRequest(
            survivor_id="abc123def456",
            merged_id="fedcba987654",
        )
        assert request.survivor_id == "abc123def456"
        assert request.merged_id == "fedcba987654"

    def test_valid_node_id_all_digits(self) -> None:
        """Test valid node ID with all digits."""
        request = MergeEntitiesRequest(
            survivor_id="123456789012",
            merged_id="210987654321",
        )
        assert request.survivor_id == "123456789012"

    def test_valid_node_id_all_letters(self) -> None:
        """Test valid node ID with all hex letters (a-f)."""
        request = MergeEntitiesRequest(
            survivor_id="abcdefabcdef",
            merged_id="fedcbafedcba",
        )
        assert request.survivor_id == "abcdefabcdef"
        assert request.merged_id == "fedcbafedcba"

    def test_invalid_node_id_too_short(self) -> None:
        """Test that node IDs shorter than 12 chars are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MergeEntitiesRequest(
                survivor_id="abc123def45",  # 11 chars
                merged_id="fedcba987654",
            )
        errors = exc_info.value.errors()
        assert any("12 characters" in str(e["msg"]) for e in errors)

    def test_invalid_node_id_too_long(self) -> None:
        """Test that node IDs longer than 12 chars are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MergeEntitiesRequest(
                survivor_id="abc123def4567",  # 13 chars
                merged_id="fedcba987654",
            )
        errors = exc_info.value.errors()
        assert any("12 characters" in str(e["msg"]) for e in errors)

    def test_invalid_node_id_empty(self) -> None:
        """Test that empty node IDs are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MergeEntitiesRequest(
                survivor_id="",
                merged_id="fedcba987654",
            )
        errors = exc_info.value.errors()
        assert any("empty" in str(e["msg"]).lower() for e in errors)

    def test_invalid_node_id_uppercase(self) -> None:
        """Test that uppercase hex is rejected (must be lowercase)."""
        with pytest.raises(ValidationError) as exc_info:
            MergeEntitiesRequest(
                survivor_id="ABC123DEF456",  # uppercase not allowed
                merged_id="fedcba987654",
            )
        errors = exc_info.value.errors()
        assert any("hexadecimal" in str(e["msg"]) for e in errors)

    def test_invalid_node_id_non_hex(self) -> None:
        """Test that non-hex characters are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MergeEntitiesRequest(
                survivor_id="ghijkl123456",  # g-z not allowed in hex
                merged_id="fedcba987654",
            )
        errors = exc_info.value.errors()
        assert any("hexadecimal" in str(e["msg"]) for e in errors)

    def test_invalid_node_id_special_chars(self) -> None:
        """Test that node IDs with special characters are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MergeEntitiesRequest(
                survivor_id="abc-123def45",  # hyphen not allowed
                merged_id="fedcba987654",
            )
        errors = exc_info.value.errors()
        assert any("hexadecimal" in str(e["msg"]) for e in errors)

    def test_invalid_node_id_spaces(self) -> None:
        """Test that node IDs with spaces are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MergeEntitiesRequest(
                survivor_id="abc 123def45",  # space not allowed
                merged_id="fedcba987654",
            )
        errors = exc_info.value.errors()
        assert any("hexadecimal" in str(e["msg"]) for e in errors)

    def test_request_id_optional(self) -> None:
        """Test that request_id is optional."""
        request = MergeEntitiesRequest(
            survivor_id="abc123def456",
            merged_id="fedcba987654",
        )
        assert request.request_id is None

    def test_request_id_valid(self) -> None:
        """Test that request_id can be set."""
        request = MergeEntitiesRequest(
            survivor_id="abc123def456",
            merged_id="fedcba987654",
            request_id="req-12345-unique",
        )
        assert request.request_id == "req-12345-unique"


# ============================================================================
# TEST: Entity Name Sanitization
# ============================================================================


class TestEntityNameSanitization:
    """Test entity name sanitization function."""

    def test_sanitize_normal_string(self) -> None:
        """Test that normal strings are not modified."""
        result = sanitize_entity_name("John Smith")
        assert result == "John Smith"

    def test_sanitize_strips_whitespace(self) -> None:
        """Test that leading/trailing whitespace is stripped."""
        result = sanitize_entity_name("  John Smith  ")
        assert result == "John Smith"

    def test_sanitize_preserves_internal_spaces(self) -> None:
        """Test that internal spaces are preserved."""
        result = sanitize_entity_name("John  Smith  Jr")
        assert result == "John  Smith  Jr"

    def test_sanitize_preserves_tabs_and_newlines(self) -> None:
        """Test that tabs and newlines are preserved (not control chars)."""
        result = sanitize_entity_name("Line1\tLine2\nLine3")
        assert "\t" in result
        assert "\n" in result

    def test_sanitize_removes_null_bytes(self) -> None:
        """Test that null bytes are removed."""
        result = sanitize_entity_name("John\x00Smith")
        assert "\x00" not in result
        assert result == "JohnSmith"

    def test_sanitize_removes_bell_char(self) -> None:
        """Test that bell character (0x07) is removed."""
        result = sanitize_entity_name("John\x07Smith")
        assert "\x07" not in result
        assert result == "JohnSmith"

    def test_sanitize_removes_backspace(self) -> None:
        """Test that backspace (0x08) is removed."""
        result = sanitize_entity_name("John\x08Smith")
        assert "\x08" not in result

    def test_sanitize_removes_del_char(self) -> None:
        """Test that DEL character (0x7f) is removed."""
        result = sanitize_entity_name("John\x7fSmith")
        assert "\x7f" not in result
        assert result == "JohnSmith"

    def test_sanitize_removes_c1_control_chars(self) -> None:
        """Test that C1 control characters (0x80-0x9f) are removed."""
        # 0x85 is NEL (Next Line)
        result = sanitize_entity_name("John\x85Smith")
        assert "\x85" not in result

    def test_sanitize_empty_string(self) -> None:
        """Test that empty strings are returned as-is."""
        result = sanitize_entity_name("")
        assert result == ""

    def test_sanitize_max_length_exact(self) -> None:
        """Test string at exactly max length is accepted."""
        long_name = "A" * MAX_ENTITY_NAME_LENGTH
        result = sanitize_entity_name(long_name)
        assert result == long_name
        assert len(result) == MAX_ENTITY_NAME_LENGTH

    def test_sanitize_max_length_exceeded(self) -> None:
        """Test that strings exceeding max length raise error."""
        too_long = "A" * (MAX_ENTITY_NAME_LENGTH + 1)
        with pytest.raises(ValueError) as exc_info:
            sanitize_entity_name(too_long)
        assert str(MAX_ENTITY_NAME_LENGTH) in str(exc_info.value)
        assert "exceeds" in str(exc_info.value).lower()

    def test_control_char_pattern_comprehensive(self) -> None:
        """Test that CONTROL_CHAR_PATTERN matches expected characters."""
        # Should match C0 control chars (except tab, newline, carriage return)
        for code in range(0x00, 0x09):  # 0x00-0x08
            char = chr(code)
            assert CONTROL_CHAR_PATTERN.search(char) is not None, f"0x{code:02x}"

        # 0x09 (tab), 0x0a (newline), 0x0d (carriage return) should NOT match
        assert CONTROL_CHAR_PATTERN.search("\t") is None
        assert CONTROL_CHAR_PATTERN.search("\n") is None
        assert CONTROL_CHAR_PATTERN.search("\r") is None

        # 0x0b (vertical tab), 0x0c (form feed) SHOULD match
        assert CONTROL_CHAR_PATTERN.search("\x0b") is not None
        assert CONTROL_CHAR_PATTERN.search("\x0c") is not None

        # 0x0e-0x1f should match
        for code in range(0x0E, 0x20):
            char = chr(code)
            assert CONTROL_CHAR_PATTERN.search(char) is not None, f"0x{code:02x}"

        # 0x7f (DEL) should match
        assert CONTROL_CHAR_PATTERN.search("\x7f") is not None

        # 0x80-0x9f (C1 control chars) should match
        for code in range(0x80, 0xA0):
            char = chr(code)
            assert CONTROL_CHAR_PATTERN.search(char) is not None, f"0x{code:02x}"


# ============================================================================
# TEST: Session ID Validation via API
# ============================================================================


class MockKGService:
    """Mock KGService for testing session validation."""

    def __init__(self) -> None:
        self.projects: dict[str, KGProject] = {}
        self.last_merge_call: dict[str, str | None] = {}

    async def get_project(self, project_id: str) -> KGProject | None:
        return self.projects.get(project_id)

    async def merge_entities(
        self,
        project_id: str,
        survivor_id: str,
        merged_id: str,
        merge_type: str = "user",
        session_id: str | None = None,
        request_id: str | None = None,
        confidence: float = 1.0,
    ) -> MergeHistory:
        """Track merge call and return mock history."""
        self.last_merge_call = {
            "project_id": project_id,
            "survivor_id": survivor_id,
            "merged_id": merged_id,
            "merge_type": merge_type,
            "session_id": session_id,
            "request_id": request_id,
        }
        return MergeHistory(
            survivor_id=survivor_id,
            merged_id=merged_id,
            merged_label="Test Entity",
            merge_type=merge_type,  # type: ignore[arg-type]
            confidence=0.9,
            merged_by=session_id,
        )

    def add_project(self, project: KGProject) -> None:
        self.projects[project.id] = project

    @property
    def kb_path(self) -> None:
        return None


class TestSessionIdValidation:
    """Test session ID validation for merge endpoint."""

    @pytest.mark.asyncio
    async def test_merge_without_session_id(self) -> None:
        """Test merge without X-Session-ID header uses 'user' merge type."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="abc123def456",
            name="Test Project",
            state=ProjectState.ACTIVE,
            kb_id="kb001",
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/abc123def456/merge",
                    json={"survivor_id": "abcd12345678", "merged_id": "ef0198765432"},
                )

            assert response.status_code == 200
            assert mock_service.last_merge_call["merge_type"] == "user"
            assert mock_service.last_merge_call["session_id"] is None
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_merge_with_valid_session_id(self) -> None:
        """Test merge with valid UUID v4 session ID uses 'agent' merge type."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="abc123def456",
            name="Test Project",
            state=ProjectState.ACTIVE,
            kb_id="kb001",
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/abc123def456/merge",
                    json={"survivor_id": "abcd12345678", "merged_id": "ef0198765432"},
                    headers={"X-Session-ID": valid_uuid},
                )

            assert response.status_code == 200
            assert mock_service.last_merge_call["merge_type"] == "agent"
            assert mock_service.last_merge_call["session_id"] == valid_uuid
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_merge_with_invalid_session_id_format(self) -> None:
        """Test merge with invalid session ID format returns 400."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="abc123def456",
            name="Test Project",
            state=ProjectState.ACTIVE,
            kb_id="kb001",
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/abc123def456/merge",
                    json={"survivor_id": "abcd12345678", "merged_id": "ef0198765432"},
                    headers={"X-Session-ID": "not-a-valid-uuid"},
                )

            assert response.status_code == 400
            assert "session id" in response.json()["detail"].lower()
            assert "uuid" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_merge_with_uuid_v1_rejected(self) -> None:
        """Test that UUID v1 is rejected (only v4 allowed)."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="abc123def456",
            name="Test Project",
            state=ProjectState.ACTIVE,
            kb_id="kb001",
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        # UUID v1 (note the '1' in the third group)
        uuid_v1 = "550e8400-e29b-11d4-a716-446655440000"

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/abc123def456/merge",
                    json={"survivor_id": "abcd12345678", "merged_id": "ef0198765432"},
                    headers={"X-Session-ID": uuid_v1},
                )

            assert response.status_code == 400
            assert "uuid" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_merge_with_uppercase_uuid(self) -> None:
        """Test that uppercase UUID v4 is accepted."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="abc123def456",
            name="Test Project",
            state=ProjectState.ACTIVE,
            kb_id="kb001",
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        # UUID v4 in uppercase
        valid_uuid = "550E8400-E29B-41D4-A716-446655440000"

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/abc123def456/merge",
                    json={"survivor_id": "abcd12345678", "merged_id": "ef0198765432"},
                    headers={"X-Session-ID": valid_uuid},
                )

            assert response.status_code == 200
            assert mock_service.last_merge_call["session_id"] == valid_uuid
        finally:
            app.dependency_overrides.pop(get_kg_service, None)


# ============================================================================
# TEST: Node ID Validation via API
# ============================================================================


class TestNodeIdValidationViaApi:
    """Test node ID validation at API level."""

    @pytest.mark.asyncio
    async def test_merge_with_invalid_survivor_id_too_short(self) -> None:
        """Test merge with too-short survivor_id returns 422."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="abc123def456",
            name="Test Project",
            state=ProjectState.ACTIVE,
            kb_id="kb001",
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/abc123def456/merge",
                    json={"survivor_id": "short", "merged_id": "ef0198765432"},
                )

            assert response.status_code == 422  # Validation error
            # Error handler returns {"error": {"code": ..., "message": ..., "detail": ...}}
            data = response.json()
            error = data.get("error", {})
            assert error.get("code") == "VALIDATION_ERROR"
            # The actual validation message is in the "detail" field
            assert "survivor_id" in error.get("message", "")
            assert "12 characters" in error.get("detail", "")
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_merge_with_invalid_merged_id_special_chars(self) -> None:
        """Test merge with special chars in merged_id returns 422."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="abc123def456",
            name="Test Project",
            state=ProjectState.ACTIVE,
            kb_id="kb001",
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/abc123def456/merge",
                    json={"survivor_id": "abcd12345678", "merged_id": "xyz-98765432"},
                )

            assert response.status_code == 422  # Validation error
            # Error handler returns {"error": {"code": ..., "message": ..., "detail": ...}}
            data = response.json()
            error = data.get("error", {})
            assert error.get("code") == "VALIDATION_ERROR"
            # The actual validation message is in the "detail" field
            assert "merged_id" in error.get("message", "")
            assert "hexadecimal" in error.get("detail", "")
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_merge_with_request_id(self) -> None:
        """Test merge with optional request_id is accepted."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="abc123def456",
            name="Test Project",
            state=ProjectState.ACTIVE,
            kb_id="kb001",
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/abc123def456/merge",
                    json={
                        "survivor_id": "abcd12345678",
                        "merged_id": "ef0198765432",
                        "request_id": "idempotency-key-12345",
                    },
                )

            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_kg_service, None)
