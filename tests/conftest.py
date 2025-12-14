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


# =============================================================================
# FFmpeg and Transcription Tool Fixtures
# =============================================================================


@pytest.fixture
def mock_ffmpeg_success() -> Generator[MagicMock, None, None]:
    """Mock successful FFmpeg execution and availability check."""
    from unittest.mock import Mock, patch

    mock_result = Mock(returncode=0, stderr=b"", stdout=b"")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            yield mock_run


@pytest.fixture
def mock_ffmpeg_not_installed() -> Generator[None, None, None]:
    """Mock FFmpeg not being installed."""
    from unittest.mock import patch

    with patch("shutil.which", return_value=None):
        yield


@pytest.fixture
def mock_openai_transcription() -> Generator[MagicMock, None, None]:
    """Mock OpenAI transcription API for testing."""
    from unittest.mock import MagicMock, patch

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = MagicMock(
        text="This is a test transcription from the mock."
    )
    with patch("app.agent.transcribe_tool.OpenAI", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_audio_segment() -> Generator[MagicMock, None, None]:
    """Mock pydub AudioSegment for testing without real audio files."""
    from unittest.mock import MagicMock, patch

    mock_segment = MagicMock()
    mock_segment.__len__ = lambda self: 300000  # 5 minutes in ms
    mock_segment.__getitem__ = lambda self, key: mock_segment

    with patch(
        "app.agent.transcribe_tool.AudioSegment.from_mp3", return_value=mock_segment
    ):
        yield mock_segment


@pytest.fixture
def temp_audio_file(temp_storage_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary fake audio file for testing."""
    audio_file = temp_storage_dir / "test_audio.mp3"
    audio_file.write_bytes(b"fake mp3 audio content")
    yield audio_file
