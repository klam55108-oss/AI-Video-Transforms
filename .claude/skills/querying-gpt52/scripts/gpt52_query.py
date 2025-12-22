#!/usr/bin/env python3
"""GPT-5.2 Query: General-purpose queries with configurable reasoning effort.

This script sends queries to GPT-5.2 with adjustable reasoning effort levels
for tasks requiring extended thinking and complex analysis.

Usage:
    python gpt52_query.py \
        --prompt "Your question here" \
        --reasoning-effort high \
        --timeout 300 \
        --output-format markdown

Environment:
    OPENAI_API_KEY: Required for OpenAI API access
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
    from client import GPT52Client, GPT52Response, ReasoningEffort  # type: ignore[import-not-found]
    from prompts import GENERAL_QUERY_PROMPT  # type: ignore[import-not-found]
except ImportError as e:
    print(f"ERROR: Failed to import _lib modules: {e}", file=sys.stderr)
    print("Ensure _lib/client.py and _lib/prompts.py exist.", file=sys.stderr)
    sys.exit(2)


async def query_gpt52(
    prompt: str,
    reasoning_effort: str,
    timeout: float,
) -> GPT52Response:
    """Query GPT-5.2 with the given prompt and reasoning effort.

    Args:
        prompt: User query to send to GPT-5.2.
        reasoning_effort: Reasoning level (none/low/medium/high/xhigh).
        timeout: API timeout in seconds.

    Returns:
        GPT52Response with success status and output/error.
    """
    client = GPT52Client()

    # Build full prompt with system context
    full_prompt = f"{GENERAL_QUERY_PROMPT}\n\n---\n\n**User Query:**\n\n{prompt}"

    # Convert string to ReasoningEffort enum
    effort = ReasoningEffort(reasoning_effort)

    return await client.query(full_prompt, reasoning_effort=effort, timeout=timeout)


def format_markdown(response: GPT52Response) -> str:
    """Format GPT52Response as markdown output.

    Args:
        response: The GPT-5.2 response object.

    Returns:
        Formatted markdown string.
    """
    if response.success:
        return response.output
    else:
        return f"""# Query Failed

**Error:** {response.error}
"""


def format_json(response: GPT52Response) -> str:
    """Format GPT52Response as JSON output.

    Args:
        response: The GPT-5.2 response object.

    Returns:
        JSON string with structured response data.
    """
    result = {
        "success": response.success,
        "output": response.output if response.success else None,
        "error": response.error if not response.success else None,
        "model": response.model,
        "output_tokens": response.output_tokens,
        "reasoning_tokens": response.reasoning_tokens,
    }
    return json.dumps(result, indent=2)


async def main() -> None:
    """Main entry point for the GPT-5.2 query script."""
    parser = argparse.ArgumentParser(
        description="GPT-5.2 Query: General-purpose queries with configurable reasoning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Query to send to GPT-5.2",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["none", "low", "medium", "high", "xhigh"],
        default="high",
        help="Reasoning effort level (default: high)",
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

    print(f"Querying GPT-5.2 (reasoning: {args.reasoning_effort})...", file=sys.stderr)

    try:
        result = await query_gpt52(
            prompt=args.prompt,
            reasoning_effort=args.reasoning_effort,
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
