"""
Pydantic models for structured agent outputs.

This module defines schemas for Claude Agent SDK structured output format,
enabling type-safe parsing of agent responses.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TranscriptionResult(BaseModel):
    """
    Structured output for video transcription operations.

    Attributes:
        success: Whether transcription completed successfully
        transcription: Full transcription text (if successful)
        source: Original source identifier (URL or filename)
        source_type: Type of source
        segments_processed: Number of audio segments transcribed
        language_detected: Detected language code (e.g., "en", "es")
        error: Error message (if failed)
    """

    success: bool
    transcription: str | None = None
    source: str
    source_type: Literal["youtube", "local", "upload"]
    segments_processed: int = 0
    language_detected: str | None = None
    error: str | None = None


class TranscriptSummary(BaseModel):
    """
    Structured output for transcript summarization.

    Attributes:
        title: Generated title for the content
        summary: Brief summary of the transcript
        key_points: List of main points or takeaways
        topics: Topic tags extracted from content
        word_count: Approximate word count
    """

    title: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    word_count: int = 0


class AgentResponse(BaseModel):
    """
    Top-level structured response from the agent.

    This is the primary schema used for output_format in ClaudeAgentOptions.

    Attributes:
        operation: Type of operation performed
        message: Natural language response to user
        data: Optional structured data specific to the operation
        suggestions: Suggested next actions for the user
    """

    operation: Literal["transcribe", "summarize", "save", "list", "error", "chat"] = (
        "chat"
    )
    message: str
    data: dict | None = None
    suggestions: list[str] = Field(default_factory=list)


def get_output_schema() -> dict:
    """
    Get JSON schema for AgentResponse to use with ClaudeAgentOptions.

    Returns:
        JSON Schema dict compatible with output_format parameter
    """
    return AgentResponse.model_json_schema()
