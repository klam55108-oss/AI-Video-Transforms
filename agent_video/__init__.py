"""
Agent Video Tools - Video transcription tools for Claude Agent SDK.

This package provides tools for transcribing video content using
OpenAI's Whisper model, designed to work with the Claude Agent SDK.

Usage with Claude Agent SDK:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
    from agent_video import video_tools_server

    options = ClaudeAgentOptions(
        mcp_servers={"video-tools": video_tools_server},
        allowed_tools=["mcp__video-tools__transcribe_video"],
    )

    async with ClaudeSDKClient(options) as client:
        await client.query("Transcribe the video at /path/to/video.mp4")
        async for msg in client.receive_response():
            print(msg)

Environment Variables:
    OPENAI_API_KEY: Required. Your OpenAI API key for Whisper transcription.

Optional Dependencies:
    yt-dlp: Required for YouTube URL support. Install with: pip install yt-dlp
"""

from .server import video_tools_server
from .transcribe_tool import transcribe_video

__all__ = [
    "transcribe_video",
    "video_tools_server",
]

__version__ = "1.0.0"
