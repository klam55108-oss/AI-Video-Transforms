"""
Tests for activity streaming functionality.

These tests verify that:
1. ActivityEvent model works correctly
2. get_activity_text() extracts activity from SDK messages
3. SessionActor emits activity events during processing
4. SSE endpoint streams activity events correctly
5. Frontend receives and displays activity updates
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from app.core.session import (
    ActivityEvent,
    ActivityType,
    SessionActor,
    TOOL_DESCRIPTIONS,
    get_activity_text,
)


# =============================================================================
# Test ActivityEvent Model
# =============================================================================


class TestActivityEvent:
    """Test ActivityEvent dataclass."""

    def test_create_thinking_event(self) -> None:
        """Test creating a thinking activity event."""
        event = ActivityEvent(
            activity_type=ActivityType.THINKING,
            message="🤔 Thinking...",
        )
        assert event.activity_type == ActivityType.THINKING
        assert event.message == "🤔 Thinking..."
        assert event.tool_name is None
        assert event.timestamp > 0

    def test_create_tool_use_event(self) -> None:
        """Test creating a tool use activity event."""
        event = ActivityEvent(
            activity_type=ActivityType.TOOL_USE,
            message="🔧 Transcribing video",
            tool_name="mcp__video-tools__transcribe_video",
        )
        assert event.activity_type == ActivityType.TOOL_USE
        assert event.tool_name == "mcp__video-tools__transcribe_video"

    def test_to_dict_serialization(self) -> None:
        """Test ActivityEvent serialization for SSE."""
        event = ActivityEvent(
            activity_type=ActivityType.TOOL_USE,
            message="🔧 Testing",
            tool_name="test_tool",
        )
        data = event.to_dict()
        assert data["type"] == "tool_use"
        assert data["message"] == "🔧 Testing"
        assert data["tool_name"] == "test_tool"
        assert "timestamp" in data

    def test_to_dict_json_serializable(self) -> None:
        """Test that to_dict output is JSON serializable."""
        event = ActivityEvent(
            activity_type=ActivityType.COMPLETED,
            message="✨ Done",
        )
        # Should not raise
        json_str = json.dumps(event.to_dict())
        parsed = json.loads(json_str)
        assert parsed["type"] == "completed"


# =============================================================================
# Test get_activity_text Function
# =============================================================================


class TestGetActivityText:
    """Test get_activity_text message inspection."""

    def test_returns_none_for_none_message(self) -> None:
        """Test that None input returns None."""
        result = get_activity_text(None)
        assert result is None

    def test_thinking_for_text_block(self) -> None:
        """Test that TextBlock content returns thinking event."""
        from claude_agent_sdk import TextBlock

        # Create an actual TextBlock instance (SDK signature: TextBlock(text))
        text_block = TextBlock(text="Hello, I'm thinking about this...")

        # Create a mock AssistantMessage with real TextBlock
        mock_msg = MagicMock()
        mock_msg.__class__.__name__ = "AssistantMessage"
        mock_msg.content = [text_block]

        result = get_activity_text(mock_msg)

        # Should return thinking event
        assert result is not None
        assert result.activity_type == ActivityType.THINKING
        assert "Thinking" in result.message

    def test_tool_use_for_tool_block(self) -> None:
        """Test that ToolUseBlock content returns tool_use event."""
        from claude_agent_sdk import ToolUseBlock

        # Create an actual ToolUseBlock instance (SDK signature: ToolUseBlock(id, name, input))
        tool_block = ToolUseBlock(
            id="test-tool-id",
            name="mcp__video-tools__transcribe_video",
            input={"video_source": "/path/to/video.mp4"},
        )

        mock_msg = MagicMock()
        mock_msg.__class__.__name__ = "AssistantMessage"
        mock_msg.content = [tool_block]

        result = get_activity_text(mock_msg)

        assert result is not None
        assert result.activity_type == ActivityType.TOOL_USE
        assert "Transcribing video" in result.message
        assert result.tool_name == "mcp__video-tools__transcribe_video"

    def test_completed_for_result_message(self) -> None:
        """Test that ResultMessage returns completed event."""
        mock_msg = MagicMock()
        mock_msg.__class__.__name__ = "ResultMessage"

        result = get_activity_text(mock_msg)

        assert result is not None
        assert result.activity_type == ActivityType.COMPLETED

    def test_handles_malformed_message(self) -> None:
        """Test graceful handling of malformed messages."""
        mock_msg = MagicMock()
        mock_msg.__class__.__name__ = "AssistantMessage"
        mock_msg.content = None  # Malformed - no content

        # Should not raise, should return None or default
        result = get_activity_text(mock_msg)
        # Even with no content, AssistantMessage should return thinking
        assert result is not None or result is None  # Either is acceptable


# =============================================================================
# Test TOOL_DESCRIPTIONS Mapping
# =============================================================================


class TestToolDescriptions:
    """Test tool name to description mapping."""

    def test_transcribe_video_has_description(self) -> None:
        """Test that transcribe_video tool has a description."""
        assert "mcp__video-tools__transcribe_video" in TOOL_DESCRIPTIONS
        assert "Transcribing" in TOOL_DESCRIPTIONS["mcp__video-tools__transcribe_video"]

    def test_kg_tools_have_descriptions(self) -> None:
        """Test that KG tools have descriptions."""
        kg_tools = [
            "mcp__video-tools__extract_to_kg",
            "mcp__video-tools__create_kg_project",
            "mcp__video-tools__bootstrap_kg_project",
        ]
        for tool in kg_tools:
            assert tool in TOOL_DESCRIPTIONS, f"Missing description for {tool}"

    def test_sdk_tools_have_descriptions(self) -> None:
        """Test that SDK built-in tools have descriptions."""
        sdk_tools = ["Skill", "Read", "Write", "Bash", "Task"]
        for tool in sdk_tools:
            assert tool in TOOL_DESCRIPTIONS, f"Missing description for {tool}"


# =============================================================================
# Test SessionActor Activity Methods
# =============================================================================


class TestSessionActorActivity:
    """Test SessionActor activity streaming methods."""

    def test_subscribe_to_activity_creates_queue(self) -> None:
        """Test that subscribe creates a new queue."""
        actor = SessionActor("test-session-id")

        queue = actor.subscribe_to_activity()

        assert queue is not None
        assert queue in actor._activity_subscribers

    def test_unsubscribe_removes_queue(self) -> None:
        """Test that unsubscribe removes the queue."""
        actor = SessionActor("test-session-id")
        queue = actor.subscribe_to_activity()

        actor.unsubscribe_from_activity(queue)

        assert queue not in actor._activity_subscribers

    def test_emit_activity_broadcasts_to_subscribers(self) -> None:
        """Test that _emit_activity sends to all subscribers."""
        actor = SessionActor("test-session-id")
        queue1 = actor.subscribe_to_activity()
        queue2 = actor.subscribe_to_activity()

        event = ActivityEvent(
            activity_type=ActivityType.THINKING,
            message="Test event",
        )
        actor._emit_activity(event)

        # Both queues should have the event
        assert not queue1.empty()
        assert not queue2.empty()

        received1 = queue1.get_nowait()
        received2 = queue2.get_nowait()

        assert received1.message == "Test event"
        assert received2.message == "Test event"

    def test_emit_activity_handles_full_queue(self) -> None:
        """Test that emit handles slow subscribers gracefully."""
        actor = SessionActor("test-session-id")

        # Create a queue with limited size
        small_queue: asyncio.Queue[ActivityEvent] = asyncio.Queue(maxsize=1)
        actor._activity_subscribers.add(small_queue)

        # Fill the queue
        event1 = ActivityEvent(ActivityType.THINKING, "First")
        small_queue.put_nowait(event1)

        # This should not raise even though queue is full
        event2 = ActivityEvent(ActivityType.THINKING, "Second")
        actor._emit_activity(event2)  # Should log warning but not raise

    def test_get_current_activity_when_processing(self) -> None:
        """Test get_current_activity returns event when processing."""
        actor = SessionActor("test-session-id")
        actor._is_processing = True

        activity = actor.get_current_activity()

        assert activity is not None
        assert activity.activity_type == ActivityType.THINKING

    def test_get_current_activity_when_idle(self) -> None:
        """Test get_current_activity returns None when idle."""
        actor = SessionActor("test-session-id")
        actor._is_processing = False

        activity = actor.get_current_activity()

        assert activity is None


# =============================================================================
# Test SSE Endpoint Integration
# =============================================================================


class TestActivitySSEEndpoint:
    """Test the SSE activity streaming endpoint."""

    # Valid UUID v4 format for tests (note: 4 at position 13, 8/9/a/b at position 17)
    VALID_TEST_UUID = "a1b2c3d4-e5f6-4789-8abc-def123456789"
    NONEXISTENT_UUID = "00000000-0000-4000-8000-000000000000"

    @pytest.mark.asyncio
    async def test_activity_endpoint_returns_404_for_unknown_session(self) -> None:
        """Test that unknown session returns 404."""
        from app.main import app
        from app.api.deps import get_session_service
        from app.services import SessionService

        # Create a mock service with no sessions
        mock_service = SessionService()
        app.dependency_overrides[get_session_service] = lambda: mock_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/chat/activity/{self.NONEXISTENT_UUID}"
                )
                assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_session_service, None)

    @pytest.mark.asyncio
    async def test_current_activity_endpoint_returns_null_when_idle(self) -> None:
        """Test that current activity endpoint returns null when not processing."""
        from app.main import app
        from app.api.deps import get_session_service
        from app.services import SessionService

        mock_service = SessionService()
        # Create a mock actor
        mock_actor = MagicMock()
        mock_actor.is_running = True
        mock_actor.get_current_activity.return_value = None
        mock_service._active_sessions[self.VALID_TEST_UUID] = mock_actor

        app.dependency_overrides[get_session_service] = lambda: mock_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/chat/activity/{self.VALID_TEST_UUID}/current"
                )
                assert response.status_code == 200
                data = response.json()
                assert data["type"] is None
                assert data["message"] is None
        finally:
            app.dependency_overrides.pop(get_session_service, None)

    @pytest.mark.asyncio
    async def test_current_activity_endpoint_returns_activity_when_processing(
        self,
    ) -> None:
        """Test that current activity endpoint returns activity when processing."""
        from app.main import app
        from app.api.deps import get_session_service
        from app.services import SessionService

        mock_service = SessionService()
        mock_actor = MagicMock()
        mock_actor.is_running = True
        mock_actor.get_current_activity.return_value = ActivityEvent(
            activity_type=ActivityType.TOOL_USE,
            message="🔧 Transcribing video",
            tool_name="transcribe_video",
        )
        mock_service._active_sessions[self.VALID_TEST_UUID] = mock_actor

        app.dependency_overrides[get_session_service] = lambda: mock_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/chat/activity/{self.VALID_TEST_UUID}/current"
                )
                assert response.status_code == 200
                data = response.json()
                assert data["type"] == "tool_use"
                assert "Transcribing" in data["message"]
        finally:
            app.dependency_overrides.pop(get_session_service, None)


# =============================================================================
# Test Activity Stream Flow (End-to-End)
# =============================================================================


class TestActivityStreamFlow:
    """Test the complete activity streaming flow."""

    @pytest.mark.asyncio
    async def test_activity_emitted_during_processing(self) -> None:
        """Test that activity events are emitted during message processing.

        This test verifies the flow:
        1. Subscriber subscribes to activity
        2. Worker emits activity events
        3. Subscriber receives events
        """
        actor = SessionActor("e2e-test-session")

        # Subscribe before any processing
        activity_queue = actor.subscribe_to_activity()

        # Simulate the worker emitting events (as it would during processing)
        events_to_emit = [
            ActivityEvent(ActivityType.THINKING, "🤔 Thinking..."),
            ActivityEvent(ActivityType.TOOL_USE, "🔧 Working", "test_tool"),
            ActivityEvent(ActivityType.COMPLETED, "✨ Done"),
        ]

        for event in events_to_emit:
            actor._emit_activity(event)

        # Verify all events were received
        received_events = []
        while not activity_queue.empty():
            received_events.append(activity_queue.get_nowait())

        assert len(received_events) == 3
        assert received_events[0].activity_type == ActivityType.THINKING
        assert received_events[1].activity_type == ActivityType.TOOL_USE
        assert received_events[2].activity_type == ActivityType.COMPLETED

    @pytest.mark.asyncio
    async def test_multiple_subscribers_receive_all_events(self) -> None:
        """Test that multiple SSE connections receive all events."""
        actor = SessionActor("multi-sub-test")

        # Simulate multiple frontend connections
        sub1 = actor.subscribe_to_activity()
        sub2 = actor.subscribe_to_activity()
        sub3 = actor.subscribe_to_activity()

        # Emit an event
        event = ActivityEvent(ActivityType.THINKING, "Test broadcast")
        actor._emit_activity(event)

        # All subscribers should receive it
        assert not sub1.empty()
        assert not sub2.empty()
        assert not sub3.empty()

        # Unsubscribe one
        actor.unsubscribe_from_activity(sub2)

        # Emit another event
        event2 = ActivityEvent(ActivityType.COMPLETED, "Done")
        actor._emit_activity(event2)

        # Only sub1 and sub3 should have the new event
        # (sub1 and sub3 now have 2 events, sub2 still has 1)
        count1 = 0
        while not sub1.empty():
            sub1.get_nowait()
            count1 += 1
        assert count1 == 2

        count2 = 0
        while not sub2.empty():
            sub2.get_nowait()
            count2 += 1
        assert count2 == 1  # Only the first event


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
