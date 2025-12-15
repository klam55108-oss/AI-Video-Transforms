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


# =============================================================================
# Knowledge Graph Fixtures
# =============================================================================


@pytest.fixture
def kg_service(tmp_path: Path):
    """Create a KnowledgeGraphService with isolated tmp_path directory.

    This fixture provides a fresh KG service for each test with an isolated
    storage directory that is automatically cleaned up after the test.
    """
    from app.services.kg_service import KnowledgeGraphService

    return KnowledgeGraphService(data_path=tmp_path)


@pytest.fixture
def sample_domain_profile():
    """Create a standard DomainProfile for testing.

    Provides a realistic domain profile with entity types (Person, Organization,
    Program, Location), connection types, and seed entities suitable for
    MK-Ultra style documentary content testing.
    """
    from app.kg.domain import (
        ConnectionType,
        DomainProfile,
        SeedEntity,
        ThingType,
    )

    return DomainProfile(
        name="CIA Mind Control Programs",
        description="Domain covering CIA psychological research programs and key personnel",
        thing_types=[
            ThingType(
                name="Person",
                description="Individuals involved in the programs",
                examples=["Sidney Gottlieb", "Allen Dulles"],
                priority=1,
            ),
            ThingType(
                name="Organization",
                description="Government agencies and institutions",
                examples=["CIA", "US Army"],
                priority=1,
            ),
            ThingType(
                name="Program",
                description="Covert operations and research projects",
                examples=["MK-Ultra", "Operation Midnight Climax"],
                priority=1,
            ),
            ThingType(
                name="Location",
                description="Places where operations occurred",
                examples=["San Francisco", "Fort Detrick"],
                priority=2,
            ),
        ],
        connection_types=[
            ConnectionType(
                name="directed",
                display_name="directed",
                description="Person directed a program or operation",
                examples=[("Sidney Gottlieb", "MK-Ultra")],
            ),
            ConnectionType(
                name="reported_to",
                display_name="reported to",
                description="Reporting relationship between people",
                examples=[("Sidney Gottlieb", "Allen Dulles")],
            ),
            ConnectionType(
                name="funded_by",
                display_name="funded by",
                description="Financial support relationship",
                examples=[("MK-Ultra", "CIA")],
            ),
            ConnectionType(
                name="located_in",
                display_name="located in",
                description="Geographic location of operations",
                examples=[("Operation Midnight Climax", "San Francisco")],
            ),
        ],
        seed_entities=[
            SeedEntity(
                label="Sidney Gottlieb",
                thing_type="Person",
                aliases=["Dr. Gottlieb", "Joseph Scheider"],
            ),
            SeedEntity(
                label="CIA",
                thing_type="Organization",
                aliases=["Central Intelligence Agency"],
            ),
            SeedEntity(
                label="MK-Ultra",
                thing_type="Program",
                aliases=["Project MK-Ultra", "MKULTRA"],
            ),
        ],
        extraction_context="Focus on CIA personnel, programs, and their relationships.",
        bootstrap_confidence=0.9,
        bootstrapped_from="ep1_source",
    )


@pytest.fixture
def sample_transcript() -> str:
    """Realistic transcript content for KG testing.

    Contains content about CIA programs, personnel, and relationships
    suitable for bootstrap and extraction testing.
    """
    return """
    In this documentary, we explore the history of MK-Ultra, one of the CIA's
    most controversial programs. Dr. Sidney Gottlieb, who headed the program,
    reported directly to Allen Dulles, the Director of Central Intelligence.

    The program operated from 1953 to 1973 and involved numerous subprojects
    focused on mind control research. Operation Midnight Climax was one such
    subproject, run by George White in San Francisco.

    Key documents reveal the involvement of multiple institutions, including
    universities and hospitals, often without the subjects' knowledge or consent.
    """
