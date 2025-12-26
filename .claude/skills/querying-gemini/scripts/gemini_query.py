#!/usr/bin/env python3
"""Gemini 3 Flash Query: General-purpose queries with configurable thinking levels.

This script sends queries to Gemini 3 Flash with adjustable thinking levels
for tasks requiring extended reasoning and complex analysis.

Usage:
    python gemini_query.py \
        --prompt "Your question here" \
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
    from prompts import GENERAL_QUERY_PROMPT  # type: ignore[import-not-found]
except ImportError as e:
    print(f"ERROR: Failed to import _lib modules: {e}", file=sys.stderr)
    print("Ensure _lib/client.py and _lib/prompts.py exist.", file=sys.stderr)
    sys.exit(2)


async def query_gemini(
    prompt: str,
    thinking_level: str,
    timeout: float,
) -> GeminiResponse:
    """Query Gemini 3 Flash with the given prompt and thinking level.

    Args:
        prompt: User query to send to Gemini 3 Flash.
        thinking_level: Thinking level (minimal/low/medium/high).
        timeout: API timeout in seconds.

    Returns:
        GeminiResponse with success status and output/error.
    """
    client = GeminiClient()

    # Build full prompt with system context
    full_prompt = f"{GENERAL_QUERY_PROMPT}\n\n---\n\n**User Query:**\n\n{prompt}"

    # Convert string to ThinkingLevel enum
    level = ThinkingLevel(thinking_level)

    return await client.query(full_prompt, thinking_level=level, timeout=timeout)


def format_markdown(response: GeminiResponse) -> str:
    """Format GeminiResponse as markdown output.

    Args:
        response: The Gemini 3 Flash response object.

    Returns:
        Formatted markdown string.
    """
    if response.success:
        return response.output
    else:
        return f"""# Query Failed

**Error:** {response.error}
"""


def format_json(response: GeminiResponse) -> str:
    """Format GeminiResponse as JSON output.

    Args:
        response: The Gemini 3 Flash response object.

    Returns:
        JSON string with structured response data.
    """
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
    """Main entry point for the Gemini 3 Flash query script."""
    parser = argparse.ArgumentParser(
        description="Gemini 3 Flash Query: General-purpose queries with configurable thinking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Query to send to Gemini 3 Flash",
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

    print(f"Querying Gemini 3 Flash (thinking: {args.thinking_level})...", file=sys.stderr)

    try:
        result = await query_gemini(
            prompt=args.prompt,
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
