"""
Video Transcription Tool for Claude Agent SDK.

This module provides a tool for transcribing video files or YouTube URLs
to text using OpenAI's gpt-4o-transcribe model with quality enhancement features.
"""

from __future__ import annotations

import asyncio
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

from app.agent.prompts import DEFAULT_TRANSCRIPTION_PROMPT

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
        "-i", video_path,
        "-vn",                    # No video
        "-acodec", "libmp3lame",  # MP3 codec
        "-ar", "44100",           # Sample rate
        "-ac", "2",               # Stereo
        "-q:a", "2",              # Quality (VBR, 0-9 where lower is better)
        "-y",                     # Overwrite output
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


def _split_audio(
    audio_path: str, segment_length_minutes: int = 5
) -> list[AudioSegment]:
    """
    Split audio into smaller segments to stay under OpenAI's 25MB limit.

    Args:
        audio_path: Path to the audio file
        segment_length_minutes: Length of each segment in minutes

    Returns:
        List of AudioSegment objects
    """
    segment_length_ms = segment_length_minutes * 60 * 1000
    audio = AudioSegment.from_mp3(audio_path)

    segments = []
    for i in range(0, len(audio), segment_length_ms):
        segment = audio[i : i + segment_length_ms]
        segments.append(segment)

    return segments


def _transcribe_segment(
    client: OpenAI,
    audio_segment: AudioSegment,
    segment_num: int,
    temp_dir: str,
    language: str | None = None,
    prompt: str | None = None,
    temperature: float = 0.0,
) -> str:
    """
    Transcribe a single audio segment using OpenAI gpt-4o-transcribe.

    Args:
        client: OpenAI client instance
        audio_segment: Audio segment to transcribe
        segment_num: Segment number for temp file naming
        temp_dir: Directory for temporary files
        language: Optional language code for transcription (improves accuracy)
        prompt: Optional context prompt for quality enhancement (e.g., previous segment)
        temperature: Sampling temperature 0-1, lower is more deterministic (default: 0.0)

    Returns:
        Transcribed text for this segment
    """
    temp_file = os.path.join(temp_dir, f"segment_{segment_num}.mp3")
    logger.info(f"Transcribing segment {segment_num}, temp_file={temp_file}")

    try:
        audio_segment.export(temp_file, format="mp3", bitrate="128k")

        file_size = os.path.getsize(temp_file)
        logger.info(f"Segment {segment_num}: exported MP3, size={file_size} bytes")

        if file_size > 23 * 1024 * 1024:
            # Reduce quality to stay under OpenAI's 25MB limit
            logger.warning(f"Segment {segment_num}: file too large, reducing quality")
            audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)
            audio_segment.export(temp_file, format="mp3", bitrate="64k")
            file_size = os.path.getsize(temp_file)
            logger.info(f"Segment {segment_num}: reduced size={file_size} bytes")

        with open(temp_file, "rb") as audio_file:
            transcription_args: dict[str, Any] = {
                "model": "gpt-4o-transcribe",
                "file": audio_file,
                "response_format": "text",
                "temperature": temperature,
            }
            if language:
                transcription_args["language"] = language
            if prompt:
                transcription_args["prompt"] = prompt

            logger.info(f"Segment {segment_num}: calling OpenAI API with model=gpt-4o-transcribe")
            transcription = client.audio.transcriptions.create(**transcription_args)

        # response_format="text" returns a string directly, not an object
        result = transcription if isinstance(transcription, str) else transcription.text
        logger.info(f"Segment {segment_num}: transcription complete, length={len(result)} chars")
        return result

    except Exception as e:
        logger.error(f"Segment {segment_num}: transcription failed: {e}", exc_info=True)
        raise

    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)


def _perform_transcription(
    video_source: str,
    output_file: str | None = None,
    language: str | None = None,
    prompt: str | None = None,
    temperature: float = 0.0,
) -> dict[str, Any]:
    """
    Core transcription logic using OpenAI gpt-4o-transcribe.

    Uses segment context chaining: each segment receives the previous segment's
    transcription as its prompt, maintaining context across long videos.

    Args:
        video_source: Path to video file or YouTube URL
        output_file: Optional path to save the transcription
        language: Optional language code for transcription (improves accuracy)
        prompt: Optional initial context prompt for quality enhancement
        temperature: Sampling temperature 0-1, lower is more deterministic (default: 0.0)

    Returns:
        Dictionary with transcription results and metadata
    """
    # Ensure environment variables are loaded from .env file
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
    audio_path: str | None = None

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
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

            logger.info("Splitting audio into segments...")
            segments = _split_audio(audio_path, segment_length_minutes=5)
            logger.info(f"Audio split into {len(segments)} segments")

            transcription_parts: list[str] = []
            # Use user prompt if provided, otherwise use default for quality
            # This becomes the initial context for segment chaining
            initial_prompt = prompt if prompt else DEFAULT_TRANSCRIPTION_PROMPT
            previous_context = initial_prompt

            for i, segment in enumerate(segments):
                # Use previous segment's transcription as context (last 500 chars)
                segment_prompt = previous_context[-500:] if previous_context else None

                segment_text = _transcribe_segment(
                    client=client,
                    audio_segment=segment,
                    segment_num=i,
                    temp_dir=temp_dir,
                    language=language,
                    prompt=segment_prompt,
                    temperature=temperature,
                )
                if segment_text:
                    transcription_parts.append(segment_text)
                    previous_context = segment_text  # Chain for next segment

            full_transcription = " ".join(transcription_parts)

            if output_file:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(full_transcription)

            return {
                "success": True,
                "transcription": full_transcription,
                "source": video_source,
                "source_type": "youtube" if is_youtube else "local_file",
                "segments_processed": len(segments),
                "output_file": output_file,
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
    "Transcribe audio from a video file or YouTube URL to text using OpenAI gpt-4o-transcribe. "
    "Supports local video files (mp4, mkv, avi, etc.) and YouTube URLs. "
    "Automatically handles long videos by splitting into segments with context chaining. "
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
            "prompt": {
                "type": "string",
                "description": "Optional text to guide transcription style. Use to: "
                "(1) specify domain terms/acronyms, (2) set punctuation style, "
                "(3) preserve filler words like 'umm', (4) specify writing style.",
            },
            "temperature": {
                "type": "number",
                "description": "Sampling temperature 0-1. Lower values (0.0) give more "
                "deterministic results. Default: 0.0",
            },
        },
        "required": ["video_source"],
    },
)
async def transcribe_video(args: dict[str, Any]) -> dict[str, Any]:
    """
    Transcribe video to text using OpenAI gpt-4o-transcribe.

    This tool extracts audio from video files using FFmpeg or downloads from YouTube,
    splits long audio into manageable segments with context chaining, and transcribes
    using OpenAI's gpt-4o-transcribe model with quality enhancement features.

    Args:
        args: Dictionary containing:
            - video_source: Path to video file or YouTube URL (required)
            - output_file: Path to save transcription (optional)
            - language: Language code for transcription (optional, improves accuracy)
            - prompt: Context prompt to guide transcription style (optional)
            - temperature: Sampling temperature 0-1 (optional, default 0.0)

    Returns:
        Structured response with transcription results or error message
    """
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

    output_file = args.get("output_file")
    language = args.get("language")
    prompt = args.get("prompt")
    temperature = args.get("temperature", 0.0)

    # Run the blocking transcription in a thread pool
    result = await asyncio.to_thread(
        _perform_transcription,
        video_source=video_source,
        output_file=output_file,
        language=language,
        prompt=prompt,
        temperature=temperature,
    )

    if result["success"]:
        response_parts = [
            "Transcription completed successfully.",
            f"Source: {result['source']} ({result['source_type']})",
            f"Segments processed: {result['segments_processed']}",
        ]
        if result.get("output_file"):
            response_parts.append(f"Saved to: {result['output_file']}")
        response_parts.append("")
        response_parts.append("--- TRANSCRIPTION ---")
        response_parts.append(result["transcription"])

        return {
            "content": [
                {
                    "type": "text",
                    "text": "\n".join(response_parts),
                }
            ]
        }
    else:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Transcription failed: {result['error']}",
                }
            ]
        }
