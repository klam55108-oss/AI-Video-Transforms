"""
Service Layer Tests.

Tests for the app/services/ module including:
- ServiceContainer lifecycle
- SessionService session management
- StorageService data operations
- TranscriptionService orchestration
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.service import SessionStatus, SourceType


class TestServiceContainer:
    """Tests for ServiceContainer class."""

    @pytest.mark.asyncio
    async def test_container_startup_initializes_services(self):
        """Test that startup initializes all services."""
        from app.services import ServiceContainer

        container = ServiceContainer()

        # Services should be None before startup
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = container.storage

        await container.startup()

        # After startup, services should be available
        assert container.storage is not None
        assert container.session is not None
        assert container.transcription is not None

        await container.shutdown()

    @pytest.mark.asyncio
    async def test_container_shutdown_cleans_up(self):
        """Test that shutdown cleans up resources."""
        from app.services import ServiceContainer

        container = ServiceContainer()
        await container.startup()

        # Add a mock session to track cleanup
        mock_actor = MagicMock()
        mock_actor.is_running = True
        mock_actor.stop = AsyncMock()
        container.session._active_sessions["test-id"] = mock_actor

        await container.shutdown()

        # Cleanup should have stopped all sessions
        mock_actor.stop.assert_called_once()

        # Services should be None after shutdown
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = container.storage

    @pytest.mark.asyncio
    async def test_container_cleanup_task_is_created(self):
        """Test that startup creates cleanup background task."""
        from app.services import ServiceContainer

        container = ServiceContainer()
        await container.startup()

        assert container._cleanup_task is not None
        assert not container._cleanup_task.done()

        await container.shutdown()

    def test_get_services_returns_singleton(self):
        """Test that get_services returns the global container.

        This test relies on the session-scoped conftest fixture that
        initializes services. We don't enter a new services_lifespan
        context because that would set _services = None on exit.
        """
        from app.services import get_services

        services1 = get_services()
        services2 = get_services()
        assert services1 is services2

    @pytest.mark.asyncio
    async def test_get_services_raises_before_init(self):
        """Test that get_services raises if not initialized."""
        from app.services import get_services

        # Temporarily clear global services
        import app.services as services_module

        original = services_module._services
        services_module._services = None

        try:
            with pytest.raises(RuntimeError, match="not initialized"):
                get_services()
        finally:
            services_module._services = original


class TestSessionService:
    """Tests for SessionService class."""

    @pytest.mark.asyncio
    async def test_get_status_returns_closed_for_unknown(self):
        """Test that get_status returns CLOSED for unknown session."""
        from app.services.session_service import SessionService

        service = SessionService()
        status = service.get_status("unknown-session-id")
        assert status == SessionStatus.CLOSED

    @pytest.mark.asyncio
    async def test_get_status_returns_ready_for_active(self):
        """Test that get_status returns READY for active session."""
        from app.services.session_service import SessionService

        service = SessionService()

        # Create mock actor
        mock_actor = MagicMock()
        mock_actor.is_running = True
        mock_actor.is_processing = False
        mock_actor.greeting_queue = MagicMock()
        mock_actor.greeting_queue.empty.return_value = True

        service._active_sessions["test-session"] = mock_actor

        status = service.get_status("test-session")
        assert status == SessionStatus.READY

    @pytest.mark.asyncio
    async def test_get_status_returns_processing_when_active(self):
        """Test that get_status returns PROCESSING when session is processing."""
        from app.services.session_service import SessionService

        service = SessionService()

        mock_actor = MagicMock()
        mock_actor.is_running = True
        mock_actor.is_processing = True

        service._active_sessions["test-session"] = mock_actor

        status = service.get_status("test-session")
        assert status == SessionStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_close_session_removes_and_stops_actor(self):
        """Test that close_session removes session and stops actor."""
        from app.services.session_service import SessionService

        service = SessionService()

        mock_actor = MagicMock()
        mock_actor.stop = AsyncMock()
        service._active_sessions["test-session"] = mock_actor

        result = await service.close_session("test-session")

        assert result is True
        assert "test-session" not in service._active_sessions
        mock_actor.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_session_returns_false_for_unknown(self):
        """Test that close_session returns False for unknown session."""
        from app.services.session_service import SessionService

        service = SessionService()
        result = await service.close_session("unknown-session")
        assert result is False

    @pytest.mark.asyncio
    async def test_close_all_sessions_stops_all_actors(self):
        """Test that close_all_sessions stops all active sessions."""
        from app.services.session_service import SessionService

        service = SessionService()

        mock_actors = []
        for i in range(3):
            actor = MagicMock()
            actor.stop = AsyncMock()
            mock_actors.append(actor)
            service._active_sessions[f"session-{i}"] = actor

        await service.close_all_sessions()

        assert len(service._active_sessions) == 0
        for actor in mock_actors:
            actor.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_active_session_count(self):
        """Test that get_active_session_count returns correct count."""
        from app.services.session_service import SessionService

        service = SessionService()

        assert service.get_active_session_count() == 0

        service._active_sessions["session-1"] = MagicMock()
        service._active_sessions["session-2"] = MagicMock()

        assert service.get_active_session_count() == 2

    @pytest.mark.asyncio
    async def test_get_all_session_ids(self):
        """Test that get_all_session_ids returns all IDs."""
        from app.services.session_service import SessionService

        service = SessionService()

        service._active_sessions["session-a"] = MagicMock()
        service._active_sessions["session-b"] = MagicMock()

        ids = service.get_all_session_ids()
        assert set(ids) == {"session-a", "session-b"}

    @pytest.mark.asyncio
    async def test_get_or_create_raises_without_api_key(self):
        """Test that get_or_create raises when API key missing."""
        from app.models.service import ServiceUnavailableError
        from app.services.session_service import SessionService

        service = SessionService()

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ServiceUnavailableError, match="ANTHROPIC_API_KEY"):
                await service.get_or_create("test-session-id")


class TestStorageService:
    """Tests for StorageService class."""

    def test_list_sessions_returns_list(self):
        """Test that list_sessions returns a list of SessionSummary."""
        from app.services.storage_service import StorageService

        service = StorageService()
        sessions = service.list_sessions(limit=10)

        assert isinstance(sessions, list)
        # All items should be SessionSummary models
        for session in sessions:
            assert hasattr(session, "session_id")
            assert hasattr(session, "title")
            assert hasattr(session, "created_at")

    def test_get_session_returns_none_for_unknown(self):
        """Test that get_session returns None for unknown session."""
        from app.services.storage_service import StorageService

        service = StorageService()
        result = service.get_session("nonexistent-session-id")
        assert result is None

    def test_list_transcripts_returns_list(self):
        """Test that list_transcripts returns a list of TranscriptMetadata."""
        from app.services.storage_service import StorageService

        service = StorageService()
        transcripts = service.list_transcripts()

        assert isinstance(transcripts, list)

    def test_get_transcript_metadata_returns_none_for_unknown(self):
        """Test that get_transcript_metadata returns None for unknown ID."""
        from app.services.storage_service import StorageService

        service = StorageService()
        result = service.get_transcript_metadata("nonexistent-id")
        assert result is None

    def test_get_global_cost_returns_response(self):
        """Test that get_global_cost returns GlobalCostResponse."""
        from app.models.api import GlobalCostResponse
        from app.services.storage_service import StorageService

        service = StorageService()
        result = service.get_global_cost()

        assert isinstance(result, GlobalCostResponse)
        assert hasattr(result, "total_input_tokens")
        assert hasattr(result, "total_cost_usd")
        assert hasattr(result, "session_count")

    def test_get_session_cost_returns_none_for_unknown(self):
        """Test that get_session_cost returns None for unknown session."""
        from app.services.storage_service import StorageService

        service = StorageService()
        result = service.get_session_cost("nonexistent-session")
        assert result is None

    def test_get_transcript_content_returns_none_for_missing_file(self):
        """Test that get_transcript_content returns None for missing file."""
        from app.services.storage_service import StorageService

        service = StorageService()
        result = service.get_transcript_content("/nonexistent/path/file.txt")
        assert result is None

    def test_get_transcript_content_returns_content_for_existing_file(self):
        """Test that get_transcript_content returns content for existing file."""
        from app.services.storage_service import StorageService

        service = StorageService()

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Test content")
            path = f.name

        try:
            result = service.get_transcript_content(path)
            assert result is not None
            assert result.content == "Test content"
        finally:
            Path(path).unlink(missing_ok=True)


class TestTranscriptionService:
    """Tests for TranscriptionService class."""

    @pytest.mark.asyncio
    async def test_save_transcript_raises_for_missing_file(self):
        """Test that save_transcript raises FileNotFoundError for missing file."""
        from app.services.storage_service import StorageService
        from app.services.transcription_service import TranscriptionService

        storage_service = StorageService()
        service = TranscriptionService(storage_service)

        with pytest.raises(FileNotFoundError, match="not found"):
            await service.save_transcript(
                file_path="/nonexistent/file.txt",
                original_source="test",
                source_type=SourceType.LOCAL,
            )

    @pytest.mark.asyncio
    async def test_get_transcript_returns_none_for_unknown(self):
        """Test that get_transcript returns None for unknown ID."""
        from app.services.storage_service import StorageService
        from app.services.transcription_service import TranscriptionService

        storage_service = StorageService()
        service = TranscriptionService(storage_service)

        result = await service.get_transcript("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_transcripts_returns_list(self):
        """Test that list_transcripts returns a list."""
        from app.services.storage_service import StorageService
        from app.services.transcription_service import TranscriptionService

        storage_service = StorageService()
        service = TranscriptionService(storage_service)

        result = await service.list_transcripts()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_delete_transcript_returns_false_for_unknown(self):
        """Test that delete_transcript returns False for unknown ID."""
        from app.services.storage_service import StorageService
        from app.services.transcription_service import TranscriptionService

        storage_service = StorageService()
        service = TranscriptionService(storage_service)

        result = await service.delete_transcript("nonexistent-id")
        assert result is False

    def test_get_transcript_metadata_returns_none_for_unknown(self):
        """Test that get_transcript_metadata returns None for unknown ID."""
        from app.services.storage_service import StorageService
        from app.services.transcription_service import TranscriptionService

        storage_service = StorageService()
        service = TranscriptionService(storage_service)

        result = service.get_transcript_metadata("nonexistent-id")
        assert result is None


class TestServiceModels:
    """Tests for service layer models."""

    def test_source_type_enum_values(self):
        """Test that SourceType has expected values."""
        assert SourceType.YOUTUBE.value == "youtube"
        assert SourceType.UPLOAD.value == "upload"
        assert SourceType.LOCAL.value == "local"

    def test_session_status_enum_values(self):
        """Test that SessionStatus has expected values."""
        assert SessionStatus.INITIALIZING.value == "initializing"
        assert SessionStatus.READY.value == "ready"
        assert SessionStatus.PROCESSING.value == "processing"
        assert SessionStatus.ERROR.value == "error"
        assert SessionStatus.CLOSED.value == "closed"

    def test_transcript_content_model(self):
        """Test TranscriptContent model."""
        from app.models.service import TranscriptContent

        content = TranscriptContent(content="Test transcript")
        assert content.content == "Test transcript"

    def test_global_cost_stats_model_defaults(self):
        """Test GlobalCostStats model has correct defaults."""
        from app.models.service import GlobalCostStats

        stats = GlobalCostStats()
        assert stats.total_input_tokens == 0
        assert stats.total_output_tokens == 0
        assert stats.total_cost_usd == 0.0
        assert stats.session_count == 0

    def test_service_unavailable_error(self):
        """Test ServiceUnavailableError exception."""
        from app.models.service import ServiceUnavailableError

        error = ServiceUnavailableError("Test message")
        assert str(error) == "Test message"
        assert error.message == "Test message"


class TestServicesLifespan:
    """Tests for services_lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_initializes_and_cleans_up(self):
        """Test that lifespan properly initializes and cleans up.

        This test verifies the services_lifespan context manager behavior.
        We save and restore the original _services to avoid breaking
        subsequent tests that depend on the conftest-initialized services.
        """
        import app.services as services_module

        from app.services import get_services, services_lifespan

        # Save original services set by conftest
        original_services = services_module._services

        mock_app = MagicMock()

        try:
            async with services_lifespan(mock_app):
                # Services should be available during lifespan
                services = get_services()
                assert services.storage is not None
                assert services.session is not None
                assert services.transcription is not None

            # After exiting, global services should be cleared
            assert services_module._services is None
        finally:
            # Restore original services for subsequent tests
            services_module._services = original_services
