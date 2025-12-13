"""
GPT-5.1-Codex-Max MCP Server for Claude Code.

Provides 3 specialized tools leveraging high-reasoning capabilities:
- codex_query: General queries with high reasoning
- codex_analyzer: Comprehensive code/project analysis
- codex_fixer: Root-cause bug fixing (not monkey patches)

Integration with Claude Code:
- Configured in .mcp.json alongside gemini-cli
- Run via: uv run python -m mcp_servers.codex.server
- Claude Code calls these tools through MCP protocol
"""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from .client import ReasoningEffort, get_client
from .prompts import get_analyzer_prompt, get_fixer_prompt, get_general_prompt

mcp = FastMCP(name="codex")

# Project root for file reading
_MODULE_DIR = Path(__file__).parent.resolve()
_PROJECT_ROOT = _MODULE_DIR.parent.parent

# File reading constraints
MAX_FILE_SIZE = 500_000  # 500KB per file
MAX_TOTAL_SIZE = 2_000_000  # 2MB total for analysis
ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".scala",
    ".sh",
    ".bash",
    ".zsh",
    ".sql",
    ".html",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".md",
    ".txt",
    ".env",
    ".gitignore",
    ".dockerfile",
    "Dockerfile",
    ".vue",
    ".svelte",
}


def _is_safe_path(path: Path) -> bool:
    """Check if path is safe to read (not system files)."""
    resolved = path.resolve()
    dangerous_prefixes = ["/etc", "/usr", "/bin", "/sbin", "/var", "/root"]
    path_str = str(resolved)
    return not any(path_str.startswith(prefix) for prefix in dangerous_prefixes)


def _should_include_file(path: Path) -> bool:
    """Check if file should be included in analysis."""
    if path.name.startswith(".") and path.suffix not in {".env", ".gitignore"}:
        return False
    if path.suffix not in ALLOWED_EXTENSIONS and path.name not in ALLOWED_EXTENSIONS:
        return False
    if "__pycache__" in str(path) or "node_modules" in str(path):
        return False
    if ".git" in str(path):
        return False
    return True


def _read_file_safe(path: Path, max_size: int = MAX_FILE_SIZE) -> str | None:
    """Safely read a file with size limits."""
    try:
        if not path.exists() or not path.is_file():
            return None
        if not _is_safe_path(path):
            return None
        if path.stat().st_size > max_size:
            return f"[File too large: {path.stat().st_size} bytes, max {max_size}]"
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[Error reading file: {e}]"


def _collect_files(
    target: str,
    base_path: Path | None = None,
) -> dict[str, str]:
    """
    Collect files from a path (file or directory).

    Returns dict of {relative_path: content}
    """
    base = base_path or _PROJECT_ROOT
    target_path = Path(target)

    # Handle relative paths
    if not target_path.is_absolute():
        target_path = base / target_path

    target_path = target_path.resolve()
    files: dict[str, str] = {}
    total_size = 0

    if target_path.is_file():
        content = _read_file_safe(target_path)
        if content:
            rel_path = str(
                target_path.relative_to(base)
                if target_path.is_relative_to(base)
                else target_path
            )
            files[rel_path] = content
    elif target_path.is_dir():
        for file_path in sorted(target_path.rglob("*")):
            if total_size >= MAX_TOTAL_SIZE:
                files["__truncated__"] = f"[Reached {MAX_TOTAL_SIZE} byte limit]"
                break
            if not file_path.is_file():
                continue
            if not _should_include_file(file_path):
                continue
            content = _read_file_safe(file_path)
            if content:
                rel_path = str(
                    file_path.relative_to(base)
                    if file_path.is_relative_to(base)
                    else file_path
                )
                files[rel_path] = content
                total_size += len(content)

    return files


def _format_files_for_prompt(files: dict[str, str]) -> str:
    """Format collected files into a prompt-friendly string."""
    if not files:
        return "[No files found]"

    parts = []
    for path, content in files.items():
        parts.append(f"### File: `{path}`\n```\n{content}\n```\n")
    return "\n".join(parts)


@mcp.tool
async def codex_query(
    prompt: str,
    reasoning_effort: str = "high",
    timeout_seconds: float = 300.0,
) -> str:
    """
    Send a general query to GPT-5.1-Codex-Max with high reasoning capabilities.

    Use this tool for one-off questions, explanations, code generation,
    or any general-purpose interaction requiring deep reasoning.

    Args:
        prompt: The question or prompt to send.
        reasoning_effort: Reasoning level - 'none', 'low', 'medium', 'high', 'xhigh'.
                         Default 'high' for thorough responses.
        timeout_seconds: Maximum wait time (default 300s for complex reasoning).

    Returns:
        Codex's response, or an error message if the request failed.
    """
    if not prompt or not prompt.strip():
        return "Error: prompt is required"

    # Map string to enum
    effort_map = {
        "none": ReasoningEffort.NONE,
        "low": ReasoningEffort.LOW,
        "medium": ReasoningEffort.MEDIUM,
        "high": ReasoningEffort.HIGH,
        "xhigh": ReasoningEffort.XHIGH,
    }
    effort = effort_map.get(reasoning_effort.lower(), ReasoningEffort.HIGH)

    client = get_client()
    response = await client.query(
        prompt,
        system_prompt=get_general_prompt(),
        reasoning_effort=effort,
        timeout=timeout_seconds,
    )

    if response.success:
        return response.output
    return f"**Error:** {response.error}"


@mcp.tool
async def codex_analyzer(
    target: str,
    focus_areas: str | None = None,
    analysis_type: str = "comprehensive",
    timeout_seconds: float = 600.0,
) -> str:
    """
    Analyze code quality, architecture, and logical flow using GPT-5.1-Codex-Max.

    This tool performs deep analysis of single files or complete projects,
    providing a comprehensive, well-structured, and actionable report.

    Analysis covers:
    - Code quality and best practices
    - Architecture alignment between components
    - Logical flow and control paths
    - Security vulnerabilities
    - Performance concerns
    - Testing gaps

    Args:
        target: File path or directory to analyze (relative to project root).
                Examples: "app/main.py", "app/", "src/components"
        focus_areas: Optional comma-separated areas to focus on.
                    Options: 'security', 'performance', 'architecture',
                            'testing', 'quality', 'all' (default: all)
        analysis_type: Type of analysis - 'quick', 'comprehensive', 'deep'.
                      Default 'comprehensive'.
        timeout_seconds: Maximum wait time (default 600s for thorough analysis).

    Returns:
        A comprehensive analysis report with prioritized findings and
        actionable recommendations, or an error message.
    """
    if not target or not target.strip():
        return "Error: target file or directory path is required"

    # Collect files
    files = _collect_files(target)
    if not files:
        return f"Error: No readable files found at '{target}'"

    # Build analysis prompt
    file_content = _format_files_for_prompt(files)
    file_count = len([f for f in files if not f.startswith("__")])

    focus_instruction = ""
    if focus_areas:
        focus_instruction = f"\n\n**Focus Areas:** {focus_areas}"

    depth_instruction = {
        "quick": "Provide a quick overview focusing on critical issues only.",
        "comprehensive": "Provide thorough analysis across all dimensions.",
        "deep": "Perform exhaustive deep-dive analysis, examining every detail.",
    }.get(analysis_type.lower(), "Provide thorough analysis across all dimensions.")

    user_prompt = f"""\
## Analysis Request

**Target:** `{target}`
**Files:** {file_count} file(s)
**Depth:** {depth_instruction}{focus_instruction}

## Code to Analyze

{file_content}

Please provide a comprehensive analysis following the report structure in your instructions.
"""

    client = get_client()
    response = await client.query(
        user_prompt,
        system_prompt=get_analyzer_prompt(),
        reasoning_effort=ReasoningEffort.HIGH,
        timeout=timeout_seconds,
    )

    if response.success:
        # Add metadata footer
        footer = f"\n\n---\n*Analysis by GPT-5.1-Codex-Max | {file_count} files | {response.reasoning_tokens} reasoning tokens*"
        return response.output + footer
    return f"**Error:** {response.error}"


@mcp.tool
async def codex_fixer(
    target: str,
    issues: str,
    fix_scope: str = "root_cause",
    timeout_seconds: float = 600.0,
) -> str:
    """
    Fix code issues at the ROOT LEVEL using GPT-5.1-Codex-Max high reasoning.

    This tool receives files/directories with concrete issues and implements
    fixes that address the root cause - NOT monkey patches or workarounds.

    Fix philosophy:
    - Traces issues back to their true origin
    - Fixes at the source, not where symptoms appear
    - Preserves existing behavior except for the bug
    - Maintains or improves type safety
    - Provides test recommendations

    Args:
        target: File path or directory containing the issue.
                Examples: "app/core/session.py", "app/api/", "src/"
        issues: Detailed description of the issue(s) to fix.
               Be specific: include error messages, stack traces,
               unexpected behaviors, or failing test outputs.
        fix_scope: Approach to fixing - 'root_cause' (default, thorough),
                  'minimal' (smallest change), 'comprehensive' (fix + refactor).
        timeout_seconds: Maximum wait time (default 600s for deep analysis).

    Returns:
        Detailed fix recommendations with before/after code,
        root cause analysis, and testing guidance.
    """
    if not target or not target.strip():
        return "Error: target file or directory path is required"
    if not issues or not issues.strip():
        return "Error: issues description is required"

    # Collect files
    files = _collect_files(target)
    if not files:
        return f"Error: No readable files found at '{target}'"

    # Build fix prompt
    file_content = _format_files_for_prompt(files)
    file_count = len([f for f in files if not f.startswith("__")])

    scope_instruction = {
        "root_cause": "Focus on identifying and fixing the ROOT CAUSE. Do not apply band-aid fixes.",
        "minimal": "Apply the smallest possible fix that resolves the issue without side effects.",
        "comprehensive": "Fix the root cause AND improve surrounding code quality if beneficial.",
    }.get(fix_scope.lower(), "Focus on identifying and fixing the ROOT CAUSE.")

    user_prompt = f"""\
## Fix Request

**Target:** `{target}`
**Files:** {file_count} file(s)
**Scope:** {scope_instruction}

## Issue Description

{issues}

## Code with Issues

{file_content}

Please analyze the root cause and provide fixes following the format in your instructions.
Remember: NO MONKEY PATCHES. Fix at the SOURCE.
"""

    client = get_client()
    response = await client.query(
        user_prompt,
        system_prompt=get_fixer_prompt(),
        reasoning_effort=ReasoningEffort.HIGH,  # Always high for fixing
        timeout=timeout_seconds,
    )

    if response.success:
        footer = f"\n\n---\n*Fix analysis by GPT-5.1-Codex-Max | {file_count} files | {response.reasoning_tokens} reasoning tokens*"
        return response.output + footer
    return f"**Error:** {response.error}"


# Entry point for CLI: python -m mcp_servers.codex.server
if __name__ == "__main__":
    mcp.run()
