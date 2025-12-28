"""
Audit Event Models for Agent Hook Logging.

This module defines Pydantic models for tracking agent tool usage,
session events, and audit trails through Claude Agent SDK hooks.

Hook events flow:
    PreToolUse  → Log intent, can block dangerous operations
    PostToolUse → Log results and outcomes
    Stop        → Log session termination
    SubagentStop → Log subagent completions
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AuditEventType(str, Enum):
    """Types of audit events captured by hooks."""

    # Tool usage events
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    TOOL_BLOCKED = "tool_blocked"

    # Session lifecycle events
    SESSION_STOP = "session_stop"
    SUBAGENT_STOP = "subagent_stop"

    # Entity Resolution events
    RESOLUTION_SCAN_START = "resolution_scan_start"
    RESOLUTION_SCAN_COMPLETE = "resolution_scan_complete"
    ENTITY_MERGE = "entity_merge"
    MERGE_REJECTED = "merge_rejected"


class AuditEventBase(BaseModel):
    """Base model for all audit events.

    All audit events share common fields for correlation and timing.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: AuditEventType
    session_id: str
    timestamp: float = Field(default_factory=time.time)


class ToolAuditEvent(AuditEventBase):
    """Audit event for tool usage (PreToolUse/PostToolUse hooks).

    Captures the full context of tool invocations including inputs,
    outputs, and timing for compliance and debugging.

    Attributes:
        tool_name: Name of the tool being invoked (e.g., "Bash", "Write")
        tool_input: Input arguments passed to the tool
        tool_response: Response from tool (PostToolUse only)
        blocked: Whether the tool was blocked by a hook
        block_reason: Reason for blocking (if blocked=True)
        duration_ms: Execution time in milliseconds (PostToolUse only)
        success: Whether the tool executed successfully (PostToolUse only)
    """

    tool_name: str
    tool_input: dict[str, Any] = Field(default_factory=dict)
    tool_response: Any | None = None
    blocked: bool = False
    block_reason: str | None = None
    duration_ms: float | None = None
    success: bool | None = None


class SessionAuditEvent(AuditEventBase):
    """Audit event for session lifecycle (Stop/SubagentStop hooks).

    Captures session termination details for tracking agent lifecycle
    and debugging incomplete sessions.

    Attributes:
        subagent_id: ID of the subagent (SubagentStop only)
        stop_reason: Reason for stopping (if available)
        total_turns: Number of turns in the session
        total_tools_used: Count of tools invoked during session
    """

    subagent_id: str | None = None
    stop_reason: str | None = None
    total_turns: int | None = None
    total_tools_used: int | None = None


class ResolutionAuditEvent(AuditEventBase):
    """Audit event for entity resolution operations.

    Captures metrics and details for duplicate detection and merge
    operations in the knowledge graph.

    Attributes:
        project_id: ID of the KG project
        candidates_found: Number of duplicate candidates found (scan events)
        auto_merged_count: Number of entities auto-merged (scan events)
        queued_for_review_count: Number of candidates queued for review (scan events)
        scan_duration_ms: Duration of the scan in milliseconds
        survivor_id: ID of the surviving node (merge events)
        merged_id: ID of the merged (removed) node (merge events)
        confidence: Confidence score of the merge decision
        merge_type: How the merge was triggered (auto, user, agent)
    """

    project_id: str
    candidates_found: int | None = None
    auto_merged_count: int | None = None
    queued_for_review_count: int | None = None
    scan_duration_ms: float | None = None
    survivor_id: str | None = None
    merged_id: str | None = None
    confidence: float | None = None
    merge_type: str | None = None


# Union type for all audit events (useful for serialization)
AuditEvent = ToolAuditEvent | SessionAuditEvent | ResolutionAuditEvent


class AuditLogEntry(BaseModel):
    """A single entry in the audit log with denormalized fields.

    Optimized for API responses with flattened structure for easy filtering.
    """

    id: str
    event_type: str
    session_id: str
    timestamp: float
    tool_name: str | None = None
    blocked: bool = False
    success: bool | None = None
    duration_ms: float | None = None
    summary: str = ""

    @classmethod
    def from_tool_event(cls, event: ToolAuditEvent) -> AuditLogEntry:
        """Create log entry from ToolAuditEvent."""
        if event.blocked:
            summary = f"Blocked: {event.block_reason or 'unknown reason'}"
        elif event.event_type == AuditEventType.POST_TOOL_USE:
            status = "success" if event.success else "failed"
            duration = f" ({event.duration_ms:.0f}ms)" if event.duration_ms else ""
            summary = f"{event.tool_name} {status}{duration}"
        else:
            summary = f"Invoking {event.tool_name}"

        return cls(
            id=event.id,
            event_type=event.event_type.value,
            session_id=event.session_id,
            timestamp=event.timestamp,
            tool_name=event.tool_name,
            blocked=event.blocked,
            success=event.success,
            duration_ms=event.duration_ms,
            summary=summary,
        )

    @classmethod
    def from_session_event(cls, event: SessionAuditEvent) -> AuditLogEntry:
        """Create log entry from SessionAuditEvent."""
        if event.event_type == AuditEventType.SUBAGENT_STOP:
            summary = f"Subagent {event.subagent_id} stopped"
        else:
            summary = f"Session stopped: {event.stop_reason or 'completed'}"

        return cls(
            id=event.id,
            event_type=event.event_type.value,
            session_id=event.session_id,
            timestamp=event.timestamp,
            summary=summary,
        )

    @classmethod
    def from_resolution_event(cls, event: ResolutionAuditEvent) -> AuditLogEntry:
        """Create log entry from ResolutionAuditEvent."""
        if event.event_type == AuditEventType.RESOLUTION_SCAN_START:
            summary = f"Resolution scan started for project {event.project_id}"
        elif event.event_type == AuditEventType.RESOLUTION_SCAN_COMPLETE:
            duration = f" ({event.scan_duration_ms:.0f}ms)" if event.scan_duration_ms else ""
            summary = f"Resolution scan complete: {event.candidates_found or 0} candidates{duration}"
        elif event.event_type == AuditEventType.ENTITY_MERGE:
            conf = f" ({event.confidence:.0%})" if event.confidence else ""
            summary = f"Entity merge ({event.merge_type}): {event.merged_id} -> {event.survivor_id}{conf}"
        elif event.event_type == AuditEventType.MERGE_REJECTED:
            summary = f"Merge rejected: {event.merged_id} and {event.survivor_id}"
        else:
            summary = f"Resolution event: {event.event_type.value}"

        return cls(
            id=event.id,
            event_type=event.event_type.value,
            session_id=event.session_id,
            timestamp=event.timestamp,
            duration_ms=event.scan_duration_ms,
            summary=summary,
        )


class AuditLogResponse(BaseModel):
    """API response containing audit log entries.

    Supports pagination for large audit logs.
    """

    session_id: str | None = None
    entries: list[AuditLogEntry] = Field(default_factory=list)
    total_count: int = 0
    has_more: bool = False


class AuditStats(BaseModel):
    """Aggregate statistics for audit events.

    Provides high-level metrics for monitoring and dashboards.
    """

    # Tool usage metrics
    total_events: int = 0
    tools_invoked: int = 0
    tools_blocked: int = 0
    tools_succeeded: int = 0
    tools_failed: int = 0
    avg_tool_duration_ms: float | None = None

    # Session lifecycle metrics
    sessions_stopped: int = 0
    subagents_stopped: int = 0

    # Entity Resolution metrics
    resolution_scans: int = 0
    entities_merged: int = 0
    merges_rejected: int = 0
    avg_scan_duration_ms: float | None = None
