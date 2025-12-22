#!/usr/bin/env python3
"""GPT-5.2 Fix: Root-cause bug fixing with comprehensive analysis.

This script collects code files and identifies root causes of bugs/issues,
providing actionable fixes that address underlying problems (not symptoms).

Usage:
    python gpt52_fix.py \
        --target "app/api/endpoints.py" \
        --issues "Error description with stack trace" \
        --fix-scope root_cause \
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
    from client import GPT52Client, GPT52Response, ReasoningEffort  # type: ignore[import-not-found]
    from files import collect_files, format_files_for_prompt  # type: ignore[import-not-found]
    from prompts import FIXER_PROMPT  # type: ignore[import-not-found]
except ImportError as e:
    print(f"ERROR: Failed to import _lib modules: {e}", file=sys.stderr)
    print(
        "Ensure _lib/client.py, _lib/files.py, and _lib/prompts.py exist.",
        file=sys.stderr,
    )
    sys.exit(2)


async def fix_bug(
    target: str,
    issues: str,
    fix_scope: str,
    timeout: float,
) -> GPT52Response:
    """Analyze and fix bugs in code using GPT-5.2.

    Args:
        target: Path to file or directory with the bug.
        issues: Description of the issues/errors to fix.
        fix_scope: Scope of fix (root_cause/minimal/comprehensive).
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

    # Build fix prompt
    scope_map = {
        "root_cause": "Identify and fix the ROOT CAUSE of the issue. NO MONKEY PATCHES.",
        "minimal": "Provide minimal fix that addresses the immediate issue with lowest risk.",
        "comprehensive": "Provide comprehensive fix that addresses the issue and improves robustness.",
    }
    scope_instruction = scope_map.get(fix_scope, scope_map["root_cause"])

    full_prompt = f"""{FIXER_PROMPT}

---

**Fix Configuration:**

- **Target**: {target}
- **Fix Scope**: {fix_scope}
- **Instruction**: {scope_instruction}

---

**Reported Issues:**

{issues}

---

**Code Files:**

{formatted_files}

---

**Your Task:**

Analyze the reported issues and the provided code files. Identify the ROOT CAUSE of the problem and provide a fix that addresses the underlying issue, not just the symptoms. {scope_instruction}
"""

    # Use high reasoning effort for debugging
    return await client.query(
        full_prompt, reasoning_effort=ReasoningEffort.HIGH, timeout=timeout
    )


def format_markdown(response: GPT52Response, target: str, issues: str) -> str:
    """Format GPT52Response as markdown output.

    Args:
        response: The GPT-5.2 response object.
        target: Target path that was analyzed.
        issues: Description of the issues.

    Returns:
        Formatted markdown string.
    """
    if response.success:
        return f"""# Bug Fix Report: {target}

## Issues

{issues}

---

## Analysis & Fix

{response.output}

---

**Fix Metadata:**
- Model: {response.model}
- Output Tokens: {response.output_tokens:,}
- Reasoning Tokens: {response.reasoning_tokens:,}
"""
    else:
        return f"""# Fix Failed: {target}

**Error:** {response.error}

**Issues:**
{issues}
"""


def format_json(response: GPT52Response, target: str, issues: str) -> str:
    """Format GPT52Response as JSON output.

    Args:
        response: The GPT-5.2 response object.
        target: Target path that was analyzed.
        issues: Description of the issues.

    Returns:
        JSON string with structured response data.
    """
    result = {
        "target": target,
        "issues": issues,
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
    """Main entry point for the GPT-5.2 fix script."""
    parser = argparse.ArgumentParser(
        description="GPT-5.2 Fix: Root-cause bug fixing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Path to file or directory with the bug",
    )
    parser.add_argument(
        "--issues",
        required=True,
        help="Description of issues/errors to fix (include stack traces)",
    )
    parser.add_argument(
        "--fix-scope",
        choices=["root_cause", "minimal", "comprehensive"],
        default="root_cause",
        help="Scope of fix (default: root_cause)",
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

    print(f"Analyzing bug in {args.target} ({args.fix_scope})...", file=sys.stderr)

    try:
        result = await fix_bug(
            target=args.target,
            issues=args.issues,
            fix_scope=args.fix_scope,
            timeout=args.timeout,
        )

        if result.success:
            if args.output_format == "json":
                print(format_json(result, args.target, args.issues))
            else:
                print(format_markdown(result, args.target, args.issues))
            sys.exit(0)
        else:
            print(f"ERROR: {result.error}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
