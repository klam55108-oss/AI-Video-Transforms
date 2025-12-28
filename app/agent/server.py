"""
MCP Server configuration for video transcription and knowledge graph tools.

This module provides a pre-configured MCP server that can be used
directly with the Claude Agent SDK.

Available tools:
    Transcription:
    - transcribe_video: Transcribe video/audio to text using Whisper
    - write_file: Save arbitrary content to files (summaries, notes, etc.)
    - save_transcript: Save raw transcription to library with ID reference
    - get_transcript: Retrieve transcript content by ID (lazy loading)
    - list_transcripts: List all transcripts in the library

    Knowledge Graph:
    - extract_to_kg: Extract entities/relationships from transcript into KG
    - list_kg_projects: List all KG projects with stats
    - create_kg_project: Create a new KG project
    - bootstrap_kg_project: Bootstrap project from first transcript
    - get_kg_stats: Get graph statistics by type
    - ask_about_graph: Query the graph for insights

    Entity Resolution:
    - find_duplicate_entities: Scan for potential duplicate entities
    - merge_entities_tool: Merge two entities into one
    - review_pending_merges: Get pending merge candidates for review
    - approve_merge: Approve a pending merge candidate
    - reject_merge: Reject a pending merge candidate
    - compare_entities_semantic: Compare two entities for semantic similarity

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
            "mcp__video-tools__extract_to_kg",
            "mcp__video-tools__list_kg_projects",
            "mcp__video-tools__create_kg_project",
            "mcp__video-tools__bootstrap_kg_project",
            "mcp__video-tools__get_kg_stats",
            "mcp__video-tools__ask_about_graph",
            "mcp__video-tools__find_duplicate_entities",
            "mcp__video-tools__merge_entities_tool",
            "mcp__video-tools__review_pending_merges",
            "mcp__video-tools__approve_merge",
            "mcp__video-tools__reject_merge",
            "mcp__video-tools__compare_entities_semantic",
        ],
    )

    async with ClaudeSDKClient(options) as client:
        await client.query("Transcribe the video at /path/to/video.mp4")
        async for msg in client.receive_response():
            print(msg)
"""

from claude_agent_sdk import create_sdk_mcp_server

from .file_tool import write_file
from .kg_tool import KG_TOOLS
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
        *KG_TOOLS,
    ],
)
