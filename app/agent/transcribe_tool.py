"""
Video Transcription Tool for Claude Agent SDK.

This module provides a tool for transcribing video files or YouTube URLs
to text using OpenAI's Whisper model.
"""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
from typing import Any

from claude_agent_sdk import tool
from dotenv import load_dotenv
from moviepy import VideoFileClip  # type: ignore[import-untyped]
from openai import OpenAI
from pydub import AudioSegment  # type: ignore[import-untyped]

# Optional YouTube support
try:
    import yt_dlp  # type: ignore[import-untyped]

    YOUTUBE_SUPPORT = True
except ImportError:
    YOUTUBE_SUPPORT = False


def _is_youtube_url(url: str) -> bool:
    """Check if the provided string is a YouTube URL."""
    youtube_regex = r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/"
    return re.match(youtube_regex, url) is not None


def _download_youtube_audio(url: str, output_dir: str) -> str:
    """
    Download audio from YouTube video.

    Args:
        url: YouTube video URL
        output_dir: Directory to save the downloaded audio

    Returns:
        Path to the downloaded audio file

    Raises:
        ImportError: If yt-dlp is not installed
        Exception: If download fails
    """
    if not YOUTUBE_SUPPORT:
        raise ImportError("yt-dlp is not installed. Install with: pip install yt-dlp")

    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }
        ],
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "extractor_args": {"youtube": {"player_client": ["android", "ios"]}},
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        audio_filename = ydl.prepare_filename(info)
        audio_path = os.path.splitext(audio_filename)[0] + ".wav"
        return audio_path


def _extract_audio_from_video(video_path: str, output_dir: str) -> str:
    """
    Extract audio from video file and save as WAV.

    Args:
        video_path: Path to the video file
        output_dir: Directory to save the extracted audio

    Returns:
        Path to the extracted audio file
    """
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    output_audio_path = os.path.join(output_dir, f"{base_name}_audio.wav")

    video = VideoFileClip(video_path)
    video.audio.write_audiofile(
        output_audio_path, codec="pcm_s16le", verbose=False, logger=None
    )
    video.close()

    return output_audio_path


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
    audio = AudioSegment.from_wav(audio_path)

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
) -> str:
    """
    Transcribe a single audio segment using OpenAI Whisper.

    Args:
        client: OpenAI client instance
        audio_segment: Audio segment to transcribe
        segment_num: Segment number for temp file naming
        temp_dir: Directory for temporary files
        language: Optional language code for transcription

    Returns:
        Transcribed text for this segment
    """
    temp_file = os.path.join(temp_dir, f"segment_{segment_num}.wav")

    try:
        audio_segment.export(temp_file, format="wav")

        file_size = os.path.getsize(temp_file)
        if file_size > 23 * 1024 * 1024:
            audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)
            audio_segment.export(temp_file, format="wav")

        with open(temp_file, "rb") as audio_file:
            transcription_args: dict[str, Any] = {
                "model": "whisper-1",
                "file": audio_file,
            }
            if language:
                transcription_args["language"] = language

            transcription = client.audio.transcriptions.create(**transcription_args)

        return transcription.text

    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)


def _perform_transcription(
    video_source: str,
    output_file: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """
    Core transcription logic.

    Args:
        video_source: Path to video file or YouTube URL
        output_file: Optional path to save the transcription
        language: Optional language code for transcription

    Returns:
        Dictionary with transcription results and metadata
    """
    # Ensure environment variables are loaded from .env file
    load_dotenv()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {
            "success": False,
            "error": "OPENAI_API_KEY environment variable is not set",
        }

    client = OpenAI(api_key=api_key)
    is_youtube = _is_youtube_url(video_source)
    audio_path: str | None = None

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            if is_youtube:
                if not YOUTUBE_SUPPORT:
                    return {
                        "success": False,
                        "error": "YouTube support requires yt-dlp. Install with: pip install yt-dlp",
                    }
                audio_path = _download_youtube_audio(video_source, temp_dir)
            else:
                if not os.path.exists(video_source):
                    return {
                        "success": False,
                        "error": f"Video file not found: {video_source}",
                    }
                audio_path = _extract_audio_from_video(video_source, temp_dir)

            segments = _split_audio(audio_path, segment_length_minutes=5)

            transcription_parts: list[str] = []
            for i, segment in enumerate(segments):
                segment_text = _transcribe_segment(
                    client=client,
                    audio_segment=segment,
                    segment_num=i,
                    temp_dir=temp_dir,
                    language=language,
                )
                if segment_text:
                    transcription_parts.append(segment_text)

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
            return {
                "success": False,
                "error": str(e),
                "source": video_source,
            }


@tool(
    "transcribe_video",
    "Transcribe audio from a video file or YouTube URL to text using OpenAI Whisper. "
    "Supports local video files (mp4, mkv, avi, etc.) and YouTube URLs. "
    "Automatically handles long videos by splitting into segments. "
    "Requires OPENAI_API_KEY environment variable to be set.",
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
                "description": "Optional ISO 639-1 language code (e.g., 'en', 'es', 'ru'). "
                "If not provided, Whisper will auto-detect the language.",
            },
        },
        "required": ["video_source"],
    },
)
async def transcribe_video(args: dict[str, Any]) -> dict[str, Any]:
    """
    Transcribe video to text using OpenAI Whisper.

    This tool extracts audio from video files or downloads from YouTube,
    splits long audio into manageable segments, and transcribes using
    OpenAI's Whisper model.

    Args:
        args: Dictionary containing:
            - video_source: Path to video file or YouTube URL (required)
            - output_file: Path to save transcription (optional)
            - language: Language code for transcription (optional)

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

    # Run the blocking transcription in a thread pool
    result = await asyncio.to_thread(
        _perform_transcription,
        video_source=video_source,
        output_file=output_file,
        language=language,
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
