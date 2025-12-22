#!/usr/bin/env python3
"""GPT-5.2 Analyze: Deep code analysis with P0-P3 prioritized findings.

This script collects code files and performs comprehensive analysis with
GPT-5.2, producing prioritized reports across multiple dimensions.

Usage:
    python gpt52_analyze.py \
        --target "app/core/" \
        --focus-areas "security,performance" \
        --analysis-type comprehensive \
        --timeout 600 \
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
    from client import GPT52Client, GPT52Response  # type: ignore[import-not-found]
    from files import collect_files, format_files_for_prompt  # type: ignore[import-not-found]
    from prompts import ANALYZER_PROMPT  # type: ignore[import-not-found]
except ImportError as e:
    print(f"ERROR: Failed to import _lib modules: {e}", file=sys.stderr)
    print(
        "Ensure _lib/client.py, _lib/files.py, and _lib/prompts.py exist.",
        file=sys.stderr,
    )
    sys.exit(2)


async def analyze_code(
    target: str,
    focus_areas: str,
    analysis_type: str,
    timeout: float,
) -> GPT52Response:
    """Analyze code files using GPT-5.2.

    Args:
        target: Path to file or directory to analyze.
        focus_areas: Comma-separated focus areas (or 'all').
        analysis_type: Analysis depth (quick/comprehensive/deep).
        timeout: API timeout in seconds.

    Returns:
        GPT52Response with success status and output/error.
    """
    client = GPT52Client()

    # Resolve target path relative to project root (4 levels up from scripts/)
    # scripts → querying-gpt52 → skills → .claude → agent-video-to-data
    project_root = SCRIPT_DIR.resolve().parents[3]
    target_path = Path(target)
    if not target_path.is_absolute():
        target_path = project_root / target_path

    if not target_path.exists():
        return GPT52Response(
            success=False,
            output="",
            error=f"Target path does not exist: {target} (resolved: {target_path})",
        )

    # Collect files
    try:
        files = collect_files(target_path, project_root)
        if not files:
            return GPT52Response(
                success=False,
                output="",
                error=f"No files found to analyze at {target_path} (may be filtered by security rules)",
            )

        formatted_files = format_files_for_prompt(files)
    except Exception as e:
        return GPT52Response(
            success=False,
            output="",
            error=f"Failed to collect files: {e}",
        )

    # Build analysis prompt
    focus_text = focus_areas if focus_areas != "all" else "all dimensions"
    depth_map = {
        "quick": "Provide quick high-level assessment focusing on critical issues only.",
        "comprehensive": "Provide comprehensive analysis across all relevant dimensions.",
        "deep": "Provide deep analysis with detailed examination of patterns and root causes.",
    }
    depth_instruction = depth_map.get(analysis_type, depth_map["comprehensive"])

    full_prompt = f"""{ANALYZER_PROMPT}

---

**Analysis Configuration:**

- **Target**: {target}
- **Focus Areas**: {focus_text}
- **Analysis Type**: {analysis_type}
- **Instruction**: {depth_instruction}

---

**Code Files:**

{formatted_files}

---

**Your Task:**

Analyze the provided code files and produce a structured report with P0-P3 prioritized findings. Focus on {focus_text}.
"""

    # Use high reasoning effort for analysis
    from client import ReasoningEffort  # type: ignore[import-not-found]

    return await client.query(
        full_prompt, reasoning_effort=ReasoningEffort.HIGH, timeout=timeout
    )


def format_markdown(response: GPT52Response, target: str) -> str:
    """Format GPT52Response as markdown output.

    Args:
        response: The GPT-5.2 response object.
        target: Target path that was analyzed.

    Returns:
        Formatted markdown string.
    """
    if response.success:
        return f"""# Code Analysis Report: {target}

{response.output}

---

**Analysis Metadata:**
- Model: {response.model}
- Output Tokens: {response.output_tokens:,}
- Reasoning Tokens: {response.reasoning_tokens:,}
"""
    else:
        return f"""# Analysis Failed: {target}

**Error:** {response.error}
"""


def format_json(response: GPT52Response, target: str) -> str:
    """Format GPT52Response as JSON output.

    Args:
        response: The GPT-5.2 response object.
        target: Target path that was analyzed.

    Returns:
        JSON string with structured response data.
    """
    result = {
        "target": target,
        "success": response.success,
        "output": response.output if response.success else None,
        "error": response.error if not response.success else None,
        "metadata": {
            "model": response.model,
            "output_tokens": response.output_tokens,
            "reasoning_tokens": response.reasoning_tokens,
        },
    }
    return json.dumps(result, indent=2)


async def main() -> None:
    """Main entry point for the GPT-5.2 analyze script."""
    parser = argparse.ArgumentParser(
        description="GPT-5.2 Analyze: Deep code analysis with P0-P3 prioritization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Path to file or directory to analyze",
    )
    parser.add_argument(
        "--focus-areas",
        default="all",
        help="Comma-separated focus areas (e.g., 'security,performance') or 'all' (default: all)",
    )
    parser.add_argument(
        "--analysis-type",
        choices=["quick", "comprehensive", "deep"],
        default="comprehensive",
        help="Analysis depth (default: comprehensive)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="API timeout in seconds (default: 600)",
    )
    parser.add_argument(
        "--output-format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )

    args = parser.parse_args()

    print(f"Analyzing {args.target} ({args.analysis_type})...", file=sys.stderr)

    try:
        result = await analyze_code(
            target=args.target,
            focus_areas=args.focus_areas,
            analysis_type=args.analysis_type,
            timeout=args.timeout,
        )

        if result.success:
            if args.output_format == "json":
                print(format_json(result, args.target))
            else:
                print(format_markdown(result, args.target))
            sys.exit(0)
        else:
            print(f"ERROR: {result.error}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
