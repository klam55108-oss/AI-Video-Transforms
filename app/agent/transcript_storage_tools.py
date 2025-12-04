"""
Transcript Storage Tools for Claude Agent SDK.

This module provides tools for persisting and retrieving transcripts, separating
raw transcription storage from arbitrary file operations. This enables:
- Automatic registration in the transcript library
- Context-efficient lazy loading of transcript content
- Clear separation between transcripts and derived artifacts (summaries, notes)

Architecture:
    save_transcript: Called immediately after transcription to persist and register
    get_transcript: Retrieves content by ID when needed (lazy loading)
    list_transcripts: Shows available transcripts for reference

This reduces context window usage by storing large transcripts externally and
referencing them by ID rather than keeping full content in memory.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool

from app.core.storage import storage


def _sanitize_filename(name: str) -> str:
    """
    Sanitize a string for use as a filename.

    Removes or replaces characters that are unsafe for filenames.

    Args:
        name: The string to sanitize.

    Returns:
        A safe filename string.
    """
    # Remove or replace unsafe characters
    safe = re.sub(r'[<>:"/\\|?*]', "_", name)
    # Replace multiple underscores/spaces with single underscore
    safe = re.sub(r"[_\s]+", "_", safe)
    # Remove leading/trailing underscores and dots
    safe = safe.strip("_.")
    # Truncate to reasonable length
    return safe[:100] if safe else "transcript"


def _generate_filename(source: str, source_type: str) -> str:
    """
    Generate a descriptive filename for a transcript.

    Args:
        source: Original source (YouTube URL or file path).
        source_type: Type of source ("youtube", "upload", "local").

    Returns:
        A sanitized filename with timestamp.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if source_type == "youtube":
        # Extract video ID or title hint from URL
        video_id_match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", source)
        if video_id_match:
            base = f"youtube_{video_id_match.group(1)}"
        else:
            base = "youtube_video"
    else:
        # Use file stem for local/upload sources
        base = Path(source).stem
        base = _sanitize_filename(base)

    return f"{base}_{timestamp}.txt"


def _write_transcript_sync(path: Path, content: str) -> tuple[int, int]:
    """
    Synchronous transcript write operation.

    Returns:
        Tuple of (file_size, line_count)
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    file_size = path.stat().st_size
    line_count = content.count("\n") + (
        1 if content and not content.endswith("\n") else 0
    )
    return file_size, line_count


@tool(
    "save_transcript",
    "Save a raw transcription to the transcript library and get a reference ID. "
    "Use this IMMEDIATELY after transcribing to persist the content and free up context. "
    "Returns a transcript ID that can be used with get_transcript to retrieve content later. "
    "This is different from write_file which is for arbitrary files like summaries.",
    {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The full transcription text to save.",
            },
            "original_source": {
                "type": "string",
                "description": "The original video source (YouTube URL or file path).",
            },
            "source_type": {
                "type": "string",
                "enum": ["youtube", "upload", "local"],
                "description": "Type of the video source.",
            },
            "session_id": {
                "type": "string",
                "description": "Optional session ID to link the transcript to.",
            },
            "custom_filename": {
                "type": "string",
                "description": "Optional custom filename (without extension). "
                "If not provided, a descriptive name will be generated.",
            },
        },
        "required": ["content", "original_source", "source_type"],
    },
)
async def save_transcript(args: dict[str, Any]) -> dict[str, Any]:
    """
    Save a transcription to the transcript library.

    This tool persists raw transcription content to ./data/transcripts/ and
    registers it in the storage system. Returns a transcript ID for future
    reference, enabling lazy loading and context optimization.

    Args:
        args: Dictionary containing:
            - content: The transcription text (required)
            - original_source: YouTube URL or file path (required)
            - source_type: "youtube", "upload", or "local" (required)
            - session_id: Optional session ID for linking
            - custom_filename: Optional custom filename

    Returns:
        Structured response with transcript ID and metadata.
    """
    content = args.get("content")
    original_source = args.get("original_source")
    source_type = args.get("source_type")
    session_id = args.get("session_id")
    custom_filename = args.get("custom_filename")

    # Validate required parameters
    if not content:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: content parameter is required",
                }
            ]
        }

    if not original_source:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: original_source parameter is required",
                }
            ]
        }

    if source_type not in ("youtube", "upload", "local"):
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: source_type must be 'youtube', 'upload', or 'local'",
                }
            ]
        }

    # Generate or validate filename
    if custom_filename:
        filename = f"{_sanitize_filename(custom_filename)}.txt"
    else:
        filename = _generate_filename(original_source, source_type)

    # Build file path in transcripts directory
    transcripts_dir = Path("data/transcripts")
    file_path = transcripts_dir / filename

    # Handle filename collision
    if file_path.exists():
        timestamp = datetime.now(timezone.utc).strftime("%H%M%S")
        stem = file_path.stem
        filename = f"{stem}_{timestamp}.txt"
        file_path = transcripts_dir / filename

    # Write the file asynchronously
    try:
        file_size, line_count = await asyncio.to_thread(
            _write_transcript_sync, file_path, content
        )

        # Register in storage system
        entry = storage.register_transcript(
            file_path=str(file_path),
            original_source=original_source,
            source_type=source_type,
            session_id=session_id,
        )

        transcript_id = entry["id"]
        char_count = len(content)
        preview = content[:200] + "..." if len(content) > 200 else content

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Transcript saved successfully!\n\n"
                    f"**Transcript ID:** `{transcript_id}`\n"
                    f"**File:** {file_path}\n"
                    f"**Size:** {file_size:,} bytes ({line_count:,} lines, "
                    f"{char_count:,} characters)\n"
                    f"**Source:** {source_type} - {original_source}\n\n"
                    f"**Preview:**\n> {preview}\n\n"
                    f"Use `get_transcript` with ID `{transcript_id}` to retrieve "
                    f"the full content when needed.",
                }
            ]
        }

    except PermissionError:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Permission denied writing to: {file_path}",
                }
            ]
        }
    except OSError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Failed to save transcript - {e}",
                }
            ]
        }


@tool(
    "get_transcript",
    "Retrieve the full content of a previously saved transcript by its ID. "
    "Use this when you need to work with the transcript content (summarize, extract, etc.). "
    "This enables lazy loading - only fetch content when actually needed.",
    {
        "type": "object",
        "properties": {
            "transcript_id": {
                "type": "string",
                "description": "The transcript ID (8-character string) returned by save_transcript.",
            },
        },
        "required": ["transcript_id"],
    },
)
async def get_transcript(args: dict[str, Any]) -> dict[str, Any]:
    """
    Retrieve transcript content by ID.

    This tool fetches the full content of a previously saved transcript,
    enabling lazy loading for context optimization.

    Args:
        args: Dictionary containing:
            - transcript_id: The ID returned by save_transcript (required)

    Returns:
        Structured response with full transcript content and metadata.
    """
    transcript_id = args.get("transcript_id", "").strip()

    if not transcript_id:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: transcript_id parameter is required",
                }
            ]
        }

    # Look up transcript metadata
    metadata = storage.get_transcript(transcript_id)
    if not metadata:
        # Try to list available transcripts
        available = storage.list_transcripts()
        if available:
            ids = ", ".join(f"`{t['id']}`" for t in available[:5])
            hint = f"\n\nAvailable transcripts: {ids}"
        else:
            hint = "\n\nNo transcripts found. Use save_transcript first."

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Transcript not found with ID: {transcript_id}{hint}",
                }
            ]
        }

    # Read the file content
    file_path = Path(metadata["file_path"])
    if not file_path.exists():
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Transcript file not found at: {file_path}\n"
                    f"The file may have been deleted or moved.",
                }
            ]
        }

    try:
        content = await asyncio.to_thread(file_path.read_text, "utf-8")

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"**Transcript ID:** `{transcript_id}`\n"
                    f"**Source:** {metadata['source_type']} - {metadata['original_source']}\n"
                    f"**Created:** {metadata['created_at']}\n\n"
                    f"---\n\n"
                    f"{content}",
                }
            ]
        }

    except OSError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Failed to read transcript file - {e}",
                }
            ]
        }


@tool(
    "list_transcripts",
    "List all saved transcripts in the library with their IDs and metadata. "
    "Use this to show the user what transcripts are available for retrieval.",
    {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of transcripts to return. Default is 10.",
                "default": 10,
            },
        },
    },
)
async def list_transcripts(args: dict[str, Any]) -> dict[str, Any]:
    """
    List available transcripts in the library.

    Args:
        args: Dictionary containing:
            - limit: Maximum number of transcripts to return (optional)

    Returns:
        Structured response with transcript summaries.
    """
    limit = args.get("limit", 10)
    if not isinstance(limit, int) or limit < 1:
        limit = 10

    transcripts = storage.list_transcripts()[:limit]

    if not transcripts:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "No transcripts found in the library.\n\n"
                    "Use `save_transcript` after transcribing a video to add one.",
                }
            ]
        }

    # Format transcript list
    lines = ["**Transcript Library**\n"]
    for t in transcripts:
        source_preview = t["original_source"]
        if len(source_preview) > 50:
            source_preview = source_preview[:47] + "..."

        lines.append(
            f"- `{t['id']}` | {t['source_type']} | {t['filename']}\n"
            f"  Source: {source_preview}\n"
            f"  Created: {t['created_at'][:19]} | Size: {t['file_size']:,} bytes"
        )

    lines.append(f"\n\nShowing {len(transcripts)} transcript(s).")
    lines.append("Use `get_transcript` with an ID to retrieve full content.")

    return {
        "content": [
            {
                "type": "text",
                "text": "\n".join(lines),
            }
        ]
    }
