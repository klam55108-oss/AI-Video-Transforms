"""
Integration Tests for Chat Endpoints.

Tests the full API flow with mocked session services.
Uses FastAPI's dependency_overrides for proper dependency injection testing.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import MagicMock
from app.core.session import MessageResponse, MessageUsage


class MockActor:
    """Mock SessionActor for testing."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.is_running = True
        self.is_processing = False
        self.greeting_queue = MagicMock()
        self.greeting_queue.empty.return_value = True

    async def get_greeting(self) -> MessageResponse:
        return MessageResponse(
            text="Hello! I am your video agent.",
            usage=MessageUsage(
                input_tokens=10,
                output_tokens=20,
                cache_creation_tokens=0,
                cache_read_tokens=0,
            ),
        )

    async def process_message(self, message: str) -> MessageResponse:
        return MessageResponse(
            text=f"I received: {message}",
            usage=MessageUsage(
                input_tokens=15,
                output_tokens=25,
                cache_creation_tokens=5,
                cache_read_tokens=5,
            ),
        )

    async def stop(self) -> None:
        pass


class MockSessionService:
    """Mock SessionService that returns a MockActor."""

    def __init__(self, mock_actor: MockActor) -> None:
        self._mock_actor = mock_actor

    async def get_or_create(self, session_id: str) -> MockActor:
        return self._mock_actor


@pytest.mark.asyncio
async def test_chat_init_success():
    """Test successful session initialization."""
    from app.api.deps import get_session_service
    from app.main import app

    session_id = "12345678-1234-4123-8123-123456789abc"
    mock_actor = MockActor(session_id)
    mock_service = MockSessionService(mock_actor)

    # Use FastAPI's dependency_overrides for proper mocking
    app.dependency_overrides[get_session_service] = lambda: mock_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/chat/init", json={"session_id": session_id})

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["response"] == "Hello! I am your video agent."
        assert data["usage"]["input_tokens"] == 10
    finally:
        # Clean up the override
        app.dependency_overrides.pop(get_session_service, None)


@pytest.mark.asyncio
async def test_chat_message_success():
    """Test sending a message and receiving a response."""
    from app.api.deps import get_session_service
    from app.main import app

    session_id = "12345678-1234-4123-8123-123456789abc"
    message = "Hello, world!"
    mock_actor = MockActor(session_id)
    mock_service = MockSessionService(mock_actor)

    app.dependency_overrides[get_session_service] = lambda: mock_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/chat", json={"session_id": session_id, "message": message}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["response"] == f"I received: {message}"
        assert data["usage"]["input_tokens"] == 15
    finally:
        app.dependency_overrides.pop(get_session_service, None)


@pytest.mark.asyncio
async def test_chat_invalid_session_id():
    """Test that invalid session IDs are rejected."""
    from app.main import app

    session_id = "invalid-id"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/chat", json={"session_id": session_id, "message": "hi"}
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_empty_message():
    """Test that empty messages are rejected."""
    from app.main import app

    session_id = "12345678-1234-4123-8123-123456789abc"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/chat", json={"session_id": session_id, "message": "   "}
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_init_returns_usage_stats():
    """Test that chat/init returns complete usage statistics."""
    from app.api.deps import get_session_service
    from app.main import app

    session_id = "12345678-1234-4123-8123-123456789abc"
    mock_actor = MockActor(session_id)
    mock_service = MockSessionService(mock_actor)

    app.dependency_overrides[get_session_service] = lambda: mock_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/chat/init", json={"session_id": session_id})

        data = response.json()
        assert "usage" in data
        assert "input_tokens" in data["usage"]
        assert "output_tokens" in data["usage"]
        assert "cache_creation_tokens" in data["usage"]
        assert "cache_read_tokens" in data["usage"]
        assert "total_cost_usd" in data["usage"]
    finally:
        app.dependency_overrides.pop(get_session_service, None)


@pytest.mark.asyncio
async def test_chat_message_returns_usage_stats():
    """Test that chat message returns complete usage statistics."""
    from app.api.deps import get_session_service
    from app.main import app

    session_id = "12345678-1234-4123-8123-123456789abc"
    mock_actor = MockActor(session_id)
    mock_service = MockSessionService(mock_actor)

    app.dependency_overrides[get_session_service] = lambda: mock_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/chat", json={"session_id": session_id, "message": "Test"}
            )

        data = response.json()
        assert "usage" in data
        assert data["usage"]["cache_creation_tokens"] == 5
        assert data["usage"]["cache_read_tokens"] == 5
    finally:
        app.dependency_overrides.pop(get_session_service, None)


@pytest.mark.asyncio
async def test_chat_long_message_accepted():
    """Test that reasonably long messages are accepted."""
    from app.api.deps import get_session_service
    from app.main import app

    session_id = "12345678-1234-4123-8123-123456789abc"
    long_message = "A" * 10000  # 10k characters
    mock_actor = MockActor(session_id)
    mock_service = MockSessionService(mock_actor)

    app.dependency_overrides[get_session_service] = lambda: mock_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/chat", json={"session_id": session_id, "message": long_message}
            )

        assert response.status_code == 200
    finally:
        app.dependency_overrides.pop(get_session_service, None)
