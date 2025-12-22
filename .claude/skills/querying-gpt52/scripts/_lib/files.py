"""
File collection and security utilities for GPT-5.2 analysis.

Provides safe file reading with:
- Path traversal protection
- System directory blocking
- File size limits
- Allowed extensions filtering
- Secret exclusion (.env files)
"""

from __future__ import annotations

from pathlib import Path

# Project root for file reading
_MODULE_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = _MODULE_DIR.parents[
    4
]  # .claude/skills/querying-gpt52/scripts/_lib → project root

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
    # NOTE: .env deliberately excluded to prevent secret exposure
    ".gitignore",
    ".dockerfile",
    "Dockerfile",
    ".vue",
    ".svelte",
}


def is_safe_path(path: Path) -> bool:
    """Check if path is safe to read (not system files).

    Args:
        path: Path to check

    Returns:
        True if path is safe to read
    """
    resolved = path.resolve()
    dangerous_prefixes = ["/etc", "/usr", "/bin", "/sbin", "/var", "/root"]
    path_str = str(resolved)
    return not any(path_str.startswith(prefix) for prefix in dangerous_prefixes)


def should_include_file(path: Path) -> bool:
    """Check if file should be included in analysis.

    Args:
        path: Path to check

    Returns:
        True if file should be included
    """
    # Skip hidden files except .gitignore (never .env - security risk)
    if path.name.startswith(".") and path.name not in {".gitignore"}:
        return False
    if path.suffix not in ALLOWED_EXTENSIONS and path.name not in ALLOWED_EXTENSIONS:
        return False
    if "__pycache__" in str(path) or "node_modules" in str(path):
        return False
    # Check for .git directory (not .gitignore file)
    if "/.git/" in str(path) or str(path).endswith("/.git"):
        return False
    return True


def read_file_safe(path: Path, max_size: int = MAX_FILE_SIZE) -> str | None:
    """Safely read a file with size limits.

    Args:
        path: Path to file
        max_size: Maximum file size in bytes

    Returns:
        File contents or None/error message
    """
    try:
        if not path.exists() or not path.is_file():
            return None
        if not is_safe_path(path):
            return None
        if path.stat().st_size > max_size:
            return f"[File too large: {path.stat().st_size} bytes, max {max_size}]"
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[Error reading file: {e}]"


def collect_files(
    target: str,
    base_path: Path | None = None,
) -> dict[str, str]:
    """
    Collect files from a path (file or directory).

    Args:
        target: File path or directory to collect from
        base_path: Base path for relative path resolution (defaults to PROJECT_ROOT)

    Returns:
        Dict of {relative_path: content}
    """
    base = base_path or PROJECT_ROOT
    target_path = Path(target)

    # Handle relative paths
    if not target_path.is_absolute():
        target_path = base / target_path

    target_path = target_path.resolve()

    # Security: Prevent path traversal escaping project root
    if not target_path.is_relative_to(base):
        return {}  # Path escaped project root via ../

    files: dict[str, str] = {}
    total_size = 0

    if target_path.is_file():
        content = read_file_safe(target_path)
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
            if not should_include_file(file_path):
                continue
            content = read_file_safe(file_path)
            if content:
                rel_path = str(
                    file_path.relative_to(base)
                    if file_path.is_relative_to(base)
                    else file_path
                )
                files[rel_path] = content
                total_size += len(content)

    return files


def format_files_for_prompt(files: dict[str, str]) -> str:
    """Format collected files into a prompt-friendly string.

    Args:
        files: Dict of {relative_path: content}

    Returns:
        Formatted string with file contents
    """
    if not files:
        return "[No files found]"

    parts = []
    for path, content in files.items():
        parts.append(f"### File: `{path}`\n```\n{content}\n```\n")
    return "\n".join(parts)
