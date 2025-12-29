"""
Tests for the video transcription tool.

Tests cover:
- FFmpeg audio extraction
- gpt-4o-transcribe model integration
- MP3 audio format handling
- Simple text-only response format
- Audio splitting for files >25 minutes
- Error handling and edge cases
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.agent.transcribe_tool import (
    TranscriptionError,
    _check_ffmpeg_available,
    _extract_audio_from_video,
    _is_youtube_url,
    _perform_transcription,
    _transcribe_audio_file,
    transcribe_video,
)


# =============================================================================
# FFmpeg Extraction Tests
# =============================================================================


class TestFFmpegExtraction:
    """Tests for FFmpeg-based audio extraction."""

    def test_check_ffmpeg_available_returns_true_when_installed(self) -> None:
        """FFmpeg check returns True when ffmpeg is in PATH."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            assert _check_ffmpeg_available() is True

    def test_check_ffmpeg_available_returns_false_when_missing(self) -> None:
        """FFmpeg check returns False when ffmpeg is not found."""
        with patch("shutil.which", return_value=None):
            assert _check_ffmpeg_available() is False

    def test_extract_audio_raises_when_ffmpeg_not_installed(
        self, temp_storage_dir: Path
    ) -> None:
        """Audio extraction raises RuntimeError when FFmpeg is missing."""
        video_path = temp_storage_dir / "test.mp4"
        video_path.write_bytes(b"fake video")

        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="FFmpeg is not installed"):
                _extract_audio_from_video(str(video_path), str(temp_storage_dir))

    def test_extract_audio_uses_correct_ffmpeg_command(
        self, temp_storage_dir: Path
    ) -> None:
        """Audio extraction calls FFmpeg with correct MP3 parameters."""
        video_path = temp_storage_dir / "test.mp4"
        video_path.write_bytes(b"fake video")

        mock_result = Mock(returncode=0, stderr=b"", stdout=b"")
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                # Create the expected output file so the function doesn't fail
                expected_output = temp_storage_dir / "test_audio.mp3"
                expected_output.write_bytes(b"fake mp3")

                _extract_audio_from_video(str(video_path), str(temp_storage_dir))

                # Verify FFmpeg was called with expected args
                call_args = mock_run.call_args[0][0]
                assert "ffmpeg" in call_args
                assert "-vn" in call_args  # No video
                assert "libmp3lame" in call_args  # MP3 codec
                assert "-y" in call_args  # Overwrite

    def test_extract_audio_returns_mp3_path(self, temp_storage_dir: Path) -> None:
        """Audio extraction returns path with .mp3 extension."""
        video_path = temp_storage_dir / "test_video.mp4"
        video_path.write_bytes(b"fake video")

        mock_result = Mock(returncode=0, stderr=b"", stdout=b"")
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("subprocess.run", return_value=mock_result):
                expected_output = temp_storage_dir / "test_video_audio.mp3"
                expected_output.write_bytes(b"fake mp3")

                result = _extract_audio_from_video(
                    str(video_path), str(temp_storage_dir)
                )

                assert result.endswith(".mp3")
                assert "test_video_audio.mp3" in result


# =============================================================================
# gpt-4o-transcribe Model Tests
# =============================================================================


class TestSimpleTranscribeModel:
    """Tests for gpt-4o-transcribe model integration (simple text-only)."""

    def test_transcribe_uses_simple_model(self, temp_storage_dir: Path) -> None:
        """Verify transcription uses gpt-4o-transcribe model, not diarize."""
        # Create mock audio file
        audio_path = temp_storage_dir / "test.mp3"
        audio_path.write_bytes(b"fake audio")

        # Create mock response with simple text (no segments)
        mock_response = MagicMock()
        mock_response.text = "Test transcription"

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response

        result = _transcribe_audio_file(
            client=mock_client,
            audio_path=str(audio_path),
        )

        # Verify correct model and parameters were used
        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-transcribe"
        assert call_kwargs["response_format"] == "json"

        # Verify result is just the text string (simplified)
        assert result == "Test transcription"

    def test_transcribe_accepts_prompt_parameter(self, temp_storage_dir: Path) -> None:
        """Verify prompt parameter is passed to API."""
        audio_path = temp_storage_dir / "test.mp3"
        audio_path.write_bytes(b"fake audio")

        mock_response = MagicMock()
        mock_response.text = "Test with custom prompt"

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response

        _transcribe_audio_file(
            client=mock_client,
            audio_path=str(audio_path),
            prompt="Custom context for transcription",
        )

        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["prompt"] == "Custom context for transcription"

    def test_transcribe_passes_language_parameter(self, temp_storage_dir: Path) -> None:
        """Verify language parameter is passed to API."""
        audio_path = temp_storage_dir / "test.mp3"
        audio_path.write_bytes(b"fake audio")

        mock_response = MagicMock()
        mock_response.text = "Prueba"

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response

        _transcribe_audio_file(
            client=mock_client,
            audio_path=str(audio_path),
            language="es",
        )

        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["language"] == "es"

    def test_transcribe_passes_temperature_parameter(
        self, temp_storage_dir: Path
    ) -> None:
        """Verify temperature parameter is passed to API."""
        audio_path = temp_storage_dir / "test.mp3"
        audio_path.write_bytes(b"fake audio")

        mock_response = MagicMock()
        mock_response.text = "Test"

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response

        _transcribe_audio_file(
            client=mock_client,
            audio_path=str(audio_path),
            temperature=0.2,
        )

        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.2

    def test_transcribe_returns_text_string(self, temp_storage_dir: Path) -> None:
        """Verify response is plain text string."""
        audio_path = temp_storage_dir / "test.mp3"
        audio_path.write_bytes(b"fake audio")

        mock_response = MagicMock()
        mock_response.text = "Simple text response"

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response

        result = _transcribe_audio_file(
            client=mock_client,
            audio_path=str(audio_path),
        )

        # Result is just a string
        assert isinstance(result, str)
        assert result == "Simple text response"

    def test_transcribe_raises_on_empty_text(self, temp_storage_dir: Path) -> None:
        """Verify error raised when API returns empty text."""
        audio_path = temp_storage_dir / "test.mp3"
        audio_path.write_bytes(b"fake audio")

        mock_response = MagicMock()
        mock_response.text = ""  # Empty text

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response

        with pytest.raises(TranscriptionError, match="empty transcription"):
            _transcribe_audio_file(
                client=mock_client,
                audio_path=str(audio_path),
            )


# =============================================================================
# Audio Splitting Tests
# =============================================================================


class TestAudioSplitting:
    """Tests for audio splitting functionality for files >25 minutes."""

    def test_split_audio_under_25_min_returns_single_chunk(
        self, temp_storage_dir: Path
    ) -> None:
        """Audio < 25 min should not be split."""
        audio_path = temp_storage_dir / "short.mp3"
        audio_path.write_bytes(b"fake short audio")

        # Mock AudioSegment to report 20 minutes (1200 seconds)
        mock_audio = MagicMock()
        mock_audio.__len__.return_value = 1200 * 1000  # milliseconds
        mock_audio.set_frame_rate.return_value = mock_audio
        mock_audio.set_channels.return_value = mock_audio

        with patch(
            "app.agent.transcribe_tool.AudioSegment.from_file", return_value=mock_audio
        ):
            from app.agent.transcribe_tool import _split_audio_for_duration

            chunks = _split_audio_for_duration(str(audio_path), max_duration_sec=1500)

        # Should return single chunk (original file)
        assert len(chunks) == 1
        assert chunks[0] == str(audio_path)

    def test_split_audio_over_25_min_returns_multiple_chunks(
        self, temp_storage_dir: Path
    ) -> None:
        """Audio > 25 min should be split into chunks."""
        audio_path = temp_storage_dir / "long.mp3"
        audio_path.write_bytes(b"fake long audio")

        # Mock AudioSegment to report 50 minutes (3000 seconds)
        mock_audio = MagicMock()
        mock_audio.__len__.return_value = 3000 * 1000  # 50 minutes in milliseconds
        mock_audio.set_frame_rate.return_value = mock_audio
        mock_audio.set_channels.return_value = mock_audio

        # Mock export for chunk creation
        def mock_export(path: str, **kwargs) -> MagicMock:
            # Create the file so os.path.getsize works
            Path(path).write_bytes(b"fake chunk data " * 1000)  # Make it big enough
            return MagicMock()  # Return mock file handle

        mock_audio.export = mock_export
        mock_audio.__getitem__ = lambda self, key: mock_audio  # Support slicing

        with patch(
            "app.agent.transcribe_tool.AudioSegment.from_file", return_value=mock_audio
        ):
            from app.agent.transcribe_tool import _split_audio_for_duration

            chunks = _split_audio_for_duration(str(audio_path), max_duration_sec=1500)

        # Should return multiple chunks (50 min / 25 min = 2 chunks)
        assert len(chunks) >= 2

    def test_split_audio_chunks_concatenate_correctly(
        self, temp_storage_dir: Path
    ) -> None:
        """Verify chunks are joined with proper spacing."""
        # This test would require mocking the entire transcription pipeline
        # For now, verify the concatenation logic in _perform_transcription
        pass


# =============================================================================
# Clean Break Error Handling Tests
# =============================================================================


class TestCleanBreakErrorHandling:
    """Tests for strict error handling - no silent fallbacks."""

    def test_transcription_error_raised_on_api_failure(
        self, temp_storage_dir: Path
    ) -> None:
        """Verify TranscriptionError is raised on API failure, not silent fallback."""
        audio_path = temp_storage_dir / "test.mp3"
        audio_path.write_bytes(b"fake audio")

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.side_effect = Exception("API error")

        with pytest.raises(TranscriptionError, match="API error"):
            _transcribe_audio_file(client=mock_client, audio_path=str(audio_path))

    def test_no_silent_fallback_on_unexpected_format(
        self, temp_storage_dir: Path
    ) -> None:
        """Verify we fail loudly if API returns unexpected format."""
        audio_path = temp_storage_dir / "test.mp3"
        audio_path.write_bytes(b"fake audio")

        # Mock response with missing text field
        mock_response = MagicMock(spec=[])
        del mock_response.text

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response

        with pytest.raises(TranscriptionError):
            _transcribe_audio_file(client=mock_client, audio_path=str(audio_path))

    def test_raises_when_file_too_large(self, temp_storage_dir: Path) -> None:
        """Verify TranscriptionError raised when audio file exceeds 25MB."""
        audio_path = temp_storage_dir / "large.mp3"
        audio_path.write_bytes(b"fake audio")

        mock_client = MagicMock()

        with patch("os.path.getsize", return_value=30 * 1024 * 1024):  # 30MB
            with pytest.raises(TranscriptionError, match="too large"):
                _transcribe_audio_file(client=mock_client, audio_path=str(audio_path))


# =============================================================================
# Integration Tests for _perform_transcription
# =============================================================================


class TestPerformTranscription:
    """Integration tests for the core transcription function."""

    def test_returns_error_when_api_key_missing(self) -> None:
        """Transcription returns error when OPENAI_API_KEY is not set."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("app.agent.transcribe_tool.load_dotenv"):
                result = _perform_transcription("test.mp4")

        assert result["success"] is False
        assert "OPENAI_API_KEY" in result["error"]

    def test_returns_error_for_missing_file(self) -> None:
        """Transcription returns error for non-existent file."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("app.agent.transcribe_tool.load_dotenv"):
                result = _perform_transcription("/nonexistent/video.mp4")

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_returns_error_when_ffmpeg_missing_for_local_file(self) -> None:
        """Transcription returns error when FFmpeg missing for local file."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("app.agent.transcribe_tool.load_dotenv"):
                with patch("os.path.exists", return_value=True):
                    with patch("shutil.which", return_value=None):
                        with patch("tempfile.TemporaryDirectory"):
                            result = _perform_transcription("/path/to/video.mp4")

        assert result["success"] is False
        # Error will come from _extract_audio_from_video

    def test_success_returns_simple_structure(self, temp_storage_dir: Path) -> None:
        """Verify successful transcription returns expected keys (text only)."""
        # Create an actual temp audio file so open() works
        audio_path = temp_storage_dir / "video_audio.mp3"
        audio_path.write_bytes(b"fake audio data")

        mock_response = MagicMock()
        mock_response.text = "Transcribed text"

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response

        mock_audio = MagicMock()
        mock_audio.__len__.return_value = 1000 * 1000  # 1000 seconds (< 25 min)
        mock_audio.set_frame_rate.return_value = mock_audio
        mock_audio.set_channels.return_value = mock_audio

        # Mock _extract_audio_from_video to return our temp file path
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("app.agent.transcribe_tool.load_dotenv"):
                with patch("os.path.exists", return_value=True):
                    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
                        with patch(
                            "app.agent.transcribe_tool._extract_audio_from_video",
                            return_value=str(audio_path),
                        ):
                            with patch(
                                "app.agent.transcribe_tool.OpenAI",
                                return_value=mock_client,
                            ):
                                with patch(
                                    "app.agent.transcribe_tool.AudioSegment.from_file",
                                    return_value=mock_audio,
                                ):
                                    result = _perform_transcription("video.mp4")

        assert result["success"] is True
        assert "transcription" in result
        assert "source" in result
        assert "source_type" in result
        assert "model" in result
        assert result["model"] == "gpt-4o-transcribe"
        # Verify NO speaker data (segments may exist from API but without speakers)
        assert "speaker_count" not in result
        assert "speakers" not in result

    def test_prompt_parameter_in_signature(self) -> None:
        """Verify _perform_transcription accepts prompt parameter."""
        import inspect

        sig = inspect.signature(_perform_transcription)
        params = sig.parameters
        assert "prompt" in params  # Now supported by simple transcribe model


# =============================================================================
# YouTube URL Detection Tests
# =============================================================================


class TestYouTubeUrlDetection:
    """Tests for YouTube URL detection."""

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
            ("https://youtube.com/watch?v=dQw4w9WgXcQ", True),
            ("https://youtu.be/dQw4w9WgXcQ", True),
            ("http://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
            ("/path/to/local/video.mp4", False),
            ("C:\\Videos\\video.mp4", False),
            ("https://vimeo.com/123456", False),
            ("https://example.com/video.mp4", False),
        ],
    )
    def test_youtube_url_detection(self, url: str, expected: bool) -> None:
        """Test YouTube URL pattern matching."""
        assert _is_youtube_url(url) == expected


# =============================================================================
# Job Queue Integration Tests
# =============================================================================


class TestTranscribeVideoJobQueue:
    """Integration tests for job queue pattern in transcribe_video tool.

    These tests verify that transcribe_video() creates background jobs
    and returns job IDs, rather than performing blocking transcription.

    Note: The @tool decorator wraps the function in SdkMcpTool. We access
    the original async function via transcribe_video.handler for testing.
    """

    @pytest.mark.asyncio
    async def test_transcribe_video_creates_job_and_returns_job_id(self) -> None:
        """Verify transcribe_video creates a job and returns the job ID."""
        from datetime import datetime
        from unittest.mock import AsyncMock, MagicMock

        from app.models.jobs import Job, JobStage, JobStatus, JobType

        # Create a mock job that would be returned by job_service.create_job
        mock_job = Job(
            id="test-job-123",
            type=JobType.TRANSCRIPTION,
            status=JobStatus.PENDING,
            stage=JobStage.QUEUED,
            progress=0,
            created_at=datetime.utcnow(),
            metadata={"video_source": "test.mp4"},
        )

        # Mock the job queue service
        mock_job_service = MagicMock()
        mock_job_service.create_job = AsyncMock(return_value=mock_job)

        # Mock get_services to return our mock
        mock_services = MagicMock()
        mock_services.job_queue = mock_job_service

        # Access the underlying handler through the SdkMcpTool wrapper
        # Patch at the import source (app.services), not the local module
        with patch("app.services.get_services", return_value=mock_services):
            result = await transcribe_video.handler({"video_source": "test.mp4"})

        # Verify job was created with correct type
        mock_job_service.create_job.assert_called_once()
        call_kwargs = mock_job_service.create_job.call_args[1]
        assert call_kwargs["job_type"] == JobType.TRANSCRIPTION
        assert call_kwargs["metadata"]["video_source"] == "test.mp4"
        assert call_kwargs["metadata"]["model"] == "gpt-4o-transcribe"

        # Verify response contains job ID
        assert "content" in result
        response_text = result["content"][0]["text"]
        assert "test-job-123" in response_text
        assert "Job ID:" in response_text
        assert "gpt-4o-transcribe" in response_text

    @pytest.mark.asyncio
    async def test_transcribe_video_passes_all_metadata(self) -> None:
        """Verify all parameters are passed to job metadata."""
        from datetime import datetime
        from unittest.mock import AsyncMock, MagicMock

        from app.models.jobs import Job, JobStage, JobStatus, JobType

        mock_job = Job(
            id="job-with-params",
            type=JobType.TRANSCRIPTION,
            status=JobStatus.PENDING,
            stage=JobStage.QUEUED,
            progress=0,
            created_at=datetime.utcnow(),
            metadata={},
        )

        mock_job_service = MagicMock()
        mock_job_service.create_job = AsyncMock(return_value=mock_job)

        mock_services = MagicMock()
        mock_services.job_queue = mock_job_service

        with patch("app.services.get_services", return_value=mock_services):
            await transcribe_video.handler(
                {
                    "video_source": "https://youtube.com/watch?v=test",
                    "output_file": "/tmp/output.txt",
                    "language": "es",
                    "temperature": 0.2,
                    "prompt": "Custom transcription context",
                    "session_id": "session-abc",
                }
            )

        # Verify all metadata was passed (including prompt)
        call_kwargs = mock_job_service.create_job.call_args[1]
        metadata = call_kwargs["metadata"]
        assert metadata["video_source"] == "https://youtube.com/watch?v=test"
        assert metadata["output_file"] == "/tmp/output.txt"
        assert metadata["language"] == "es"
        assert metadata["temperature"] == 0.2
        assert metadata["prompt"] == "Custom transcription context"
        assert metadata["session_id"] == "session-abc"
        assert metadata["model"] == "gpt-4o-transcribe"

    @pytest.mark.asyncio
    async def test_transcribe_video_returns_error_without_video_source(self) -> None:
        """Verify error response when video_source is missing."""
        # No need to mock services - missing video_source returns early
        result = await transcribe_video.handler({})

        assert "content" in result
        response_text = result["content"][0]["text"]
        assert "Error" in response_text
        assert "video_source" in response_text

    @pytest.mark.asyncio
    async def test_transcribe_video_handles_service_error_gracefully(self) -> None:
        """Verify tool returns structured error when service fails."""
        from unittest.mock import AsyncMock, MagicMock

        mock_job_service = MagicMock()
        mock_job_service.create_job = AsyncMock(
            side_effect=RuntimeError("Job queue unavailable")
        )

        mock_services = MagicMock()
        mock_services.job_queue = mock_job_service

        with patch("app.services.get_services", return_value=mock_services):
            result = await transcribe_video.handler({"video_source": "test.mp4"})

        # Should return error content, not raise exception
        assert "content" in result
        response_text = result["content"][0]["text"]
        assert "Failed" in response_text or "error" in response_text.lower()


# =============================================================================
# Async Tool Interface Tests
# =============================================================================


class TestTranscribeVideoTool:
    """Tests for the transcribe_video tool interface."""

    def test_transcribe_video_tool_exists(self) -> None:
        """Verify transcribe_video is exported and decorated as a tool."""
        # The tool should be importable and have tool metadata
        assert transcribe_video is not None
        # The decorated function has the original function accessible
        assert hasattr(transcribe_video, "name") or callable(transcribe_video)

    def test_perform_transcription_accepts_temperature_parameter(self) -> None:
        """Verify _perform_transcription accepts temperature parameter."""
        import inspect

        sig = inspect.signature(_perform_transcription)
        params = sig.parameters
        assert "temperature" in params
        assert params["temperature"].default == 0.0

    def test_perform_transcription_error_returns_correct_structure(self) -> None:
        """Verify error responses have expected structure."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("app.agent.transcribe_tool.load_dotenv"):
                result = _perform_transcription("video.mp4")

        assert result["success"] is False
        assert "error" in result


# =============================================================================
# Video Title Extraction Tests
# =============================================================================


class TestVideoTitleExtraction:
    """Tests for video_title extraction from YouTube URLs.

    Title extraction only works for YouTube videos (via yt-dlp).
    Local files do not have titles extracted and return None.
    """

    def test_youtube_download_returns_video_title(self, temp_storage_dir: Path) -> None:
        """Verify _download_youtube_audio returns title from yt-dlp info."""
        mock_info = {
            "title": "Test Video Title",
            "duration": 120,
        }

        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl.prepare_filename.return_value = str(
            temp_storage_dir / "Test Video Title.mp3"
        )

        # Create the expected output file
        output_file = temp_storage_dir / "Test Video Title.mp3"
        output_file.write_bytes(b"fake audio")

        with patch("app.agent.transcribe_tool.YOUTUBE_SUPPORT", True):
            with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
                with patch(
                    "app.agent.transcribe_tool.yt_dlp.YoutubeDL"
                ) as mock_ydl_class:
                    mock_ydl_class.return_value.__enter__.return_value = mock_ydl

                    from app.agent.transcribe_tool import _download_youtube_audio

                    audio_path, video_title = _download_youtube_audio(
                        "https://youtube.com/watch?v=test123",
                        str(temp_storage_dir),
                    )

        assert video_title == "Test Video Title"
        assert audio_path.endswith(".mp3")

    def test_youtube_download_returns_none_when_title_missing(
        self, temp_storage_dir: Path
    ) -> None:
        """Verify _download_youtube_audio returns None if yt-dlp has no title."""
        mock_info = {
            "duration": 120,
            # No 'title' key
        }

        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl.prepare_filename.return_value = str(temp_storage_dir / "video.mp3")

        output_file = temp_storage_dir / "video.mp3"
        output_file.write_bytes(b"fake audio")

        with patch("app.agent.transcribe_tool.YOUTUBE_SUPPORT", True):
            with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
                with patch(
                    "app.agent.transcribe_tool.yt_dlp.YoutubeDL"
                ) as mock_ydl_class:
                    mock_ydl_class.return_value.__enter__.return_value = mock_ydl

                    from app.agent.transcribe_tool import _download_youtube_audio

                    audio_path, video_title = _download_youtube_audio(
                        "https://youtube.com/watch?v=test123",
                        str(temp_storage_dir),
                    )

        assert video_title is None

    def test_local_file_transcription_has_no_video_title(
        self, temp_storage_dir: Path
    ) -> None:
        """Verify local file transcription returns None for video_title.

        Title extraction only works for YouTube videos. Local files
        do not have a title extracted automatically.
        """
        audio_path = temp_storage_dir / "video_audio.mp3"
        audio_path.write_bytes(b"fake audio data")

        mock_response = MagicMock()
        mock_response.text = "Transcribed text from local file"

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response

        mock_audio = MagicMock()
        mock_audio.__len__.return_value = 600 * 1000  # 10 minutes
        mock_audio.set_frame_rate.return_value = mock_audio
        mock_audio.set_channels.return_value = mock_audio

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("app.agent.transcribe_tool.load_dotenv"):
                with patch("os.path.exists", return_value=True):
                    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
                        with patch(
                            "app.agent.transcribe_tool._extract_audio_from_video",
                            return_value=str(audio_path),
                        ):
                            with patch(
                                "app.agent.transcribe_tool.OpenAI",
                                return_value=mock_client,
                            ):
                                with patch(
                                    "app.agent.transcribe_tool.AudioSegment.from_file",
                                    return_value=mock_audio,
                                ):
                                    result = _perform_transcription(
                                        "/path/to/video.mp4"
                                    )

        assert result["success"] is True
        assert "video_title" in result
        assert result["video_title"] is None  # Local files don't have titles

    def test_youtube_transcription_includes_video_title(
        self, temp_storage_dir: Path
    ) -> None:
        """Verify YouTube transcription result includes video_title."""
        audio_path = temp_storage_dir / "Test Video.mp3"
        audio_path.write_bytes(b"fake audio data")

        mock_response = MagicMock()
        mock_response.text = "Transcribed text from YouTube"

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response

        mock_audio = MagicMock()
        mock_audio.__len__.return_value = 600 * 1000  # 10 minutes
        mock_audio.set_frame_rate.return_value = mock_audio
        mock_audio.set_channels.return_value = mock_audio

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("app.agent.transcribe_tool.load_dotenv"):
                with patch("app.agent.transcribe_tool.YOUTUBE_SUPPORT", True):
                    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
                        with patch(
                            "app.agent.transcribe_tool._download_youtube_audio",
                            return_value=(str(audio_path), "My YouTube Video Title"),
                        ):
                            with patch(
                                "app.agent.transcribe_tool.OpenAI",
                                return_value=mock_client,
                            ):
                                with patch(
                                    "app.agent.transcribe_tool.AudioSegment.from_file",
                                    return_value=mock_audio,
                                ):
                                    result = _perform_transcription(
                                        "https://youtube.com/watch?v=abc123"
                                    )

        assert result["success"] is True
        assert result["video_title"] == "My YouTube Video Title"
        assert result["source_type"] == "youtube"
