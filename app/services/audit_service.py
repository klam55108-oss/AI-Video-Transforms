"""
Audit Service for Agent Hook Logging.

Provides persistent storage and querying for audit events captured
by Claude Agent SDK hooks. Uses JSON file storage with in-memory
caching for performance.

Architecture:
    data/audit/
    ├── sessions/
    │   └── {session_id}.json  # Per-session audit logs
    └── global_stats.json       # Aggregate statistics
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import stat
from collections import OrderedDict
from pathlib import Path
from typing import Any

import aiofiles

from app.core.config import get_settings
from app.models.audit import (
    AuditEvent,
    AuditEventType,
    AuditLogEntry,
    AuditLogResponse,
    AuditStats,
    SessionAuditEvent,
    ToolAuditEvent,
)

logger = logging.getLogger(__name__)

# Security: File permissions for audit logs (owner: rw, group: r, others: none)
AUDIT_FILE_MODE: int = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP  # 0o640


class AuditService:
    """
    Service for storing and querying agent audit events.

    Provides thread-safe, async-compatible operations with:
    - Per-session JSON file persistence
    - In-memory LRU caching for hot sessions
    - Aggregate statistics tracking
    - Query/filter capabilities

    Follows the ServiceContainer pattern for FastAPI lifecycle management.
    """

    def __init__(self, data_path: Path | None = None) -> None:
        """Initialize audit service.

        Args:
            data_path: Base data directory. Defaults to settings.data_path.
        """
        settings = get_settings()
        self._data_path = data_path or Path(settings.data_path)
        self._audit_path = self._data_path / "audit"
        self._sessions_path = self._audit_path / "sessions"
        self._stats_path = self._audit_path / "global_stats.json"

        # Configuration from settings (not magic numbers)
        self._retention_hours = settings.audit_retention_hours
        self._max_events_per_session = settings.audit_max_events_per_session
        self._cache_max_sessions = settings.audit_cache_max_sessions

        # In-memory cache with LRU eviction
        self._session_cache: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        self._cache_lock = asyncio.Lock()

        # Aggregate stats (cached, persisted periodically)
        self._stats = AuditStats()
        self._stats_dirty = False

        # Track count of events with duration for accurate average calculation
        self._events_with_duration_count: int = 0

        # Ensure directories exist
        self._sessions_path.mkdir(parents=True, exist_ok=True)

        # Load existing stats
        self._load_stats()

    def _load_stats(self) -> None:
        """Load aggregate stats from disk."""
        try:
            if self._stats_path.exists():
                data = json.loads(self._stats_path.read_text())
                self._stats = AuditStats.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to load audit stats: {e}")
            self._stats = AuditStats()

    async def _save_stats(self) -> None:
        """Persist aggregate stats to disk."""
        if not self._stats_dirty:
            return

        try:
            self._stats_path.write_text(
                json.dumps(self._stats.model_dump(), indent=2)
            )
            self._stats_dirty = False
        except Exception as e:
            logger.error(f"Failed to save audit stats: {e}")

    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session's audit log."""
        return self._sessions_path / f"{session_id}.json"

    async def _load_session_events(self, session_id: str) -> list[dict[str, Any]]:
        """Load events for a session from disk or cache.

        Args:
            session_id: The session to load events for.

        Returns:
            List of event dictionaries (raw JSON format).
        """
        async with self._cache_lock:
            # Check cache first
            if session_id in self._session_cache:
                # Move to end (most recently used)
                self._session_cache.move_to_end(session_id)
                return self._session_cache[session_id]

            # Load from disk using async I/O
            session_path = self._get_session_path(session_id)
            events: list[dict[str, Any]] = []

            if session_path.exists():
                try:
                    async with aiofiles.open(session_path, mode="r") as f:
                        content = await f.read()
                    data = json.loads(content)
                    events = data.get("events", [])
                except Exception as e:
                    logger.error(f"Failed to load audit log for {session_id}: {e}")

            # Cache with LRU eviction
            if len(self._session_cache) >= self._cache_max_sessions:
                self._session_cache.popitem(last=False)  # Remove oldest

            self._session_cache[session_id] = events
            return events

    async def _save_session_events(
        self, session_id: str, events: list[dict[str, Any]]
    ) -> None:
        """Persist session events to disk using async I/O.

        Args:
            session_id: The session to save events for.
            events: List of event dictionaries.
        """
        session_path = self._get_session_path(session_id)
        try:
            data = {
                "session_id": session_id,
                "event_count": len(events),
                "events": events,
            }
            # Use aiofiles for non-blocking async I/O
            async with aiofiles.open(session_path, mode="w") as f:
                await f.write(json.dumps(data, indent=2))

            # Set secure file permissions (owner: rw, group: r, others: none)
            os.chmod(session_path, AUDIT_FILE_MODE)
        except Exception as e:
            logger.error(f"Failed to save audit log for {session_id}: {e}")

    async def log_event(self, event: AuditEvent) -> None:
        """Log an audit event.

        Persists the event to both cache and disk, updating aggregate stats.

        Args:
            event: The audit event to log.
        """
        session_id = event.session_id
        event_dict = event.model_dump()

        # Load existing events
        events = await self._load_session_events(session_id)

        # Enforce per-session limit to prevent unbounded growth.
        # Logic: If at capacity (N events), keep N-1 oldest before appending new event.
        # Result: After append, we have exactly N events (the limit).
        # Example: If max=10000 and we have 10000 events, slice keeps 9999, then append = 10000.
        if len(events) >= self._max_events_per_session:
            events = events[-(self._max_events_per_session - 1) :]
            logger.warning(
                f"Audit log for {session_id} exceeded max size, pruning old events"
            )

        # Append new event
        events.append(event_dict)

        # Update cache
        async with self._cache_lock:
            self._session_cache[session_id] = events

        # Persist to disk
        await self._save_session_events(session_id, events)

        # Update aggregate stats
        self._update_stats(event)

        logger.debug(
            f"Logged audit event: {event.event_type.value} for session {session_id}"
        )

    def _update_stats(self, event: AuditEvent) -> None:
        """Update aggregate statistics based on event type."""
        self._stats.total_events += 1
        self._stats_dirty = True

        if isinstance(event, ToolAuditEvent):
            if event.event_type == AuditEventType.PRE_TOOL_USE:
                self._stats.tools_invoked += 1
            elif event.event_type == AuditEventType.TOOL_BLOCKED:
                self._stats.tools_blocked += 1
            elif event.event_type == AuditEventType.POST_TOOL_USE:
                if event.success is True:
                    self._stats.tools_succeeded += 1
                elif event.success is False:
                    self._stats.tools_failed += 1

                # Update average duration using accurate count of events with duration.
                # Using succeeded + failed is inaccurate because some events may lack duration.
                if event.duration_ms is not None:
                    self._events_with_duration_count += 1
                    n = self._events_with_duration_count

                    if self._stats.avg_tool_duration_ms is None:
                        self._stats.avg_tool_duration_ms = event.duration_ms
                    else:
                        # Running average: new_avg = (old_avg * (n-1) + new_value) / n
                        self._stats.avg_tool_duration_ms = (
                            (self._stats.avg_tool_duration_ms * (n - 1))
                            + event.duration_ms
                        ) / n

        elif isinstance(event, SessionAuditEvent):
            if event.event_type == AuditEventType.SESSION_STOP:
                self._stats.sessions_stopped += 1
            elif event.event_type == AuditEventType.SUBAGENT_STOP:
                self._stats.subagents_stopped += 1

    async def get_session_audit_log(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
        event_type: str | None = None,
    ) -> AuditLogResponse:
        """Get audit log for a specific session.

        Args:
            session_id: The session to get logs for.
            limit: Maximum number of entries to return.
            offset: Number of entries to skip.
            event_type: Filter by event type (optional).

        Returns:
            AuditLogResponse with paginated entries.
        """
        events = await self._load_session_events(session_id)

        # Filter by event type if specified
        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]

        total_count = len(events)

        # Apply pagination (reverse to show newest first)
        events = list(reversed(events))
        paginated = events[offset : offset + limit]

        # Convert to log entries
        entries = []
        for event_dict in paginated:
            try:
                entry = self._dict_to_log_entry(event_dict)
                entries.append(entry)
            except Exception as e:
                logger.warning(f"Failed to parse audit event: {e}")

        return AuditLogResponse(
            session_id=session_id,
            entries=entries,
            total_count=total_count,
            has_more=(offset + limit) < total_count,
        )

    def _dict_to_log_entry(self, event_dict: dict[str, Any]) -> AuditLogEntry:
        """Convert event dictionary to AuditLogEntry."""
        event_type = event_dict.get("event_type", "")

        if event_type in (
            AuditEventType.PRE_TOOL_USE.value,
            AuditEventType.POST_TOOL_USE.value,
            AuditEventType.TOOL_BLOCKED.value,
        ):
            tool_event = ToolAuditEvent.model_validate(event_dict)
            return AuditLogEntry.from_tool_event(tool_event)
        else:
            session_event = SessionAuditEvent.model_validate(event_dict)
            return AuditLogEntry.from_session_event(session_event)

    async def get_stats(self) -> AuditStats:
        """Get aggregate audit statistics.

        Returns:
            AuditStats with current aggregate metrics.
        """
        # Persist any pending stats
        await self._save_stats()
        return self._stats

    async def list_sessions_with_audits(
        self, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List sessions that have audit logs.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of session info dicts with event counts.
        """
        sessions = []

        try:
            session_files = sorted(
                self._sessions_path.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,  # Newest first
            )

            for session_file in session_files[:limit]:
                session_id = session_file.stem
                try:
                    data = json.loads(session_file.read_text())
                    sessions.append(
                        {
                            "session_id": session_id,
                            "event_count": data.get("event_count", 0),
                            "last_modified": session_file.stat().st_mtime,
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to read audit file {session_file}: {e}")

        except Exception as e:
            logger.error(f"Failed to list audit sessions: {e}")

        return sessions

    async def cleanup_old_logs(self) -> int:
        """Remove audit logs older than retention period.

        Returns:
            Number of sessions cleaned up.
        """
        import time

        cutoff_time = time.time() - (self._retention_hours * 3600)
        cleaned = 0

        try:
            for session_file in self._sessions_path.glob("*.json"):
                if session_file.stat().st_mtime < cutoff_time:
                    session_id = session_file.stem

                    # Remove from cache
                    async with self._cache_lock:
                        self._session_cache.pop(session_id, None)

                    # Delete file
                    session_file.unlink()
                    cleaned += 1
                    logger.debug(f"Cleaned up old audit log: {session_id}")

        except Exception as e:
            logger.error(f"Error during audit log cleanup: {e}")

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old audit logs")

        return cleaned
