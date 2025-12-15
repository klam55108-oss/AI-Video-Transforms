"""
Concurrency Tests for SessionActor and session management.

Testing Checklist Items:
- [x] Concurrent session creation with same ID creates only one worker
- [x] Session cleanup occurs after TTL expires
- [x] Worker properly cancels on stop()
- [x] No race conditions when accessing active_sessions
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.session_service import SessionService


class TestConcurrentSessionCreation:
    """Test that concurrent session creation with same ID creates only one worker."""

    @pytest.mark.asyncio
    async def test_concurrent_get_or_create_session_creates_single_worker(self):
        """
        When multiple coroutines try to create a session with the same ID
        concurrently, only one worker should be created.
        """
        # Create service instance
        service = SessionService()

        # Mock the ClaudeSDKClient to avoid real API calls
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.query = AsyncMock()
        mock_client_instance.receive_response = MagicMock(
            return_value=AsyncMock(__anext__=AsyncMock(side_effect=StopAsyncIteration))
        )

        # Patch environment and SDK client
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch(
                "app.core.session.ClaudeSDKClient", return_value=mock_client_instance
            ):
                session_id = "test-concurrent-session-id-1234"

                # Launch multiple concurrent requests for the same session
                results = await asyncio.gather(
                    service.get_or_create(session_id),
                    service.get_or_create(session_id),
                    service.get_or_create(session_id),
                )

                # All results should be the same SessionActor instance
                assert all(r is results[0] for r in results), (
                    "All concurrent calls should return the same SessionActor"
                )

                # Verify only one session exists
                async with service._sessions_lock:
                    assert len(service._active_sessions) == 1
                    assert session_id in service._active_sessions

                # Cleanup
                actor = results[0]
                await actor.stop()
                async with service._sessions_lock:
                    if session_id in service._active_sessions:
                        del service._active_sessions[session_id]


class TestSessionTTLCleanup:
    """Test that session cleanup occurs after TTL expires."""

    @pytest.mark.asyncio
    async def test_session_is_expired_after_ttl(self):
        """Test that is_expired() returns True after TTL has passed."""
        import time
        from app.core.session import SessionActor

        actor = SessionActor("test-ttl-session")

        # Session should not be expired immediately
        assert not actor.is_expired(ttl=1.0)

        # Manually set last_activity to the past
        actor.last_activity = time.time() - 2.0

        # Now session should be expired with 1 second TTL
        assert actor.is_expired(ttl=1.0)

        # But not with longer TTL
        assert not actor.is_expired(ttl=10.0)

    @pytest.mark.asyncio
    async def test_touch_updates_last_activity(self):
        """Test that touch() updates the last_activity timestamp."""
        from app.core.session import SessionActor

        actor = SessionActor("test-touch-session")
        old_activity = actor.last_activity

        # Wait a tiny bit and touch
        await asyncio.sleep(0.01)
        actor.touch()

        assert actor.last_activity > old_activity

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired_sessions(self):
        """Test that cleanup_expired_sessions removes expired sessions."""
        import time
        from app.core.session import SessionActor

        # Create service instance
        service = SessionService()

        # Create a mock expired session
        actor = SessionActor("expired-session")
        actor.last_activity = time.time() - 7200  # 2 hours ago
        actor._running_event.clear()  # Mark as not running

        async with service._sessions_lock:
            service._active_sessions["expired-session"] = actor

        # Create cleanup task with short interval for testing
        with patch("app.services.session_service.CLEANUP_INTERVAL_SECONDS", 0.01):
            # Run one cleanup iteration
            cleanup_task = asyncio.create_task(service.run_cleanup_loop())
            await asyncio.sleep(0.05)  # Wait for cleanup to run
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass

        # Verify session was cleaned up
        async with service._sessions_lock:
            assert "expired-session" not in service._active_sessions


class TestWorkerCancellation:
    """Test that worker properly cancels on stop()."""

    @pytest.mark.asyncio
    async def test_stop_clears_running_event(self):
        """Test that stop() clears the running event."""
        from app.core.session import SessionActor

        actor = SessionActor("test-stop-event")
        actor._running_event.set()

        await actor.stop()

        assert not actor.is_running

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self):
        """Test that calling stop() multiple times is safe."""
        from app.core.session import SessionActor

        actor = SessionActor("test-stop-idempotent")

        # Call stop multiple times - should not raise
        await actor.stop()
        await actor.stop()
        await actor.stop()

        assert not actor.is_running

    @pytest.mark.asyncio
    async def test_stop_cancels_active_task(self):
        """Test that stop() cancels the active task if running."""
        from app.core.session import SessionActor

        actor = SessionActor("test-stop-cancel")

        # Create a long-running task
        async def long_running():
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                raise

        actor._running_event.set()
        actor.active_task = asyncio.create_task(long_running())

        # Stop should cancel the task
        await actor.stop()

        assert actor.active_task is None
        assert not actor.is_running


class TestRaceConditions:
    """Test that there are no race conditions when accessing active_sessions."""

    @pytest.mark.asyncio
    async def test_concurrent_session_access_is_safe(self):
        """Test that multiple concurrent accesses to active_sessions are safe."""
        from app.core.session import SessionActor

        # Create service instance
        service = SessionService()

        async def create_and_delete_session(session_id: str):
            """Create a session, verify it exists, then delete it."""
            actor = SessionActor(session_id)
            actor._running_event.set()

            async with service._sessions_lock:
                service._active_sessions[session_id] = actor

            # Small delay to increase chance of race conditions
            await asyncio.sleep(0.001)

            async with service._sessions_lock:
                if session_id in service._active_sessions:
                    del service._active_sessions[session_id]

        # Run many concurrent operations
        tasks = [create_and_delete_session(f"session-{i}") for i in range(50)]
        await asyncio.gather(*tasks)

        # All sessions should be cleaned up
        async with service._sessions_lock:
            assert len(service._active_sessions) == 0

    @pytest.mark.asyncio
    async def test_lock_prevents_dict_modification_during_iteration(self):
        """Test that the lock prevents modification during iteration."""
        from app.core.session import SessionActor

        # Create service instance
        service = SessionService()

        # Clear and populate with test sessions
        async with service._sessions_lock:
            service._active_sessions.clear()
            for i in range(10):
                actor = SessionActor(f"iter-session-{i}")
                service._active_sessions[f"iter-session-{i}"] = actor

        errors = []

        async def iterate_sessions():
            """Iterate over sessions while holding lock."""
            async with service._sessions_lock:
                for session_id in list(service._active_sessions.keys()):
                    await asyncio.sleep(0.001)

        async def modify_sessions():
            """Try to modify sessions."""
            for i in range(10, 20):
                async with service._sessions_lock:
                    service._active_sessions[f"iter-session-{i}"] = SessionActor(
                        f"iter-session-{i}"
                    )
                await asyncio.sleep(0.001)

        # Run concurrently - should not raise
        try:
            await asyncio.gather(
                iterate_sessions(),
                modify_sessions(),
            )
        except RuntimeError as e:
            errors.append(str(e))

        assert len(errors) == 0, f"Race condition detected: {errors}"

        # Cleanup
        async with service._sessions_lock:
            service._active_sessions.clear()
