"""
Pytest configuration and fixtures for backend tests.
"""

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Configure pytest-asyncio to use function-scoped event loops
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session", autouse=True)
def initialize_services():
    """Initialize services for all tests.

    This fixture uses the services_lifespan context manager to ensure
    all services (storage, session, transcription) are properly initialized
    before any tests run, and cleaned up after all tests complete.

    We use a sync fixture that creates its own event loop to avoid
    pytest-asyncio scope mismatch issues.
    """
    from app.services import services_lifespan

    mock_app = MagicMock()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Enter the async context manager synchronously
    cm = services_lifespan(mock_app)
    loop.run_until_complete(cm.__aenter__())

    yield

    # Exit the async context manager
    loop.run_until_complete(cm.__aexit__(None, None, None))
    loop.close()


@pytest.fixture
def temp_storage_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for storage tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_storage_"))
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_upload_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for upload tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_uploads_"))
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing FastAPI endpoints."""
    # Import here to avoid circular imports and allow patching
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_video_content() -> bytes:
    """Create minimal video-like content for upload tests."""
    # This is not a real video, just bytes to test file handling
    return b"fake video content for testing purposes"


@pytest.fixture
def sample_transcript_content() -> str:
    """Sample transcript content for storage tests."""
    return """[00:00:00] Hello and welcome to this video.
[00:00:05] Today we'll be discussing testing strategies.
[00:00:10] Let's get started with the basics.
"""
