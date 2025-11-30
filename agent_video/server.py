"""
MCP Server configuration for video transcription tools.

This module provides a pre-configured MCP server that can be used
directly with the Claude Agent SDK.

Example usage:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
    from agent_video import video_tools_server

    options = ClaudeAgentOptions(
        mcp_servers={"video-tools": video_tools_server},
        allowed_tools=[
            "mcp__video-tools__transcribe_video",
            "mcp__video-tools__write_file",
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

# Create MCP server with video tools
video_tools_server = create_sdk_mcp_server(
    name="video-tools",
    version="1.0.0",
    tools=[transcribe_video, write_file],
)
