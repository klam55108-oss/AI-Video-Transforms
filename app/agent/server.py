"""
MCP Server configuration for video transcription tools.

This module provides a pre-configured MCP server that can be used
directly with the Claude Agent SDK.

Available tools:
    - transcribe_video: Transcribe video/audio to text using Whisper
    - write_file: Save arbitrary content to files (summaries, notes, etc.)
    - save_transcript: Save raw transcription to library with ID reference
    - get_transcript: Retrieve transcript content by ID (lazy loading)
    - list_transcripts: List all transcripts in the library

Example usage:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
    from app.agent import video_tools_server

    options = ClaudeAgentOptions(
        mcp_servers={"video-tools": video_tools_server},
        allowed_tools=[
            "mcp__video-tools__transcribe_video",
            "mcp__video-tools__write_file",
            "mcp__video-tools__save_transcript",
            "mcp__video-tools__get_transcript",
            "mcp__video-tools__list_transcripts",
        ],
    )

    async with ClaudeSDKClient(options) as client:
        await client.query("Transcribe the video at /path/to/video.mp4")
        async for msg in client.receive_response():
            print(msg)
"""

from claude_agent_sdk import create_sdk_mcp_server

from .file_tool import write_file
from .transcribe_tool import transcribe_video
from .transcript_storage_tools import get_transcript, list_transcripts, save_transcript

# Create MCP server with video tools
video_tools_server = create_sdk_mcp_server(
    name="video-tools",
    version="1.0.0",
    tools=[
        transcribe_video,
        write_file,
        save_transcript,
        get_transcript,
        list_transcripts,
    ],
)
