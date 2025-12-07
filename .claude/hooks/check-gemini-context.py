#!/usr/bin/env python3
"""
SessionStart hook: Check if Gemini MCP server has a GEMINI.md context file.

If GEMINI.md doesn't exist in mcp_servers/gemini/, this hook outputs
additionalContext instructing Claude to generate one using gemini_query.
"""

import json
import os
import sys
from pathlib import Path


def main() -> None:
    """Check for GEMINI.md and output context if missing."""
    # Get project directory from environment
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        # Fallback: try to determine from hook input
        try:
            input_data = json.load(sys.stdin)
            project_dir = input_data.get("cwd", "")
        except (json.JSONDecodeError, EOFError):
            pass

    if not project_dir:
        sys.exit(0)  # Can't determine project dir, skip silently

    gemini_md_path = Path(project_dir) / "mcp_servers" / "gemini" / "GEMINI.md"

    if gemini_md_path.exists():
        # GEMINI.md already exists, nothing to do
        sys.exit(0)

    # Check if the gemini MCP server directory exists
    gemini_server_dir = gemini_md_path.parent
    if not gemini_server_dir.exists():
        # Gemini MCP server not configured for this project
        sys.exit(0)

    # GEMINI.md is missing - output context to prompt Claude to create it
    # NOTE: Gemini will create the file at project root (for full visibility),
    # then a PostToolUse hook will move it to mcp_servers/gemini/
    context = f"""[Gemini MCP Context Setup Required]

The Gemini CLI MCP server is configured but lacks a GEMINI.md context file.

ACTION REQUIRED: Ask Gemini to analyze this project and create GEMINI.md.

Use `mcp__gemini-cli__gemini_query` with this prompt:
\"\"\"
Analyze this entire project and create a comprehensive GEMINI.md context file.
You have full visibility of the project from the root directory.

Review ALL directories including app/, tests/, mcp_servers/, and dependencies.
Create a GEMINI.md file that includes:

1. Project Overview - What the project does, key features
2. Tech Stack - Languages, frameworks, ALL key dependencies
3. Project Structure - ALL important directories and their purposes
4. Development Commands - How to run, test, build, lint
5. Code Conventions - Style guidelines, patterns used (like SessionActor)
6. Important Context - Architecture patterns, security considerations, etc.

Output this as a complete GEMINI.md file with valid Markdown formatting.
The file should give you full context to assist with ANY part of this project.
\"\"\"

A PostToolUse hook will automatically move the created GEMINI.md to {gemini_md_path}.
After completion, inform the user that Gemini context has been initialized.
"""

    # Output JSON with additionalContext for SessionStart hook
    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
