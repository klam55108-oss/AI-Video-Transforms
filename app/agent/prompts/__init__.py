"""
Prompts Package - Versioned prompt management for the video agent.

This package provides a centralized system for managing and versioning
prompts used throughout the application.

Usage:
    # Get a prompt by name (returns latest version)
    from app.agent.prompts import get_prompt
    prompt = get_prompt("video_transcription_agent")

    # Get specific version
    prompt = get_prompt("video_transcription_agent", version="1.0.0")

    # Get just the content string
    from app.agent.prompts import get_prompt_content
    content = get_prompt_content("video_transcription_agent")

    # Import specific prompts directly
    from app.agent.prompts import VIDEO_TRANSCRIPTION_PROMPT, SYSTEM_PROMPT

    # Register a new prompt
    from app.agent.prompts import register_prompt
    register_prompt(
        name="my_prompt",
        version="1.0.0",
        content="Your prompt here",
        description="Description of this version"
    )
"""

from __future__ import annotations

# Import registry functions and types
from .registry import (
    PromptRegistry,
    PromptVersion,
    get_prompt,
    get_prompt_content,
    list_prompt_versions,
    list_prompts,
    register_prompt,
)

# Import specific prompts - this also registers them via side effects
from .video_transcription import (
    DEFAULT_TRANSCRIPTION_PROMPT,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_STRUCTURED,
    TRANSCRIPTION_PROMPT_TEMPLATES,
    VIDEO_TRANSCRIPTION_PROMPT,
)

__all__ = [
    # Registry types
    "PromptRegistry",
    "PromptVersion",
    # Registry functions
    "register_prompt",
    "get_prompt",
    "get_prompt_content",
    "list_prompts",
    "list_prompt_versions",
    # Specific prompts
    "VIDEO_TRANSCRIPTION_PROMPT",
    "SYSTEM_PROMPT",
    "SYSTEM_PROMPT_STRUCTURED",  # Version 2.0.0 with structured output support
    # Transcription prompts
    "DEFAULT_TRANSCRIPTION_PROMPT",
    "TRANSCRIPTION_PROMPT_TEMPLATES",
]
