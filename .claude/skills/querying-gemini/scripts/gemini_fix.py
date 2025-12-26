#!/usr/bin/env python3
"""Gemini 3 Flash Fix: Root-cause bug fixing (NOT monkey patches).

This script analyzes issues and provides root-level fixes by identifying
true causes and addressing architectural flaws.

Usage:
    python gemini_fix.py \
        --target "app/api/endpoints.py" \
        --issues "TypeError: 'NoneType' object is not subscriptable on line 45" \
        --fix-scope root_cause \
        --timeout 600 \
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
    from prompts import FIXER_PROMPT  # type: ignore[import-not-found]
except ImportError as e:
    print(f"ERROR: Failed to import _lib modules: {e}", file=sys.stderr)
    print("Ensure _lib/client.py and _lib/prompts.py exist.", file=sys.stderr)
    sys.exit(2)

# File collection constants (same as analyze)
MAX_FILE_SIZE = 500 * 1024  # 500KB per file
MAX_TOTAL_SIZE = 2 * 1024 * 1024  # 2MB total
ALLOWED_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".sh",
    ".bash", ".zsh", ".sql", ".md", ".json", ".yaml", ".yml", ".toml",
    ".xml", ".html", ".css", ".scss", ".vue", ".svelte", ".astro",
}
EXCLUDED_DIRS = {"__pycache__", "node_modules", ".git", ".venv", "venv", "dist", "build"}
BLOCKED_PATHS = {"/etc", "/usr", "/bin", "/sbin", "/var", "/root"}


def collect_files(target: Path, project_root: Path) -> list[tuple[Path, str]]:
    """Collect files from target path respecting size and security limits."""
    files: list[tuple[Path, str]] = []
    total_size = 0

    # Security check
    try:
        resolved = target.resolve()
        for blocked in BLOCKED_PATHS:
            if str(resolved).startswith(blocked):
                print(f"WARNING: Blocked system path: {target}", file=sys.stderr)
                return []
    except Exception:
        pass

    if target.is_file():
        targets = [target]
    elif target.is_dir():
        targets = list(target.rglob("*"))
    else:
        print(f"WARNING: Target not found: {target}", file=sys.stderr)
        return []

    for path in targets:
        if not path.is_file():
            continue

        if any(excluded in path.parts for excluded in EXCLUDED_DIRS):
            continue

        if path.name == ".env" or path.name.startswith(".env."):
            continue

        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue

        try:
            size = path.stat().st_size
            if size > MAX_FILE_SIZE:
                print(f"WARNING: Skipping large file ({size} bytes): {path}", file=sys.stderr)
                continue

            if total_size + size > MAX_TOTAL_SIZE:
                print(f"WARNING: Total size limit reached, skipping: {path}", file=sys.stderr)
                continue

            content = path.read_text(encoding="utf-8", errors="replace")
            rel_path = path.relative_to(project_root) if project_root in path.parents or project_root == path.parent else path
            files.append((rel_path, content))
            total_size += size

        except Exception as e:
            print(f"WARNING: Could not read {path}: {e}", file=sys.stderr)

    return files


def build_fix_prompt(
    files: list[tuple[Path, str]],
    issues: str,
    fix_scope: str,
) -> str:
    """Build the fix prompt with collected files and issue description.

    Args:
        files: List of (path, content) tuples.
        issues: Detailed description of the issues to fix.
        fix_scope: Fix approach (root_cause/minimal/comprehensive).

    Returns:
        Complete prompt string for Gemini.
    """
    # Build file content section
    file_sections = []
    for path, content in files:
        file_sections.append(f"### File: `{path}`\n\n```{path.suffix.lstrip('.')}\n{content}\n```")

    files_content = "\n\n".join(file_sections)

    # Build scope instruction
    scope_instructions = {
        "root_cause": "Identify and fix the TRUE root cause. Do not apply symptom-masking workarounds.",
        "minimal": "Apply the smallest possible change that fixes the issue while preserving all other behavior.",
        "comprehensive": "Fix the issue AND refactor related code to prevent similar issues in the future.",
    }
    scope_instruction = scope_instructions.get(fix_scope, scope_instructions["root_cause"])

    return f"""{FIXER_PROMPT}

---

## Fix Configuration

**Fix Scope:** {scope_instruction}
**Files Provided:** {len(files)} files

---

## Issue Description

{issues}

---

## Code Context

{files_content}
"""


async def fix_code(
    target: str,
    issues: str,
    fix_scope: str,
    timeout: float,
) -> GeminiResponse:
    """Fix code issues using Gemini 3 Flash.

    Args:
        target: File or directory path containing the issue.
        issues: Detailed description of the issues.
        fix_scope: Fix approach (root_cause/minimal/comprehensive).
        timeout: API timeout in seconds.

    Returns:
        GeminiResponse with fix recommendations.
    """
    # Resolve paths
    project_root = Path.cwd()
    target_path = Path(target)
    if not target_path.is_absolute():
        target_path = project_root / target_path

    # Collect files
    files = collect_files(target_path, project_root)
    if not files:
        return GeminiResponse(
            success=False,
            output="",
            error=f"No analyzable files found in: {target}",
        )

    print(f"Collected {len(files)} files for analysis", file=sys.stderr)

    # Build prompt
    prompt = build_fix_prompt(files, issues, fix_scope)

    # Execute query with high thinking for root cause analysis
    client = GeminiClient()
    return await client.query(prompt, thinking_level=ThinkingLevel.HIGH, timeout=timeout)


def format_markdown(response: GeminiResponse) -> str:
    """Format GeminiResponse as markdown output."""
    if response.success:
        return response.output
    else:
        return f"""# Fix Analysis Failed

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
    """Main entry point for the Gemini 3 Flash fix script."""
    parser = argparse.ArgumentParser(
        description="Gemini 3 Flash Fix: Root-cause bug fixing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--target",
        required=True,
        help="File or directory containing the issue",
    )
    parser.add_argument(
        "--issues",
        required=True,
        help="Detailed description of the issues (include error messages, stack traces)",
    )
    parser.add_argument(
        "--fix-scope",
        choices=["root_cause", "minimal", "comprehensive"],
        default="root_cause",
        help="Fix approach (default: root_cause)",
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

    print(f"Analyzing issues with Gemini 3 Flash (scope: {args.fix_scope})...", file=sys.stderr)
    print(f"Target: {args.target}", file=sys.stderr)

    try:
        result = await fix_code(
            target=args.target,
            issues=args.issues,
            fix_scope=args.fix_scope,
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
