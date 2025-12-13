---
description: Load a general understanding of the codebase into the context window
---

# Prime

Execute the `Workflow` and `Report` sections to understand the codebase then summarize your understanding.

## Workflow

1. Run `git ls-files` to list all files in the repository.
2. Read `README.md` for an overview of the project.
3. Read `CLAUDE.md` for project-specific patterns and commands.
4. Read Claude Agent SDK documentation in order:
   - `ai_docs/claude_agent_sdk/01_OVERVIEW_QUICKSTART.md` - Installation, setup, migration
   - `ai_docs/claude_agent_sdk/02_CORE_API_TOOLS.md` - Core API, custom tools, MCP, subagents
   - `ai_docs/claude_agent_sdk/03_SESSION_PERMISSIONS_HOSTING.md` - Sessions, permissions, hosting
   - `ai_docs/claude_agent_sdk/04_API_REFERENCE.md` - Types, errors, skills, cost tracking

## Report

Summarize your understanding of the codebase, including:
- Project purpose and architecture
- Key patterns
