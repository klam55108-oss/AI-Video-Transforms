"""
Tests for audit hook system.

Tests the audit models, service, and API endpoints for capturing
agent tool usage and session events.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_audit_service
from app.main import app
from app.models.audit import (
    AuditEventType,
    AuditLogEntry,
    AuditLogResponse,
    AuditStats,
    SessionAuditEvent,
    ToolAuditEvent,
)
from app.services.audit_service import AuditService


# -----------------------------------------------------------------------------
# Audit Models Tests
# -----------------------------------------------------------------------------


class TestAuditModels:
    """Test audit model creation and serialization."""

    def test_tool_audit_event_creation(self) -> None:
        """Test ToolAuditEvent model creation with defaults."""
        event = ToolAuditEvent(
            event_type=AuditEventType.PRE_TOOL_USE,
            session_id="test-session-123",
            tool_name="Bash",
            tool_input={"command": "ls -la"},
        )

        assert event.event_type == AuditEventType.PRE_TOOL_USE
        assert event.session_id == "test-session-123"
        assert event.tool_name == "Bash"
        assert event.tool_input == {"command": "ls -la"}
        assert event.blocked is False
        assert event.id  # Should have auto-generated ID
        assert event.timestamp > 0

    def test_tool_audit_event_blocked(self) -> None:
        """Test ToolAuditEvent with blocked operation."""
        event = ToolAuditEvent(
            event_type=AuditEventType.TOOL_BLOCKED,
            session_id="test-session",
            tool_name="Bash",
            tool_input={"command": "rm -rf /"},
            blocked=True,
            block_reason="Dangerous command pattern detected",
        )

        assert event.blocked is True
        assert event.block_reason == "Dangerous command pattern detected"

    def test_session_audit_event_creation(self) -> None:
        """Test SessionAuditEvent model creation."""
        event = SessionAuditEvent(
            event_type=AuditEventType.SESSION_STOP,
            session_id="test-session",
            stop_reason="completed",
            total_turns=5,
        )

        assert event.event_type == AuditEventType.SESSION_STOP
        assert event.stop_reason == "completed"
        assert event.total_turns == 5

    def test_audit_log_entry_from_tool_event(self) -> None:
        """Test creating log entry from tool event."""
        event = ToolAuditEvent(
            event_type=AuditEventType.POST_TOOL_USE,
            session_id="test-session",
            tool_name="Write",
            tool_input={"file_path": "/tmp/test.txt"},
            success=True,
            duration_ms=150.5,
        )

        entry = AuditLogEntry.from_tool_event(event)

        assert entry.tool_name == "Write"
        assert entry.success is True
        assert entry.duration_ms == 150.5
        assert "success" in entry.summary
        assert "150ms" in entry.summary

    def test_audit_log_entry_from_blocked_event(self) -> None:
        """Test creating log entry from blocked tool event."""
        event = ToolAuditEvent(
            event_type=AuditEventType.TOOL_BLOCKED,
            session_id="test-session",
            tool_name="Bash",
            tool_input={},
            blocked=True,
            block_reason="Protected path",
        )

        entry = AuditLogEntry.from_tool_event(event)

        assert entry.blocked is True
        assert "Blocked" in entry.summary
        assert "Protected path" in entry.summary


# -----------------------------------------------------------------------------
# Audit Service Tests
# -----------------------------------------------------------------------------


class TestAuditService:
    """Test AuditService functionality."""

    @pytest.fixture
    def audit_service(self, tmp_path: Path) -> AuditService:
        """Create audit service with temporary storage."""
        return AuditService(data_path=tmp_path)

    @pytest.mark.asyncio
    async def test_log_and_retrieve_event(
        self, audit_service: AuditService
    ) -> None:
        """Test logging an event and retrieving it."""
        event = ToolAuditEvent(
            event_type=AuditEventType.PRE_TOOL_USE,
            session_id="test-session-abc",
            tool_name="Read",
            tool_input={"file_path": "/tmp/file.txt"},
        )

        await audit_service.log_event(event)

        # Retrieve the audit log
        log = await audit_service.get_session_audit_log("test-session-abc")

        assert log.session_id == "test-session-abc"
        assert log.total_count == 1
        assert len(log.entries) == 1
        assert log.entries[0].tool_name == "Read"

    @pytest.mark.asyncio
    async def test_stats_tracking(self, audit_service: AuditService) -> None:
        """Test that stats are updated correctly."""
        # Log a few events
        await audit_service.log_event(
            ToolAuditEvent(
                event_type=AuditEventType.PRE_TOOL_USE,
                session_id="session-1",
                tool_name="Bash",
                tool_input={},
            )
        )
        await audit_service.log_event(
            ToolAuditEvent(
                event_type=AuditEventType.POST_TOOL_USE,
                session_id="session-1",
                tool_name="Bash",
                tool_input={},
                success=True,
                duration_ms=100,
            )
        )
        await audit_service.log_event(
            ToolAuditEvent(
                event_type=AuditEventType.TOOL_BLOCKED,
                session_id="session-1",
                tool_name="Write",
                tool_input={},
                blocked=True,
            )
        )

        stats = await audit_service.get_stats()

        assert stats.total_events == 3
        assert stats.tools_invoked == 1
        assert stats.tools_succeeded == 1
        assert stats.tools_blocked == 1

    @pytest.mark.asyncio
    async def test_list_sessions_with_audits(
        self, audit_service: AuditService
    ) -> None:
        """Test listing sessions that have audit logs."""
        # Create events for multiple sessions
        for session_id in ["session-a", "session-b", "session-c"]:
            await audit_service.log_event(
                ToolAuditEvent(
                    event_type=AuditEventType.PRE_TOOL_USE,
                    session_id=session_id,
                    tool_name="Test",
                    tool_input={},
                )
            )

        sessions = await audit_service.list_sessions_with_audits()

        assert len(sessions) == 3
        session_ids = {s["session_id"] for s in sessions}
        assert "session-a" in session_ids
        assert "session-b" in session_ids
        assert "session-c" in session_ids

    @pytest.mark.asyncio
    async def test_pagination(self, audit_service: AuditService) -> None:
        """Test audit log pagination."""
        session_id = "paginated-session"

        # Log 10 events
        for i in range(10):
            await audit_service.log_event(
                ToolAuditEvent(
                    event_type=AuditEventType.POST_TOOL_USE,
                    session_id=session_id,
                    tool_name=f"Tool{i}",
                    tool_input={},
                    success=True,
                )
            )

        # Get first page
        page1 = await audit_service.get_session_audit_log(
            session_id, limit=3, offset=0
        )
        assert len(page1.entries) == 3
        assert page1.total_count == 10
        assert page1.has_more is True

        # Get second page
        page2 = await audit_service.get_session_audit_log(
            session_id, limit=3, offset=3
        )
        assert len(page2.entries) == 3
        assert page2.has_more is True

        # Get last page
        page_last = await audit_service.get_session_audit_log(
            session_id, limit=3, offset=9
        )
        assert len(page_last.entries) == 1
        assert page_last.has_more is False


# -----------------------------------------------------------------------------
# Audit API Tests
# -----------------------------------------------------------------------------


class TestAuditAPI:
    """Test audit API endpoints."""

    @pytest.fixture
    def mock_audit_service(self, tmp_path: Path) -> AuditService:
        """Create mock audit service for API tests."""
        return AuditService(data_path=tmp_path)

    @pytest.mark.asyncio
    async def test_get_stats_endpoint(
        self, mock_audit_service: AuditService
    ) -> None:
        """Test GET /audit/stats endpoint."""
        app.dependency_overrides[get_audit_service] = lambda: mock_audit_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/audit/stats")

            assert response.status_code == 200
            data = response.json()
            assert "total_events" in data
            assert "tools_invoked" in data
        finally:
            app.dependency_overrides.pop(get_audit_service, None)

    @pytest.mark.asyncio
    async def test_list_sessions_endpoint(
        self, mock_audit_service: AuditService
    ) -> None:
        """Test GET /audit/sessions endpoint."""
        # Add some test data
        await mock_audit_service.log_event(
            ToolAuditEvent(
                event_type=AuditEventType.PRE_TOOL_USE,
                session_id="api-test-session",
                tool_name="Test",
                tool_input={},
            )
        )

        app.dependency_overrides[get_audit_service] = lambda: mock_audit_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/audit/sessions")

            assert response.status_code == 200
            data = response.json()
            assert "sessions" in data
            assert len(data["sessions"]) == 1
        finally:
            app.dependency_overrides.pop(get_audit_service, None)

    @pytest.mark.asyncio
    async def test_get_session_audit_log_endpoint(
        self, mock_audit_service: AuditService
    ) -> None:
        """Test GET /audit/sessions/{session_id} endpoint."""
        session_id = "550e8400-e29b-41d4-a716-446655440000"

        # Add test event
        await mock_audit_service.log_event(
            ToolAuditEvent(
                event_type=AuditEventType.POST_TOOL_USE,
                session_id=session_id,
                tool_name="Write",
                tool_input={},
                success=True,
            )
        )

        app.dependency_overrides[get_audit_service] = lambda: mock_audit_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(f"/audit/sessions/{session_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["session_id"] == session_id
            assert data["total_count"] == 1
        finally:
            app.dependency_overrides.pop(get_audit_service, None)

    @pytest.mark.asyncio
    async def test_cleanup_endpoint(
        self, mock_audit_service: AuditService
    ) -> None:
        """Test POST /audit/cleanup endpoint."""
        app.dependency_overrides[get_audit_service] = lambda: mock_audit_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post("/audit/cleanup")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "sessions_cleaned" in data
        finally:
            app.dependency_overrides.pop(get_audit_service, None)


# -----------------------------------------------------------------------------
# Hook Factory Tests
# -----------------------------------------------------------------------------


class TestHookFactory:
    """Test hook factory and callback functions."""

    @pytest.fixture
    def audit_service(self, tmp_path: Path) -> AuditService:
        """Create audit service for hook tests."""
        return AuditService(data_path=tmp_path)

    @pytest.mark.asyncio
    async def test_pre_tool_use_logs_event(
        self, audit_service: AuditService
    ) -> None:
        """Test that pre_tool_use hook logs events."""
        from app.core.hooks import AuditHookFactory

        factory = AuditHookFactory("test-session", audit_service)

        input_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.txt"},
        }

        result = await factory.pre_tool_use_hook(input_data, "tool-123", None)

        # Should return empty dict (continue)
        assert result == {}

        # Should have logged the event
        log = await audit_service.get_session_audit_log("test-session")
        assert log.total_count == 1
        assert log.entries[0].tool_name == "Read"

    @pytest.mark.asyncio
    async def test_pre_tool_use_blocks_dangerous_bash(
        self, audit_service: AuditService
    ) -> None:
        """Test that dangerous bash commands are blocked."""
        from app.core.hooks import AuditHookFactory

        factory = AuditHookFactory("test-session", audit_service)

        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
        }

        result = await factory.pre_tool_use_hook(input_data, "tool-456", None)

        # Should return deny decision
        assert "hookSpecificOutput" in result
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

        # Should have logged as blocked
        log = await audit_service.get_session_audit_log("test-session")
        assert log.entries[0].blocked is True

    @pytest.mark.asyncio
    async def test_pre_tool_use_blocks_protected_paths(
        self, audit_service: AuditService
    ) -> None:
        """Test that writes to protected paths are blocked."""
        from app.core.hooks import AuditHookFactory

        factory = AuditHookFactory("test-session", audit_service)

        input_data = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/etc/passwd"},
        }

        result = await factory.pre_tool_use_hook(input_data, "tool-789", None)

        assert "hookSpecificOutput" in result
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    @pytest.mark.asyncio
    async def test_post_tool_use_logs_result(
        self, audit_service: AuditService
    ) -> None:
        """Test that post_tool_use hook logs results."""
        from app.core.hooks import AuditHookFactory

        factory = AuditHookFactory("test-session", audit_service)

        # Simulate pre-tool to set start time
        await factory.pre_tool_use_hook(
            {"tool_name": "Bash", "tool_input": {"command": "ls"}},
            "tool-abc",
            None,
        )

        # Simulate small delay
        await asyncio.sleep(0.01)

        # Post-tool use
        result = await factory.post_tool_use_hook(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
                "tool_response": {"content": "file1\nfile2"},
            },
            "tool-abc",
            None,
        )

        assert result == {}

        log = await audit_service.get_session_audit_log("test-session")
        # Should have 2 events: pre and post
        assert log.total_count == 2

        # Post event should have duration
        post_events = [
            e for e in log.entries
            if e.event_type == AuditEventType.POST_TOOL_USE.value
        ]
        assert len(post_events) == 1
        assert post_events[0].duration_ms is not None
        assert post_events[0].duration_ms >= 0

    @pytest.mark.asyncio
    async def test_stop_hook_logs_session_stop(
        self, audit_service: AuditService
    ) -> None:
        """Test that stop hook logs session termination."""
        from app.core.hooks import AuditHookFactory

        factory = AuditHookFactory("test-session", audit_service)

        result = await factory.stop_hook(
            {"stop_reason": "completed"},
            None,
            None,
        )

        assert result == {}

        log = await audit_service.get_session_audit_log("test-session")
        assert log.total_count == 1
        assert log.entries[0].event_type == AuditEventType.SESSION_STOP.value
