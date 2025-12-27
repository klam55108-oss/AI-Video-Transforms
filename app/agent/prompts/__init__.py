"""
Prompts Package - Versioned prompt management for CognivAgent.

This package provides a centralized system for managing prompts.

Usage:
    # Import the system prompt directly (recommended)
    from app.agent.prompts import SYSTEM_PROMPT

    # Get a prompt by name via registry
    from app.agent.prompts import get_prompt
    prompt = get_prompt("video_transcription_agent")

    # Get just the content string
    from app.agent.prompts import get_prompt_content
    content = get_prompt_content("video_transcription_agent")
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
    # System prompt (main export)
    "SYSTEM_PROMPT",
    "SYSTEM_PROMPT_STRUCTURED",
    # Transcription prompts (for gpt-4o-transcribe)
    "DEFAULT_TRANSCRIPTION_PROMPT",
    "TRANSCRIPTION_PROMPT_TEMPLATES",
]
