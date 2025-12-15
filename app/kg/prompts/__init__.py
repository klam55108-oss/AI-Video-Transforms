"""
KG Prompts Package - System prompts for Knowledge Graph agents.

This package provides the system prompts used by the KG Bootstrap and Extraction
agents. Each prompt is designed to guide Claude through specific knowledge graph
operations.

Available Prompts:
    BOOTSTRAP_SYSTEM_PROMPT: Guides domain analysis and profile creation from
        the first video transcript. Produces thing types, connection types,
        seed entities, and extraction context.

Available Functions:
    generate_extraction_prompt: Creates dynamic extraction prompts from a
        DomainProfile. Adapts to the specific domain learned during bootstrap.

Usage:
    from app.kg.prompts import BOOTSTRAP_SYSTEM_PROMPT, generate_extraction_prompt

    # Bootstrap: Use static system prompt
    options = ClaudeAgentOptions(
        system_prompt=BOOTSTRAP_SYSTEM_PROMPT,
        mcp_servers={"kg-bootstrap": bootstrap_server},
        allowed_tools=BOOTSTRAP_TOOL_NAMES,
    )

    # Extraction: Use dynamic prompt from profile
    prompt = generate_extraction_prompt(
        profile=project.domain_profile,
        title="Video Title",
        content=transcript_text,
    )
"""

from __future__ import annotations

from .bootstrap_prompt import BOOTSTRAP_SYSTEM_PROMPT
from .templates import generate_extraction_prompt

__all__ = [
    "BOOTSTRAP_SYSTEM_PROMPT",
    "generate_extraction_prompt",
]
