"""
Integration Tests for Chat Endpoints.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch
from app.core.session import MessageResponse, MessageUsage


class MockActor:
    def __init__(self, session_id):
        self.session_id = session_id
        self.is_running = True
        self.is_processing = False

    async def get_greeting(self):
        return MessageResponse(
            text="Hello! I am your video agent.",
            usage=MessageUsage(
                input_tokens=10,
                output_tokens=20,
                cache_creation_tokens=0,
                cache_read_tokens=0,
            ),
        )

    async def process_message(self, message):
        return MessageResponse(
            text=f"I received: {message}",
            usage=MessageUsage(
                input_tokens=15,
                output_tokens=25,
                cache_creation_tokens=5,
                cache_read_tokens=5,
            ),
        )

    async def stop(self):
        pass


@pytest.mark.asyncio
async def test_chat_init_success():
    """Test successful session initialization."""
    from app.main import app

    session_id = "12345678-1234-4123-8123-123456789abc"

    # Mock get_or_create_session to return our MockActor
    with patch(
        "app.main.get_or_create_session",
        new=AsyncMock(return_value=MockActor(session_id)),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/chat/init", json={"session_id": session_id})

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["response"] == "Hello! I am your video agent."
    assert data["usage"]["input_tokens"] == 10


@pytest.mark.asyncio
async def test_chat_message_success():
    """Test sending a message and receiving a response."""
    from app.main import app

    session_id = "12345678-1234-4123-8123-123456789abc"
    message = "Hello, world!"

    with patch(
        "app.main.get_or_create_session",
        new=AsyncMock(return_value=MockActor(session_id)),
    ):
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
