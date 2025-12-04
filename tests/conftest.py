"""
Pytest configuration and fixtures for backend tests.
"""

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Configure pytest-asyncio to use function-scoped event loops
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use the default event loop policy."""
    return asyncio.DefaultEventLoopPolicy()


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
