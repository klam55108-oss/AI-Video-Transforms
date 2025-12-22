"""
Video Transcription Tool for Claude Agent SDK.

This module provides a tool for transcribing video files or YouTube URLs
to text using OpenAI's gpt-4o-transcribe model.

IMPORTANT: Uses gpt-4o-transcribe which:
- Returns plain text transcription (no timestamps, no speaker diarization)
- Supports prompt parameter for context/formatting hints
- Has 25-minute (1500s) duration limit per request
- For longer audio, files are automatically split into chunks

See: https://platform.openai.com/docs/api-reference/audio/createTranscription
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any

from claude_agent_sdk import tool
from dotenv import load_dotenv
from openai import OpenAI
from pydub import AudioSegment  # type: ignore[import-untyped]

# NOTE: Import removed - DEFAULT_TRANSCRIPTION_PROMPT is defined in prompts module

# Set up logging for transcription debugging
logger = logging.getLogger(__name__)

# Optional YouTube support
try:
    import yt_dlp  # type: ignore[import-untyped]

    YOUTUBE_SUPPORT = True
except ImportError:
    YOUTUBE_SUPPORT = False


def _check_ffmpeg_available() -> bool:
    """Check if FFmpeg is available in the system PATH."""
    return shutil.which("ffmpeg") is not None


def _is_youtube_url(url: str) -> bool:
    """Check if the provided string is a YouTube URL."""
    youtube_regex = r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/"
    return re.match(youtube_regex, url) is not None


def _download_youtube_audio(url: str, output_dir: str) -> str:
    """
    Download audio from YouTube video as MP3.

    Args:
        url: YouTube video URL
        output_dir: Directory to save the downloaded audio

    Returns:
        Path to the downloaded MP3 audio file

    Raises:
        ImportError: If yt-dlp is not installed
        RuntimeError: If FFmpeg is not available
        Exception: If download fails
    """
    if not YOUTUBE_SUPPORT:
        raise ImportError("yt-dlp is not installed. Install with: pip install yt-dlp")

    if not _check_ffmpeg_available():
        raise RuntimeError(
            "FFmpeg is required for YouTube audio extraction. Please install FFmpeg."
        )

    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "quiet": False,  # Enable output for debugging
        "no_warnings": False,
        "nocheckcertificate": True,
        "extractor_args": {"youtube": {"player_client": ["android", "ios"]}},
    }

    logger.info(f"yt-dlp: Starting download for {url}")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            logger.info(f"yt-dlp: Video title: {info.get('title', 'Unknown')}")
            logger.info(f"yt-dlp: Duration: {info.get('duration', 'Unknown')} seconds")
            audio_filename = ydl.prepare_filename(info)
            audio_path = os.path.splitext(audio_filename)[0] + ".mp3"
            logger.info(f"yt-dlp: Audio saved to: {audio_path}")
            return audio_path
    except Exception as e:
        logger.error(f"yt-dlp: Download failed: {e}", exc_info=True)
        raise


def _extract_audio_from_video(video_path: str, output_dir: str) -> str:
    """
    Extract audio from video file using FFmpeg and save as MP3.

    Args:
        video_path: Path to the video file
        output_dir: Directory to save the extracted audio

    Returns:
        Path to the extracted MP3 audio file

    Raises:
        RuntimeError: If FFmpeg is not available or extraction fails
    """
    if not _check_ffmpeg_available():
        raise RuntimeError(
            "FFmpeg is not installed or not in PATH. "
            "Install with: apt install ffmpeg (Linux) or brew install ffmpeg (macOS)"
        )

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    output_audio_path = os.path.join(output_dir, f"{base_name}_audio.mp3")

    cmd = [
        "ffmpeg",
        "-i",
        video_path,
        "-vn",  # No video
        "-acodec",
        "libmp3lame",  # MP3 codec
        "-ar",
        "44100",  # Sample rate
        "-ac",
        "2",  # Stereo
        "-q:a",
        "2",  # Quality (VBR, 0-9 where lower is better)
        "-y",  # Overwrite output
        output_audio_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=300,  # 5 minute timeout
            check=False,
        )

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"FFmpeg audio extraction failed: {stderr}")

        return output_audio_path

    except subprocess.TimeoutExpired as e:
        raise RuntimeError("FFmpeg audio extraction timed out after 5 minutes") from e


def _split_audio_for_duration(
    audio_path: str,
    max_duration_sec: int = 1400,  # Under 1500s limit with margin
    output_dir: str | None = None,
) -> list[str]:
    """
    Split audio into chunks under 25 minutes for API limit.

    The gpt-4o-transcribe API has a 1500-second (25-minute) duration limit.
    This function splits longer audio files into chunks with margin for safety.

    Args:
        audio_path: Path to the audio file
        max_duration_sec: Maximum chunk duration (default: 1400s = 23.3min)
        output_dir: Directory for chunk files (defaults to temp dir)

    Returns:
        List of paths to audio chunks (original file if no splitting needed)

    Raises:
        RuntimeError: If audio splitting fails
    """
    audio = AudioSegment.from_file(audio_path)
    duration_ms = len(audio)
    max_chunk_ms = max_duration_sec * 1000

    if duration_ms <= max_chunk_ms:
        return [audio_path]  # No splitting needed

    if output_dir is None:
        output_dir = os.path.dirname(audio_path)

    chunks = []
    for i, start_ms in enumerate(range(0, duration_ms, max_chunk_ms)):
        chunk = audio[start_ms : start_ms + max_chunk_ms]

        # Skip very short chunks (< 100ms) that can occur at exact boundaries
        if len(chunk) < 100:
            logger.debug(f"Skipping chunk {i}: too short ({len(chunk)}ms)")
            continue

        chunk_path = os.path.join(output_dir, f"chunk_{i:03d}.mp3")
        chunk.export(chunk_path, format="mp3", bitrate="128k")
        chunks.append(chunk_path)
        logger.info(
            f"Created chunk {i}: {chunk_path} ({len(chunk) / 1000:.1f}s, {os.path.getsize(chunk_path) / 1024 / 1024:.1f}MB)"
        )

    return chunks


class TranscriptionError(Exception):
    """Raised when transcription fails or returns invalid data."""

    pass


def _transcribe_audio_file(
    client: OpenAI,
    audio_path: str,
    language: str | None = None,
    temperature: float = 0.0,
    prompt: str | None = None,
) -> str:
    """
    Transcribe an audio file using OpenAI gpt-4o-transcribe.

    Returns plain text transcription without timestamps or speaker diarization.

    Args:
        client: OpenAI client instance
        audio_path: Path to the audio file (MP3)
        language: Optional language code (ISO-639-1) for transcription
        temperature: Sampling temperature 0-1 (default: 0.0)
        prompt: Optional context/formatting hint for the transcription

    Returns:
        Transcribed text string

    Raises:
        TranscriptionError: If API fails or returns empty text
    """
    file_size = os.path.getsize(audio_path)
    logger.info(
        f"Transcribing audio file: {audio_path}, size={file_size / 1024 / 1024:.1f}MB"
    )

    # Check file size - OpenAI limit is 25MB
    if file_size > 25 * 1024 * 1024:
        raise TranscriptionError(
            f"Audio file too large ({file_size / 1024 / 1024:.1f}MB). "
            "OpenAI limit is 25MB."
        )

    try:
        with open(audio_path, "rb") as audio_file:
            transcription_args: dict[str, Any] = {
                "model": "gpt-4o-transcribe",
                "file": audio_file,
                "response_format": "json",
                "temperature": temperature,
            }

            if language:
                transcription_args["language"] = language

            if prompt:
                transcription_args["prompt"] = prompt

            logger.info(
                f"Calling OpenAI API: model=gpt-4o-transcribe, "
                f"language={language or 'auto'}, prompt={'yes' if prompt else 'no'}"
            )

            transcription = client.audio.transcriptions.create(**transcription_args)

        # Extract text from response
        text = getattr(transcription, "text", None) or ""

        if not text:
            raise TranscriptionError(
                "OpenAI API returned empty transcription. "
                "Check if the audio file contains audible speech."
            )

        logger.info(f"Transcription complete: {len(text)} chars")

        return text

    except TranscriptionError:
        raise

    except Exception as e:
        logger.error(f"Transcription API call failed: {e}", exc_info=True)
        raise TranscriptionError(f"OpenAI transcription API failed: {str(e)}") from e


def _perform_transcription(
    video_source: str,
    output_file: str | None = None,
    language: str | None = None,
    temperature: float = 0.0,
    prompt: str | None = None,
) -> dict[str, Any]:
    """
    Core transcription logic using OpenAI gpt-4o-transcribe.

    Handles audio extraction, splitting for 25-minute limit, and transcription.
    For audio longer than 25 minutes, automatically splits into chunks and
    concatenates results.

    Args:
        video_source: Path to video file or YouTube URL
        output_file: Optional path to save the transcription
        language: Optional language code for transcription (improves accuracy)
        temperature: Sampling temperature 0-1, lower is more deterministic (default: 0.0)
        prompt: Optional context/formatting hint for transcription

    Returns:
        Dictionary with transcription results and metadata

    Raises:
        TranscriptionError: If transcription fails (NO silent fallbacks)
    """
    load_dotenv()
    logger.info(f"Starting transcription: source={video_source}, language={language}")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set")
        return {
            "success": False,
            "error": "OPENAI_API_KEY environment variable is not set",
        }

    client = OpenAI(api_key=api_key)
    is_youtube = _is_youtube_url(video_source)
    logger.info(f"Source type: {'YouTube' if is_youtube else 'local file'}")

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Extract audio
            if is_youtube:
                if not YOUTUBE_SUPPORT:
                    logger.error("yt-dlp not installed")
                    return {
                        "success": False,
                        "error": "YouTube support requires yt-dlp. Install with: pip install yt-dlp",
                    }
                logger.info(f"Downloading YouTube audio from: {video_source}")
                audio_path = _download_youtube_audio(video_source, temp_dir)
                logger.info(f"YouTube audio downloaded: {audio_path}")
            else:
                if not os.path.exists(video_source):
                    logger.error(f"Video file not found: {video_source}")
                    return {
                        "success": False,
                        "error": f"Video file not found: {video_source}",
                    }
                logger.info(f"Extracting audio from local video: {video_source}")
                audio_path = _extract_audio_from_video(video_source, temp_dir)
                logger.info(f"Audio extracted: {audio_path}")

            # Get audio duration
            audio = AudioSegment.from_file(audio_path)
            duration = len(audio) / 1000.0  # Convert ms to seconds
            logger.info(f"Audio duration: {duration:.1f}s ({duration / 60:.1f}min)")

            # Split audio if needed for 25-minute API limit
            chunks = _split_audio_for_duration(
                audio_path, max_duration_sec=1400, output_dir=temp_dir
            )

            logger.info(f"Processing {len(chunks)} audio chunk(s)")

            # Transcribe each chunk
            chunk_texts: list[str] = []
            for i, chunk_path in enumerate(chunks):
                logger.info(f"Transcribing chunk {i + 1}/{len(chunks)}")

                # Use prompt for first chunk, continuation context for subsequent chunks
                chunk_prompt = prompt if i == 0 else None
                if i > 0 and chunk_texts:
                    # Add last 100 chars of previous chunk as context
                    chunk_prompt = chunk_texts[-1][-100:]

                chunk_text = _transcribe_audio_file(
                    client=client,
                    audio_path=chunk_path,
                    language=language,
                    temperature=temperature,
                    prompt=chunk_prompt,
                )
                chunk_texts.append(chunk_text)

            # Concatenate chunks
            full_transcription = " ".join(chunk_texts)
            logger.info(
                f"Transcription complete: {len(chunks)} chunk(s), {len(full_transcription)} chars"
            )

            # Write output file if requested
            if output_file:
                from app.core.permissions import validate_file_path

                is_valid, error_msg = validate_file_path(output_file)
                if not is_valid:
                    logger.warning(f"Blocked write to: {output_file} - {error_msg}")
                else:
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(full_transcription)

            return {
                "success": True,
                "transcription": full_transcription,
                "source": video_source,
                "source_type": "youtube" if is_youtube else "local_file",
                "model": "gpt-4o-transcribe",
                "output_file": output_file,
                "duration": duration,
                "chunk_count": len(chunks),
            }

        except TranscriptionError as e:
            logger.error(f"Transcription failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "source": video_source,
                "error_type": "validation",
            }

        except Exception as e:
            logger.error(f"Transcription failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "source": video_source,
            }


@tool(
    "transcribe_video",
    "Create a background job to transcribe audio from a video file or YouTube URL. "
    "Returns immediately with a job ID for tracking progress. "
    "Supports local video files (mp4, mkv, avi, etc.) and YouTube URLs. "
    "Uses gpt-4o-transcribe model with automatic chunking for videos > 25 minutes. "
    "Supports optional prompt parameter for domain-specific vocabulary. "
    "Requires OPENAI_API_KEY environment variable and FFmpeg installed.",
    {
        "type": "object",
        "properties": {
            "video_source": {
                "type": "string",
                "description": "Path to a local video file OR a YouTube URL to transcribe",
            },
            "output_file": {
                "type": "string",
                "description": "Optional path to save the transcription as a text file",
            },
            "language": {
                "type": "string",
                "description": "Optional ISO 639-1 language code (e.g., 'en', 'es', 'zh'). "
                "Providing this improves accuracy and reduces latency.",
            },
            "temperature": {
                "type": "number",
                "description": "Sampling temperature 0-1. Lower values (0.0) give more "
                "deterministic results. Default: 0.0",
            },
            "prompt": {
                "type": "string",
                "description": "Optional context or formatting hint. Use to improve accuracy for "
                "technical terms, proper nouns, acronyms, or specific formatting preferences. "
                "Example: 'This is a lecture about quantum physics with terms like entanglement and superposition.'",
            },
            "session_id": {
                "type": "string",
                "description": "Optional session ID to link the transcript to a chat session",
            },
        },
        "required": ["video_source"],
    },
)
async def transcribe_video(args: dict[str, Any]) -> dict[str, Any]:
    """
    Create a background transcription job.

    This tool creates an asynchronous job to transcribe video/audio using
    gpt-4o-transcribe. The job runs in the background, allowing the user
    to monitor progress via the Jobs panel.

    Features:
        - Plain text transcription (no timestamps or speaker diarization)
        - Optional prompt for domain-specific vocabulary
        - Automatic chunking for videos > 25 minutes

    Args:
        args: Dictionary containing:
            - video_source: Path to video file or YouTube URL (required)
            - output_file: Path to save transcription (optional)
            - language: Language code (ISO-639-1) for transcription (optional)
            - temperature: Sampling temperature 0-1 (optional, default 0.0)
            - prompt: Context/formatting hint (optional)
            - session_id: Session ID to link transcript (optional)

    Returns:
        Structured response with job ID for progress tracking
    """
    try:
        video_source = args.get("video_source")
        if not video_source:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Error: video_source parameter is required",
                    }
                ]
            }

        # Get job queue service
        from app.models.jobs import JobType
        from app.services import get_services

        job_service = get_services().job_queue

        # Create job with metadata
        job = await job_service.create_job(
            job_type=JobType.TRANSCRIPTION,
            metadata={
                "video_source": video_source,
                "output_file": args.get("output_file"),
                "language": args.get("language"),
                "temperature": args.get("temperature", 0.0),
                "prompt": args.get("prompt"),
                "session_id": args.get("session_id"),
                "model": "gpt-4o-transcribe",
            },
        )

        prompt_text = args.get("prompt")
        prompt_info = f"Prompt: {prompt_text[:50]}...\n" if prompt_text else ""

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Started transcription job: {job.id}\n\n"
                    f"Source: {video_source}\n"
                    f"Model: gpt-4o-transcribe (plain text)\n"
                    f"{prompt_info}"
                    f"Job ID: {job.id}\n\n"
                    "You can monitor progress in the Jobs panel. "
                    "The transcript will be automatically saved to the library when complete.",
                }
            ]
        }

    except Exception as e:
        logger.error(f"Failed to create transcription job: {e}", exc_info=True)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Failed to create transcription job: {str(e)}",
                }
            ]
        }
