#!/usr/bin/env python3
"""Gemini 3 Flash Analyze: Comprehensive code analysis with structured reporting.

This script performs deep, multi-dimensional code analysis from single files
to complete projects, outputting structured reports with P0-P3 prioritization.

Usage:
    python gemini_analyze.py \
        --target "app/core/" \
        --focus-areas "security,performance" \
        --analysis-type comprehensive \
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
    from prompts import ANALYZER_PROMPT  # type: ignore[import-not-found]
except ImportError as e:
    print(f"ERROR: Failed to import _lib modules: {e}", file=sys.stderr)
    print("Ensure _lib/client.py and _lib/prompts.py exist.", file=sys.stderr)
    sys.exit(2)

# File collection constants
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
    """Collect files from target path respecting size and security limits.

    Args:
        target: File or directory to analyze.
        project_root: Project root for relative path calculation.

    Returns:
        List of (path, content) tuples.
    """
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

        # Skip excluded directories
        if any(excluded in path.parts for excluded in EXCLUDED_DIRS):
            continue

        # Skip .env files (security)
        if path.name == ".env" or path.name.startswith(".env."):
            continue

        # Check extension
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue

        # Check file size
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


def build_analysis_prompt(
    files: list[tuple[Path, str]],
    focus_areas: list[str],
    analysis_type: str,
) -> str:
    """Build the analysis prompt with collected files.

    Args:
        files: List of (path, content) tuples.
        focus_areas: Areas to focus analysis on.
        analysis_type: Type of analysis (quick/comprehensive/deep).

    Returns:
        Complete prompt string for Gemini.
    """
    # Build file content section
    file_sections = []
    for path, content in files:
        file_sections.append(f"### File: `{path}`\n\n```{path.suffix.lstrip('.')}\n{content}\n```")

    files_content = "\n\n".join(file_sections)

    # Build focus instruction
    if "all" in focus_areas:
        focus_instruction = "Analyze all dimensions thoroughly."
    else:
        focus_instruction = f"Focus particularly on: {', '.join(focus_areas)}."

    # Build depth instruction
    depth_instructions = {
        "quick": "Provide a rapid assessment focusing on critical issues only.",
        "comprehensive": "Perform a balanced analysis covering all major concerns.",
        "deep": "Conduct an exhaustive analysis with detailed findings for each dimension.",
    }
    depth_instruction = depth_instructions.get(analysis_type, depth_instructions["comprehensive"])

    return f"""{ANALYZER_PROMPT}

---

## Analysis Configuration

**Focus Areas:** {focus_instruction}
**Analysis Depth:** {depth_instruction}
**Files to Analyze:** {len(files)} files

---

## Code to Analyze

{files_content}
"""


async def analyze_code(
    target: str,
    focus_areas: list[str],
    analysis_type: str,
    timeout: float,
) -> GeminiResponse:
    """Analyze code using Gemini 3 Flash.

    Args:
        target: File or directory path to analyze.
        focus_areas: List of areas to focus on.
        analysis_type: Type of analysis (quick/comprehensive/deep).
        timeout: API timeout in seconds.

    Returns:
        GeminiResponse with analysis results.
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
    prompt = build_analysis_prompt(files, focus_areas, analysis_type)

    # Determine thinking level based on analysis type
    thinking_map = {
        "quick": ThinkingLevel.LOW,
        "comprehensive": ThinkingLevel.HIGH,
        "deep": ThinkingLevel.HIGH,
    }
    thinking_level = thinking_map.get(analysis_type, ThinkingLevel.HIGH)

    # Execute query
    client = GeminiClient()
    return await client.query(prompt, thinking_level=thinking_level, timeout=timeout)


def format_markdown(response: GeminiResponse) -> str:
    """Format GeminiResponse as markdown output."""
    if response.success:
        return response.output
    else:
        return f"""# Analysis Failed

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
    """Main entry point for the Gemini 3 Flash analyze script."""
    parser = argparse.ArgumentParser(
        description="Gemini 3 Flash Analyze: Comprehensive code analysis with P0-P3 prioritization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--target",
        required=True,
        help="File or directory to analyze",
    )
    parser.add_argument(
        "--focus-areas",
        default="all",
        help="Comma-separated focus areas: security,performance,architecture,testing,quality,all (default: all)",
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

    # Parse focus areas
    focus_areas = [area.strip().lower() for area in args.focus_areas.split(",")]

    print(f"Analyzing with Gemini 3 Flash ({args.analysis_type})...", file=sys.stderr)
    print(f"Target: {args.target}", file=sys.stderr)
    print(f"Focus: {', '.join(focus_areas)}", file=sys.stderr)

    try:
        result = await analyze_code(
            target=args.target,
            focus_areas=focus_areas,
            analysis_type=args.analysis_type,
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
