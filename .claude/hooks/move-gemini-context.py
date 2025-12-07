#!/usr/bin/env python3
"""
PostToolUse hook: Move GEMINI.md from project root to mcp_servers/gemini/.

After Gemini CLI tool calls, this hook checks if GEMINI.md was created/updated
at project root and moves it to the MCP server directory for organization.

This ensures Gemini has full project visibility when creating the context file,
while keeping the file stored with the MCP server code.
"""

import json
import os
import shutil
import sys
from pathlib import Path


def main() -> None:
    """Check for new GEMINI.md at root and move to mcp_servers/gemini/."""
    # Get project directory
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        try:
            input_data = json.load(sys.stdin)
            project_dir = input_data.get("cwd", "")
        except (json.JSONDecodeError, EOFError):
            pass

    if not project_dir:
        sys.exit(0)

    project_path = Path(project_dir)
    root_gemini_md = project_path / "GEMINI.md"
    target_gemini_md = project_path / "mcp_servers" / "gemini" / "GEMINI.md"

    # Check if source exists
    if not root_gemini_md.exists():
        sys.exit(0)

    # Check if target directory exists
    if not target_gemini_md.parent.exists():
        sys.exit(0)

    # Determine if we should move:
    # - Target doesn't exist, OR
    # - Source is newer than target
    should_move = False
    if not target_gemini_md.exists():
        should_move = True
    else:
        source_mtime = root_gemini_md.stat().st_mtime
        target_mtime = target_gemini_md.stat().st_mtime
        if source_mtime > target_mtime:
            should_move = True

    if should_move:
        try:
            # Move the file (not copy - we want it in mcp_servers/gemini/)
            shutil.move(str(root_gemini_md), str(target_gemini_md))
            # Output message for Claude to see
            print(f"[Hook] Moved GEMINI.md to {target_gemini_md}")
        except (OSError, shutil.Error) as e:
            print(f"[Hook] Failed to move GEMINI.md: {e}", file=sys.stderr)
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
