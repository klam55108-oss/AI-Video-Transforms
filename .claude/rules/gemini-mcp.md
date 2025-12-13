---
paths: mcp_servers/gemini/**/*.py
---

# Gemini MCP Server Patterns

## Framework
- Use FastMCP with `@mcp.tool` decorators
- Server defined in `mcp_servers/gemini/server.py`
- Client wrapper in `mcp_servers/gemini/client.py`

## Subprocess Execution
```python
# Command pattern for Gemini CLI
gemini --approval-mode yolo --model <model> <prompt>
```

## Session Management
- Multi-turn chat via `session_manager.py`
- Sessions stored in memory with unique IDs
- Use `gemini_chat` for conversations, `gemini_query` for one-shots

## Context Management
- GEMINI.md provides project context to Gemini
- Auto-generated via Claude Code hooks:
  - `SessionStart`: Detects missing context
  - `PostToolUse`: Moves generated file to correct location

## Error Handling
- Wrap subprocess calls in try/except
- Return structured error messages
- Handle timeout scenarios gracefully
