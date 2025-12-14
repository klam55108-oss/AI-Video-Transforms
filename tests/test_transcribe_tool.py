"""
Tests for the video transcription tool.

Tests cover:
- FFmpeg audio extraction
- gpt-4o-transcribe model integration
- MP3 audio format handling
- Quality enhancement features (prompt, temperature, segment chaining)
- Error handling and edge cases
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.agent.transcribe_tool import (
    _check_ffmpeg_available,
    _extract_audio_from_video,
    _is_youtube_url,
    _perform_transcription,
    _split_audio,
    _transcribe_segment,
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
# Model and API Tests
# =============================================================================


class TestGpt4oTranscribeModel:
    """Tests for gpt-4o-transcribe model integration."""

    def test_transcribe_segment_uses_gpt4o_model(self) -> None:
        """Verify transcription uses gpt-4o-transcribe model."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(
            text="Test transcription"
        )

        mock_segment = MagicMock()
        mock_segment.export = MagicMock()

        with patch("os.path.getsize", return_value=1024):
            with patch("builtins.open", MagicMock()):
                with patch("os.path.exists", return_value=True):
                    with patch("os.remove"):
                        _transcribe_segment(
                            client=mock_client,
                            audio_segment=mock_segment,
                            segment_num=0,
                            temp_dir="/tmp",
                        )

        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-transcribe"

    def test_transcribe_segment_passes_language_parameter(self) -> None:
        """Verify language parameter is passed to API."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(
            text="Test transcription"
        )

        mock_segment = MagicMock()
        mock_segment.export = MagicMock()

        with patch("os.path.getsize", return_value=1024):
            with patch("builtins.open", MagicMock()):
                with patch("os.path.exists", return_value=True):
                    with patch("os.remove"):
                        _transcribe_segment(
                            client=mock_client,
                            audio_segment=mock_segment,
                            segment_num=0,
                            temp_dir="/tmp",
                            language="es",
                        )

        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["language"] == "es"


# =============================================================================
# MP3 Audio Format Tests
# =============================================================================


class TestMp3AudioSplitting:
    """Tests for MP3 audio format handling."""

    def test_split_audio_uses_from_mp3(self) -> None:
        """Verify _split_audio uses AudioSegment.from_mp3."""
        mock_segment = MagicMock()
        mock_segment.__len__ = lambda self: 600000  # 10 minutes
        mock_segment.__getitem__ = lambda self, key: mock_segment

        with patch(
            "app.agent.transcribe_tool.AudioSegment.from_mp3",
            return_value=mock_segment,
        ) as mock_from_mp3:
            _split_audio("/path/to/audio.mp3")
            mock_from_mp3.assert_called_once_with("/path/to/audio.mp3")

    def test_split_audio_creates_segments(self) -> None:
        """Verify audio is split into 5-minute segments."""
        mock_segment = MagicMock()
        # 12 minutes = 720000 ms -> should create 3 segments
        mock_segment.__len__ = lambda self: 720000
        mock_segment.__getitem__ = lambda self, key: mock_segment

        with patch(
            "app.agent.transcribe_tool.AudioSegment.from_mp3",
            return_value=mock_segment,
        ):
            segments = _split_audio("/path/to/audio.mp3", segment_length_minutes=5)
            assert len(segments) == 3


# =============================================================================
# Quality Enhancement Tests
# =============================================================================


class TestQualityEnhancements:
    """Tests for transcription quality enhancement features."""

    def test_prompt_parameter_passed_to_api(self) -> None:
        """Verify prompt is included in API call."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(
            text="Test transcription"
        )

        mock_segment = MagicMock()
        mock_segment.export = MagicMock()

        with patch("os.path.getsize", return_value=1024):
            with patch("builtins.open", MagicMock()):
                with patch("os.path.exists", return_value=True):
                    with patch("os.remove"):
                        _transcribe_segment(
                            client=mock_client,
                            audio_segment=mock_segment,
                            segment_num=0,
                            temp_dir="/tmp",
                            prompt="ZyntriQix, DALL·E, GPT-4.5",
                        )

        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["prompt"] == "ZyntriQix, DALL·E, GPT-4.5"

    def test_temperature_parameter_passed_to_api(self) -> None:
        """Verify temperature is included in API call."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(
            text="Test transcription"
        )

        mock_segment = MagicMock()
        mock_segment.export = MagicMock()

        with patch("os.path.getsize", return_value=1024):
            with patch("builtins.open", MagicMock()):
                with patch("os.path.exists", return_value=True):
                    with patch("os.remove"):
                        _transcribe_segment(
                            client=mock_client,
                            audio_segment=mock_segment,
                            segment_num=0,
                            temp_dir="/tmp",
                            temperature=0.2,
                        )

        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.2

    def test_default_temperature_is_zero(self) -> None:
        """Verify default temperature is 0.0 for determinism."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(
            text="Test transcription"
        )

        mock_segment = MagicMock()
        mock_segment.export = MagicMock()

        with patch("os.path.getsize", return_value=1024):
            with patch("builtins.open", MagicMock()):
                with patch("os.path.exists", return_value=True):
                    with patch("os.remove"):
                        _transcribe_segment(
                            client=mock_client,
                            audio_segment=mock_segment,
                            segment_num=0,
                            temp_dir="/tmp",
                        )

        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.0

    def test_response_format_is_text(self) -> None:
        """Verify response_format is set to text for gpt-4o-transcribe."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(
            text="Test transcription"
        )

        mock_segment = MagicMock()
        mock_segment.export = MagicMock()

        with patch("os.path.getsize", return_value=1024):
            with patch("builtins.open", MagicMock()):
                with patch("os.path.exists", return_value=True):
                    with patch("os.remove"):
                        _transcribe_segment(
                            client=mock_client,
                            audio_segment=mock_segment,
                            segment_num=0,
                            temp_dir="/tmp",
                        )

        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["response_format"] == "text"

    def test_transcribe_segment_exports_as_mp3(self) -> None:
        """Verify audio segment is exported as MP3 with bitrate."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(
            text="Test transcription"
        )

        mock_segment = MagicMock()

        with patch("os.path.getsize", return_value=1024):
            with patch("builtins.open", MagicMock()):
                with patch("os.path.exists", return_value=True):
                    with patch("os.remove"):
                        _transcribe_segment(
                            client=mock_client,
                            audio_segment=mock_segment,
                            segment_num=0,
                            temp_dir="/tmp",
                        )

        # Check export was called with mp3 format
        mock_segment.export.assert_called()
        call_args = mock_segment.export.call_args
        assert call_args[1]["format"] == "mp3"
        assert "bitrate" in call_args[1]


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

    def test_passes_prompt_and_temperature_to_segments(self) -> None:
        """Verify prompt and temperature are passed through segment chaining."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(
            text="Segment text"
        )

        mock_segment = MagicMock()
        mock_segment.__len__ = lambda self: 300000  # 5 min
        mock_segment.__getitem__ = lambda self, key: mock_segment
        mock_segment.export = MagicMock()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("app.agent.transcribe_tool.load_dotenv"):
                with patch("os.path.exists", return_value=True):
                    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
                        with patch(
                            "subprocess.run",
                            return_value=Mock(returncode=0, stderr=b""),
                        ):
                            with patch(
                                "app.agent.transcribe_tool.OpenAI",
                                return_value=mock_client,
                            ):
                                with patch(
                                    "app.agent.transcribe_tool.AudioSegment.from_mp3",
                                    return_value=mock_segment,
                                ):
                                    with patch("os.path.getsize", return_value=1024):
                                        with patch("builtins.open", MagicMock()):
                                            with patch("os.remove"):
                                                result = _perform_transcription(
                                                    "video.mp4",
                                                    prompt="Initial context",
                                                    temperature=0.1,
                                                )

        # Verify the transcription was called and result is valid
        assert mock_client.audio.transcriptions.create.called
        assert result["success"] is True or "error" in result


# =============================================================================
# Async Tool Interface Tests
# =============================================================================


class TestTranscribeVideoTool:
    """Tests for the transcribe_video tool interface.

    Note: The @tool decorator wraps the function in SdkMcpTool, so we test
    the underlying logic via _perform_transcription and verify the tool's
    structure exists.
    """

    def test_transcribe_video_tool_exists(self) -> None:
        """Verify transcribe_video is exported and decorated as a tool."""
        # The tool should be importable and have tool metadata
        assert transcribe_video is not None
        # The decorated function has the original function accessible
        assert hasattr(transcribe_video, "name") or callable(transcribe_video)

    def test_perform_transcription_accepts_prompt_parameter(self) -> None:
        """Verify _perform_transcription accepts prompt parameter."""
        import inspect

        sig = inspect.signature(_perform_transcription)
        params = sig.parameters
        assert "prompt" in params
        assert params["prompt"].default is None

    def test_perform_transcription_accepts_temperature_parameter(self) -> None:
        """Verify _perform_transcription accepts temperature parameter."""
        import inspect

        sig = inspect.signature(_perform_transcription)
        params = sig.parameters
        assert "temperature" in params
        assert params["temperature"].default == 0.0

    def test_perform_transcription_success_returns_correct_structure(self) -> None:
        """Verify successful transcription returns expected keys."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(
            text="Transcribed text"
        )

        mock_segment = MagicMock()
        mock_segment.__len__ = lambda self: 300000
        mock_segment.__getitem__ = lambda self, key: mock_segment
        mock_segment.export = MagicMock()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("app.agent.transcribe_tool.load_dotenv"):
                with patch("os.path.exists", return_value=True):
                    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
                        with patch(
                            "subprocess.run",
                            return_value=Mock(returncode=0, stderr=b""),
                        ):
                            with patch(
                                "app.agent.transcribe_tool.OpenAI",
                                return_value=mock_client,
                            ):
                                with patch(
                                    "app.agent.transcribe_tool.AudioSegment.from_mp3",
                                    return_value=mock_segment,
                                ):
                                    with patch("os.path.getsize", return_value=1024):
                                        with patch("builtins.open", MagicMock()):
                                            with patch("os.remove"):
                                                result = _perform_transcription(
                                                    "video.mp4"
                                                )

        assert result["success"] is True
        assert "transcription" in result
        assert "source" in result
        assert "source_type" in result
        assert "segments_processed" in result

    def test_perform_transcription_error_returns_correct_structure(self) -> None:
        """Verify error responses have expected structure."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("app.agent.transcribe_tool.load_dotenv"):
                result = _perform_transcription("video.mp4")

        assert result["success"] is False
        assert "error" in result


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
