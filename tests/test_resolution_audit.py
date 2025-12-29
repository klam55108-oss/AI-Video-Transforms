"""
Tests for Entity Resolution Audit Logging.

Tests the resolution-specific audit models, service methods,
and integration with the KG service.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.models.audit import (
    AuditEventType,
    AuditLogEntry,
    AuditStats,
    ResolutionAuditEvent,
)
from app.services.audit_service import AuditService


# -----------------------------------------------------------------------------
# ResolutionAuditEvent Model Tests
# -----------------------------------------------------------------------------


class TestResolutionAuditEvent:
    """Test ResolutionAuditEvent model creation and serialization."""

    def test_resolution_scan_event_creation(self) -> None:
        """Test creating a resolution scan complete event."""
        event = ResolutionAuditEvent(
            event_type=AuditEventType.RESOLUTION_SCAN_COMPLETE,
            session_id="system",
            project_id="proj-12345678",
            candidates_found=5,
            scan_duration_ms=123.45,
        )

        assert event.event_type == AuditEventType.RESOLUTION_SCAN_COMPLETE
        assert event.session_id == "system"
        assert event.project_id == "proj-12345678"
        assert event.candidates_found == 5
        assert event.scan_duration_ms == 123.45
        assert event.id  # Should have auto-generated ID
        assert event.timestamp > 0

    def test_entity_merge_event_creation(self) -> None:
        """Test creating an entity merge event."""
        event = ResolutionAuditEvent(
            event_type=AuditEventType.ENTITY_MERGE,
            session_id="session-abc",
            project_id="proj-12345678",
            survivor_id="node-1111",
            merged_id="node-2222",
            confidence=0.95,
            merge_type="auto",
        )

        assert event.event_type == AuditEventType.ENTITY_MERGE
        assert event.survivor_id == "node-1111"
        assert event.merged_id == "node-2222"
        assert event.confidence == 0.95
        assert event.merge_type == "auto"

    def test_merge_rejected_event_creation(self) -> None:
        """Test creating a merge rejected event."""
        event = ResolutionAuditEvent(
            event_type=AuditEventType.MERGE_REJECTED,
            session_id="session-xyz",
            project_id="proj-12345678",
            survivor_id="node-3333",
            merged_id="node-4444",
        )

        assert event.event_type == AuditEventType.MERGE_REJECTED
        assert event.survivor_id == "node-3333"
        assert event.merged_id == "node-4444"

    def test_resolution_event_serialization(self) -> None:
        """Test ResolutionAuditEvent serializes correctly."""
        event = ResolutionAuditEvent(
            event_type=AuditEventType.RESOLUTION_SCAN_COMPLETE,
            session_id="system",
            project_id="proj-test",
            candidates_found=10,
            auto_merged_count=2,
            queued_for_review_count=8,
            scan_duration_ms=500.0,
        )

        data = event.model_dump()

        assert data["event_type"] == "resolution_scan_complete"
        assert data["project_id"] == "proj-test"
        assert data["candidates_found"] == 10
        assert data["auto_merged_count"] == 2
        assert data["queued_for_review_count"] == 8


# -----------------------------------------------------------------------------
# AuditStats Resolution Fields Tests
# -----------------------------------------------------------------------------


class TestAuditStatsResolutionFields:
    """Test AuditStats includes resolution metrics."""

    def test_audit_stats_has_resolution_fields(self) -> None:
        """Test that AuditStats has resolution metric fields."""
        stats = AuditStats()

        assert hasattr(stats, "resolution_scans")
        assert hasattr(stats, "entities_merged")
        assert hasattr(stats, "merges_rejected")
        assert hasattr(stats, "avg_scan_duration_ms")

        # Defaults should be zero/None
        assert stats.resolution_scans == 0
        assert stats.entities_merged == 0
        assert stats.merges_rejected == 0
        assert stats.avg_scan_duration_ms is None

    def test_audit_stats_resolution_values(self) -> None:
        """Test AuditStats with resolution values."""
        stats = AuditStats(
            resolution_scans=15,
            entities_merged=42,
            merges_rejected=3,
            avg_scan_duration_ms=250.5,
        )

        assert stats.resolution_scans == 15
        assert stats.entities_merged == 42
        assert stats.merges_rejected == 3
        assert stats.avg_scan_duration_ms == 250.5


# -----------------------------------------------------------------------------
# AuditLogEntry from Resolution Event Tests
# -----------------------------------------------------------------------------


class TestAuditLogEntryFromResolutionEvent:
    """Test AuditLogEntry.from_resolution_event()."""

    def test_from_scan_complete_event(self) -> None:
        """Test creating log entry from scan complete event."""
        event = ResolutionAuditEvent(
            event_type=AuditEventType.RESOLUTION_SCAN_COMPLETE,
            session_id="system",
            project_id="proj-test",
            candidates_found=5,
            scan_duration_ms=150.0,
        )

        entry = AuditLogEntry.from_resolution_event(event)

        assert entry.event_type == "resolution_scan_complete"
        assert "5 candidates" in entry.summary
        assert "150ms" in entry.summary
        assert entry.duration_ms == 150.0

    def test_from_entity_merge_event(self) -> None:
        """Test creating log entry from entity merge event."""
        event = ResolutionAuditEvent(
            event_type=AuditEventType.ENTITY_MERGE,
            session_id="session-abc",
            project_id="proj-test",
            survivor_id="survivor-node",
            merged_id="merged-node",
            confidence=0.92,
            merge_type="user",
        )

        entry = AuditLogEntry.from_resolution_event(event)

        assert entry.event_type == "entity_merge"
        assert "merged-node" in entry.summary
        assert "survivor-node" in entry.summary
        assert "user" in entry.summary
        assert "92%" in entry.summary

    def test_from_merge_rejected_event(self) -> None:
        """Test creating log entry from merge rejected event."""
        event = ResolutionAuditEvent(
            event_type=AuditEventType.MERGE_REJECTED,
            session_id="session-xyz",
            project_id="proj-test",
            survivor_id="node-a",
            merged_id="node-b",
        )

        entry = AuditLogEntry.from_resolution_event(event)

        assert entry.event_type == "merge_rejected"
        assert "rejected" in entry.summary.lower()
        assert "node-a" in entry.summary
        assert "node-b" in entry.summary


# -----------------------------------------------------------------------------
# AuditService log_resolution_event Tests
# -----------------------------------------------------------------------------


class TestAuditServiceResolutionLogging:
    """Test AuditService.log_resolution_event() method."""

    @pytest.fixture
    def audit_service(self, tmp_path: Path) -> AuditService:
        """Create audit service with temporary storage."""
        return AuditService(data_path=tmp_path)

    @pytest.mark.asyncio
    async def test_log_resolution_scan_event(self, audit_service: AuditService) -> None:
        """Test logging a resolution scan event."""
        await audit_service.log_resolution_event(
            event_type=AuditEventType.RESOLUTION_SCAN_COMPLETE,
            project_id="proj-test",
            candidates_found=10,
            scan_duration_ms=200.0,
        )

        # Verify event was logged (system session)
        log = await audit_service.get_session_audit_log("system")
        assert log.total_count == 1
        assert log.entries[0].event_type == "resolution_scan_complete"

    @pytest.mark.asyncio
    async def test_log_resolution_event_with_session(
        self, audit_service: AuditService
    ) -> None:
        """Test logging resolution event with session ID."""
        await audit_service.log_resolution_event(
            event_type=AuditEventType.ENTITY_MERGE,
            project_id="proj-test",
            session_id="user-session-123",
            survivor_id="node-a",
            merged_id="node-b",
            confidence=0.88,
            merge_type="user",
        )

        # Verify event was logged to the specified session
        log = await audit_service.get_session_audit_log("user-session-123")
        assert log.total_count == 1
        assert log.entries[0].event_type == "entity_merge"

    @pytest.mark.asyncio
    async def test_log_resolution_updates_stats(
        self, audit_service: AuditService
    ) -> None:
        """Test that resolution events update aggregate stats."""
        # Log scan complete event
        await audit_service.log_resolution_event(
            event_type=AuditEventType.RESOLUTION_SCAN_COMPLETE,
            project_id="proj-1",
            candidates_found=5,
            scan_duration_ms=100.0,
        )

        # Log merge events
        await audit_service.log_resolution_event(
            event_type=AuditEventType.ENTITY_MERGE,
            project_id="proj-1",
            survivor_id="a",
            merged_id="b",
        )
        await audit_service.log_resolution_event(
            event_type=AuditEventType.ENTITY_MERGE,
            project_id="proj-1",
            survivor_id="c",
            merged_id="d",
        )

        # Log rejection
        await audit_service.log_resolution_event(
            event_type=AuditEventType.MERGE_REJECTED,
            project_id="proj-1",
            survivor_id="e",
            merged_id="f",
        )

        stats = await audit_service.get_stats()

        assert stats.resolution_scans == 1
        assert stats.entities_merged == 2
        assert stats.merges_rejected == 1
        assert stats.total_events == 4

    @pytest.mark.asyncio
    async def test_avg_scan_duration_calculation(
        self, audit_service: AuditService
    ) -> None:
        """Test running average calculation for scan duration."""
        # Log scans with known durations: 100, 200, 300
        # Expected average: (100 + 200 + 300) / 3 = 200
        for duration in [100.0, 200.0, 300.0]:
            await audit_service.log_resolution_event(
                event_type=AuditEventType.RESOLUTION_SCAN_COMPLETE,
                project_id="proj-avg",
                candidates_found=0,
                scan_duration_ms=duration,
            )

        stats = await audit_service.get_stats()

        assert stats.resolution_scans == 3
        assert stats.avg_scan_duration_ms is not None
        # Allow small floating point tolerance
        assert abs(stats.avg_scan_duration_ms - 200.0) < 0.01


# -----------------------------------------------------------------------------
# Feature Flag Tests
# -----------------------------------------------------------------------------


class TestResolutionFeatureFlag:
    """Test entity resolution feature flag behavior."""

    @pytest.mark.asyncio
    async def test_feature_flag_exists(self) -> None:
        """Test that entity_resolution_enabled setting exists."""
        settings = get_settings()
        assert hasattr(settings, "entity_resolution_enabled")
        # Default should be enabled
        assert settings.entity_resolution_enabled is True

    @pytest.mark.asyncio
    async def test_scan_returns_empty_when_disabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that scan_for_duplicates returns empty when disabled."""
        from app.core.config import get_settings as original_get_settings
        from app.services.kg_service import KnowledgeGraphService

        # Clear settings cache and set env var
        original_get_settings.cache_clear()
        monkeypatch.setenv("APP_ENTITY_RESOLUTION_ENABLED", "false")

        try:
            # Re-fetch settings
            settings = original_get_settings()
            assert settings.entity_resolution_enabled is False

            # Create service
            kg_service = KnowledgeGraphService(data_path=tmp_path)

            # scan_for_duplicates should return empty list
            result = await kg_service.scan_for_duplicates("nonexistent-project")
            assert result == []
        finally:
            # Restore cache
            original_get_settings.cache_clear()


# -----------------------------------------------------------------------------
# Integration Tests
# -----------------------------------------------------------------------------


class TestResolutionAuditIntegration:
    """Integration tests for resolution audit logging."""

    @pytest.fixture
    def audit_service(self, tmp_path: Path) -> AuditService:
        """Create audit service with temporary storage."""
        return AuditService(data_path=tmp_path)

    @pytest.mark.asyncio
    async def test_resolution_events_in_mixed_log(
        self, audit_service: AuditService
    ) -> None:
        """Test that resolution events work alongside other event types."""
        from app.models.audit import ToolAuditEvent

        session_id = "mixed-session"

        # Log a tool event
        await audit_service.log_event(
            ToolAuditEvent(
                event_type=AuditEventType.POST_TOOL_USE,
                session_id=session_id,
                tool_name="TestTool",
                tool_input={},
                success=True,
            )
        )

        # Log a resolution event
        await audit_service.log_resolution_event(
            event_type=AuditEventType.RESOLUTION_SCAN_COMPLETE,
            project_id="proj-mixed",
            session_id=session_id,
            candidates_found=3,
        )

        # Verify both events are in the log
        log = await audit_service.get_session_audit_log(session_id)
        assert log.total_count == 2

        event_types = {e.event_type for e in log.entries}
        assert "post_tool_use" in event_types
        assert "resolution_scan_complete" in event_types

    @pytest.mark.asyncio
    async def test_resolution_event_type_filter(
        self, audit_service: AuditService
    ) -> None:
        """Test filtering audit log by resolution event type."""
        session_id = "filter-session"

        # Log various resolution events
        await audit_service.log_resolution_event(
            event_type=AuditEventType.RESOLUTION_SCAN_COMPLETE,
            project_id="proj-filter",
            session_id=session_id,
            candidates_found=5,
        )
        await audit_service.log_resolution_event(
            event_type=AuditEventType.ENTITY_MERGE,
            project_id="proj-filter",
            session_id=session_id,
            survivor_id="a",
            merged_id="b",
        )

        # Filter by merge event type
        log = await audit_service.get_session_audit_log(
            session_id, event_type="entity_merge"
        )
        assert log.total_count == 1
        assert log.entries[0].event_type == "entity_merge"
