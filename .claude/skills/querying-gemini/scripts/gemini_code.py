#!/usr/bin/env python3
"""Gemini 3 Flash Code: High-quality code generation with best practices.

This script generates production-ready code based on requirements,
leveraging Gemini 3 Flash's superior coding capabilities.

Usage:
    python gemini_code.py \
        --request "Implement a rate limiter using token bucket algorithm" \
        --language python \
        --context "FastAPI application with async support" \
        --thinking-level high \
        --timeout 300 \
        --output-format markdown

Environment:
    GEMINI_API_KEY or GOOGLE_API_KEY: Required for Google Gen AI API access
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add _lib to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "_lib"))

try:
    from client import GeminiClient, GeminiResponse, ThinkingLevel  # type: ignore[import-not-found]
    from prompts import CODE_GENERATOR_PROMPT  # type: ignore[import-not-found]
except ImportError as e:
    print(f"ERROR: Failed to import _lib modules: {e}", file=sys.stderr)
    print("Ensure _lib/client.py and _lib/prompts.py exist.", file=sys.stderr)
    sys.exit(2)


def build_code_prompt(
    request: str,
    language: str | None,
    context: str | None,
) -> str:
    """Build the code generation prompt.

    Args:
        request: Description of the code to generate.
        language: Optional programming language hint.
        context: Optional additional context about requirements.

    Returns:
        Complete prompt string for Gemini.
    """
    sections = [CODE_GENERATOR_PROMPT, "\n---\n"]

    # Add language hint if provided
    if language:
        sections.append(f"**Target Language:** {language}\n")

    # Add context if provided
    if context:
        sections.append(f"**Context:** {context}\n")

    # Add the main request
    sections.append(f"\n## Code Request\n\n{request}")

    return "".join(sections)


async def generate_code(
    request: str,
    language: str | None,
    context: str | None,
    thinking_level: str,
    timeout: float,
) -> GeminiResponse:
    """Generate code using Gemini 3 Flash.

    Args:
        request: Description of the code to generate.
        language: Optional programming language hint.
        context: Optional additional context.
        thinking_level: Thinking level (minimal/low/medium/high).
        timeout: API timeout in seconds.

    Returns:
        GeminiResponse with generated code.
    """
    client = GeminiClient()

    # Build prompt
    prompt = build_code_prompt(request, language, context)

    # Convert string to ThinkingLevel enum
    level = ThinkingLevel(thinking_level)

    return await client.query(prompt, thinking_level=level, timeout=timeout)


def format_markdown(response: GeminiResponse) -> str:
    """Format GeminiResponse as markdown output."""
    if response.success:
        return response.output
    else:
        return f"""# Code Generation Failed

**Error:** {response.error}
"""


def format_json(response: GeminiResponse) -> str:
    """Format GeminiResponse as JSON output."""
    result = {
        "success": response.success,
        "output": response.output if response.success else None,
        "error": response.error if not response.success else None,
        "model": response.model,
        "output_tokens": response.output_tokens,
        "prompt_tokens": response.prompt_tokens,
    }
    return json.dumps(result, indent=2)


async def main() -> None:
    """Main entry point for the Gemini 3 Flash code script."""
    parser = argparse.ArgumentParser(
        description="Gemini 3 Flash Code: High-quality code generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--request",
        required=True,
        help="Description of the code to generate",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Target programming language (e.g., python, javascript, go)",
    )
    parser.add_argument(
        "--context",
        default=None,
        help="Additional context about the codebase or requirements",
    )
    parser.add_argument(
        "--thinking-level",
        choices=["minimal", "low", "medium", "high"],
        default="high",
        help="Thinking level (default: high)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="API timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "--output-format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )

    args = parser.parse_args()

    print(f"Generating code with Gemini 3 Flash (thinking: {args.thinking_level})...", file=sys.stderr)
    if args.language:
        print(f"Language: {args.language}", file=sys.stderr)

    try:
        result = await generate_code(
            request=args.request,
            language=args.language,
            context=args.context,
            thinking_level=args.thinking_level,
            timeout=args.timeout,
        )

        if result.success:
            if args.output_format == "json":
                print(format_json(result))
            else:
                print(format_markdown(result))
            sys.exit(0)
        else:
            print(f"ERROR: {result.error}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
