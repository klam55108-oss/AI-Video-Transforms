"""
API Tests for FastAPI endpoints.

Testing Checklist Items:
- [x] All new endpoints return correct status codes
- [x] File upload accepts only valid video extensions
- [x] Download returns correct file with proper headers
"""

import io
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


class TestStatusEndpoint:
    """Test /status/{session_id} endpoint."""

    @pytest.mark.asyncio
    async def test_status_returns_initializing_for_unknown_session(self):
        """Test that status returns INITIALIZING for unknown session."""
        from web_app import app

        # Use valid UUID v4 format for unknown session
        unknown_session_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/status/{unknown_session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "initializing"
        assert data["session_id"] == unknown_session_id

    @pytest.mark.asyncio
    async def test_status_returns_ready_for_active_session(self):
        """Test that status returns READY for active session."""
        from web_app import app, active_sessions, sessions_lock, SessionActor

        transport = ASGITransport(app=app)

        # Create a mock active session with valid UUID v4
        session_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        actor = SessionActor(session_id)
        actor._running_event.set()
        actor._is_processing = False

        async with sessions_lock:
            active_sessions[session_id] = actor

        try:
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get(f"/status/{session_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
        finally:
            async with sessions_lock:
                if session_id in active_sessions:
                    del active_sessions[session_id]

    @pytest.mark.asyncio
    async def test_status_returns_processing_when_active(self):
        """Test that status returns PROCESSING when session is processing."""
        from web_app import app, active_sessions, sessions_lock, SessionActor

        transport = ASGITransport(app=app)

        session_id = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        actor = SessionActor(session_id)
        actor._running_event.set()
        actor._is_processing = True

        async with sessions_lock:
            active_sessions[session_id] = actor

        try:
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get(f"/status/{session_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "processing"
        finally:
            async with sessions_lock:
                if session_id in active_sessions:
                    del active_sessions[session_id]


class TestHistoryEndpoints:
    """Test /history endpoints."""

    @pytest.mark.asyncio
    async def test_list_history_returns_200(self):
        """Test that list history returns 200."""
        from web_app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/history")

        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_get_history_returns_404_for_unknown_session(self):
        """Test that get history returns 404 for unknown session."""
        from web_app import app

        # Use valid UUID v4 that doesn't exist
        nonexistent_id = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/history/{nonexistent_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_history_returns_success(self):
        """Test that delete history returns success."""
        from web_app import app

        # Use valid UUID v4 format
        session_id = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/history/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data


class TestTranscriptsEndpoints:
    """Test /transcripts endpoints."""

    @pytest.mark.asyncio
    async def test_list_transcripts_returns_200(self):
        """Test that list transcripts returns 200."""
        from web_app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/transcripts")

        assert response.status_code == 200
        data = response.json()
        assert "transcripts" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_download_transcript_returns_404_for_unknown(self):
        """Test that download returns 404 for unknown transcript."""
        from web_app import app

        # Use valid 8-hex-char ID that doesn't exist
        nonexistent_id = "abcd1234"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/transcripts/{nonexistent_id}/download")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_download_transcript_returns_file_with_headers(self):
        """Test that download returns file with correct headers."""
        from web_app import app
        from storage import storage

        # Create a temporary transcript file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Test transcript content")
            transcript_path = f.name

        try:
            # Register the transcript
            entry = storage.register_transcript(
                file_path=transcript_path,
                original_source="test-source",
                source_type="local",
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get(f"/transcripts/{entry['id']}/download")

            assert response.status_code == 200
            assert "content-disposition" in response.headers
            assert response.headers.get("content-type", "").startswith("text/plain")
            assert response.text == "Test transcript content"
        finally:
            Path(transcript_path).unlink(missing_ok=True)
            storage.delete_transcript(entry["id"])

    @pytest.mark.asyncio
    async def test_delete_transcript_returns_success(self):
        """Test that delete transcript returns success."""
        from web_app import app

        # Use valid 8-hex-char ID format
        transcript_id = "ef567890"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/transcripts/{transcript_id}")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data


class TestUploadEndpoint:
    """Test /upload endpoint."""

    @pytest.mark.asyncio
    async def test_upload_rejects_invalid_session_id(self):
        """Test that upload rejects invalid session_id format."""
        from web_app import app

        transport = ASGITransport(app=app)

        files = {"file": ("test.mp4", io.BytesIO(b"fake content"), "video/mp4")}
        data = {"session_id": "invalid-session-id"}

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/upload", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is False
        assert "Invalid session ID format" in result["error"]

    @pytest.mark.asyncio
    async def test_upload_rejects_invalid_extension(self):
        """Test that upload rejects files with invalid extensions."""
        from web_app import app

        transport = ASGITransport(app=app)

        files = {"file": ("test.txt", io.BytesIO(b"fake content"), "text/plain")}
        # Use valid UUID v4 format
        data = {"session_id": "12345678-1234-4123-8123-123456789abc"}

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/upload", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is False
        assert "Invalid file type" in result["error"]

    @pytest.mark.asyncio
    async def test_upload_accepts_valid_video_extension(self, temp_upload_dir: Path):
        """Test that upload accepts valid video extensions."""
        from web_app import app

        # Use valid UUID v4 format
        session_id = "12345678-1234-4123-8123-123456789abc"

        # Patch UPLOAD_DIR to use temp directory
        with patch("web_app.UPLOAD_DIR", temp_upload_dir):
            transport = ASGITransport(app=app)

            files = {
                "file": ("test.mp4", io.BytesIO(b"fake video content"), "video/mp4")
            }
            data = {"session_id": session_id}

            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post("/upload", files=files, data=data)

            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            assert result["file_id"] is not None
            assert result["file_path"] is not None

    @pytest.mark.asyncio
    async def test_upload_accepts_all_allowed_extensions(self, temp_upload_dir: Path):
        """Test that upload accepts all allowed video extensions."""
        from web_app import app, ALLOWED_EXTENSIONS

        # Use valid UUID v4 format (one for all tests)
        session_id = "12345678-1234-4123-8123-123456789abc"

        with patch("web_app.UPLOAD_DIR", temp_upload_dir):
            transport = ASGITransport(app=app)

            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                for ext in ALLOWED_EXTENSIONS:
                    filename = f"test{ext}"
                    files = {"file": (filename, io.BytesIO(b"content"), "video/mp4")}
                    data = {"session_id": session_id}

                    response = await client.post("/upload", files=files, data=data)
                    result = response.json()

                    assert result["success"] is True, (
                        f"Extension {ext} should be accepted"
                    )

    @pytest.mark.asyncio
    async def test_upload_creates_session_directory(self, temp_upload_dir: Path):
        """Test that upload creates a directory for the session."""
        from web_app import app

        # Use valid UUID v4 format
        session_id = "abcdef12-3456-4789-abcd-ef1234567890"

        with patch("web_app.UPLOAD_DIR", temp_upload_dir):
            transport = ASGITransport(app=app)

            files = {"file": ("video.mkv", io.BytesIO(b"content"), "video/x-matroska")}
            data = {"session_id": session_id}

            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post("/upload", files=files, data=data)

            assert response.status_code == 200
            session_dir = temp_upload_dir / session_id
            assert session_dir.exists()


class TestChatEndpoints:
    """Test /chat endpoints."""

    @pytest.mark.asyncio
    async def test_delete_chat_session_invalid_uuid_returns_400(self):
        """Test that DELETE /chat/{session_id} returns 400 for invalid UUID."""
        from web_app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/chat/invalid-session-id")

        assert response.status_code == 400
        data = response.json()
        assert data["detail"] == "Invalid session ID format"

    @pytest.mark.asyncio
    async def test_delete_chat_session_not_found_returns_404(self):
        """Test that DELETE /chat/{session_id} returns 404 for unknown session."""
        from web_app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Use a valid UUID v4 format but for a non-existent session
            response = await client.delete("/chat/550e8400-e29b-41d4-a716-446655440000")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Session not found"


class TestRootEndpoint:
    """Test root endpoint."""

    @pytest.mark.asyncio
    async def test_root_returns_html(self):
        """Test that root returns HTML page."""
        from web_app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


class TestAllowedExtensions:
    """Test ALLOWED_EXTENSIONS configuration."""

    def test_allowed_extensions_includes_common_formats(self):
        """Test that ALLOWED_EXTENSIONS includes common video formats."""
        from web_app import ALLOWED_EXTENSIONS

        expected = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}
        assert ALLOWED_EXTENSIONS == expected

    def test_allowed_extensions_are_lowercase(self):
        """Test that all allowed extensions are lowercase."""
        from web_app import ALLOWED_EXTENSIONS

        for ext in ALLOWED_EXTENSIONS:
            assert ext == ext.lower()
            assert ext.startswith(".")
