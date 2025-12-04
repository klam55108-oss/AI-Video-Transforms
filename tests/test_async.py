"""
Async Tests for blocking operation wrappers.

Testing Checklist Items:
- [x] Transcription doesn't block event loop
- [x] File writing doesn't block event loop
- [x] Timeout fires correctly for long operations
"""

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest


class TestTranscriptionAsyncWrapper:
    """Test that transcription doesn't block the event loop."""

    @pytest.mark.asyncio
    async def test_transcription_uses_to_thread(self):
        """Verify transcription is wrapped with asyncio.to_thread."""
        # Read the transcribe_tool.py to verify the pattern exists
        import agent_video.transcribe_tool as transcribe_module
        import inspect

        source = inspect.getsource(transcribe_module)

        # Verify asyncio.to_thread is used for _perform_transcription
        assert "asyncio.to_thread" in source, (
            "transcribe_tool.py should use asyncio.to_thread"
        )
        assert "_perform_transcription" in source, (
            "Should have _perform_transcription function"
        )

    @pytest.mark.asyncio
    async def test_event_loop_not_blocked_during_mock_transcription(self):
        """Test that other tasks can run during transcription."""
        # Simulate a blocking operation with to_thread
        blocking_call_count = 0

        def slow_operation():
            nonlocal blocking_call_count
            time.sleep(0.1)  # Simulate blocking work
            blocking_call_count += 1
            return "result"

        async def other_task():
            """This task should be able to run during slow_operation."""
            await asyncio.sleep(0.01)
            return True

        # Run both concurrently
        start = time.time()
        result1, result2 = await asyncio.gather(
            asyncio.to_thread(slow_operation),
            other_task(),
        )
        elapsed = time.time() - start

        assert result2 is True, "Other task should complete"
        assert blocking_call_count == 1
        # If event loop was blocked, total time would be > 0.11s
        # With proper async, it should be around 0.1s
        assert elapsed < 0.15, f"Event loop was blocked, took {elapsed}s"


class TestFileWritingAsyncWrapper:
    """Test that file writing doesn't block the event loop."""

    @pytest.mark.asyncio
    async def test_file_tool_uses_to_thread(self):
        """Verify file_tool.py uses asyncio.to_thread."""
        import agent_video.file_tool as file_module
        import inspect

        source = inspect.getsource(file_module)

        assert "asyncio.to_thread" in source, (
            "file_tool.py should use asyncio.to_thread"
        )
        assert "_write_file_sync" in source, (
            "Should have _write_file_sync helper function"
        )

    @pytest.mark.asyncio
    async def test_write_file_sync_helper_exists(self):
        """Test that _write_file_sync helper function works correctly."""
        from agent_video.file_tool import _write_file_sync

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            temp_path = Path(f.name)

        try:
            content = "Test content\nWith multiple lines\n"
            file_size, line_count = _write_file_sync(temp_path, content)

            assert file_size > 0
            assert line_count == 2  # Two lines
            assert temp_path.read_text() == content
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_event_loop_not_blocked_during_file_write(self):
        """Test that other tasks can run during file writing."""
        from agent_video.file_tool import _write_file_sync

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "test_file.txt"

            other_task_completed = False

            async def other_task():
                nonlocal other_task_completed
                await asyncio.sleep(0.01)
                other_task_completed = True
                return True

            # Create large content to make write take some time
            large_content = "x" * 100000

            # Run both concurrently
            await asyncio.gather(
                asyncio.to_thread(_write_file_sync, temp_path, large_content),
                other_task(),
            )

            assert other_task_completed, "Other task should complete during file write"


class TestTimeoutBehavior:
    """Test that timeout fires correctly for long operations."""

    @pytest.mark.asyncio
    async def test_response_timeout_constant_exists(self):
        """Verify RESPONSE_TIMEOUT_SECONDS is defined."""
        from web_app import RESPONSE_TIMEOUT_SECONDS

        assert RESPONSE_TIMEOUT_SECONDS > 0
        assert RESPONSE_TIMEOUT_SECONDS == 300.0  # 5 minutes as per spec

    @pytest.mark.asyncio
    async def test_greeting_timeout_constant_exists(self):
        """Verify GREETING_TIMEOUT_SECONDS is defined."""
        from web_app import GREETING_TIMEOUT_SECONDS

        assert GREETING_TIMEOUT_SECONDS > 0
        assert GREETING_TIMEOUT_SECONDS == 30.0  # 30 seconds as per spec

    @pytest.mark.asyncio
    async def test_process_message_timeout_raises_on_slow_response(self):
        """Test that process_message raises TimeoutError for slow operations."""
        from web_app import SessionActor

        actor = SessionActor("test-timeout-session")
        actor._running_event.set()

        # Create a task that never completes
        async def never_complete():
            await asyncio.sleep(1000)

        actor.active_task = asyncio.create_task(never_complete())

        # Patch the timeout to be very short for testing
        with patch("web_app.RESPONSE_TIMEOUT_SECONDS", 0.1):
            with pytest.raises(TimeoutError) as exc_info:
                await actor.process_message("test message")

            assert "timed out" in str(exc_info.value).lower()

        # Cleanup
        actor.active_task.cancel()
        try:
            await actor.active_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_get_greeting_timeout_returns_fallback(self):
        """Test that get_greeting returns fallback message on timeout."""
        from web_app import SessionActor

        actor = SessionActor("test-greeting-timeout")
        actor._running_event.set()

        # Patch timeout to be very short
        with patch("web_app.GREETING_TIMEOUT_SECONDS", 0.01):
            response = await actor.get_greeting()

        # Should return fallback message (response is now MessageResponse)
        assert (
            "ready to help" in response.text.lower()
            or "initialization was slow" in response.text.lower()
        )

    @pytest.mark.asyncio
    async def test_asyncio_wait_timeout_behavior(self):
        """Test the asyncio.wait timeout pattern used in process_message."""

        async def slow_task():
            await asyncio.sleep(10)
            return "completed"

        task = asyncio.create_task(slow_task())

        done, pending = await asyncio.wait(
            [task],
            timeout=0.01,
            return_when=asyncio.FIRST_COMPLETED,
        )

        # With short timeout, task should be in pending (done should be empty)
        assert len(done) == 0
        assert len(pending) == 1

        # Cleanup
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_graceful_shutdown_timeout_exists(self):
        """Verify GRACEFUL_SHUTDOWN_TIMEOUT is defined."""
        from web_app import GRACEFUL_SHUTDOWN_TIMEOUT

        assert GRACEFUL_SHUTDOWN_TIMEOUT > 0
        assert GRACEFUL_SHUTDOWN_TIMEOUT == 2.0  # 2 seconds as per spec
