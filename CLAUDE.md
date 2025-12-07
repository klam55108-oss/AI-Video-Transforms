# Agent Video to Data

## Project Overview

A Python video transcription toolkit with two interfaces: CLI and Web UI. Built with the Claude Agent SDK and OpenAI Whisper, providing MCP-based tools for transcribing local videos and YouTube URLs.

## Tech Stack

- **Language**: Python 3.11+
- **Package Manager**: uv
- **AI Framework**: Claude Agent SDK
- **Web Framework**: FastAPI, Uvicorn, Jinja2
- **Frontend**: Tailwind CSS (CDN), Vanilla JS
- **Transcription**: OpenAI Whisper API
- **Video/Audio**: MoviePy, Pydub, yt-dlp
- **Quality**: mypy (strict), ruff

## Project Structure

```
app/
├── agent/                # Agent core
│   ├── agent.py          # CLI entry point
│   ├── server.py         # MCP server (5 tools)
│   └── prompts/          # Versioned system prompts
├── core/                 # Shared modules
│   ├── session.py        # SessionActor pattern
│   ├── storage.py        # File-based persistence
│   ├── cost_tracking.py  # Usage aggregation
│   └── permissions.py    # Tool access control
├── models/               # Pydantic schemas
│   ├── api.py            # Web API models
│   └── structured.py     # Agent output schemas
├── static/               # JS, CSS
├── templates/            # Jinja2 HTML
└── main.py               # FastAPI web app

mcp_servers/
└── gemini/               # Gemini CLI MCP server
    ├── server.py         # FastMCP server (6 tools)
    ├── client.py         # Async subprocess wrapper
    ├── session_manager.py # Chat session state
    └── GEMINI.md         # Auto-generated context
```

## Commands

```bash
# CLI agent
uv run python -m app.agent.agent

# Web server (http://127.0.0.1:8000)
uv run python -m app.main

# Quality checks
uv run mypy .
uv run ruff check .
uv run ruff format .
uv run pytest
```

## Environment Variables

Required in `.env`:
- `ANTHROPIC_API_KEY` — Claude Agent SDK
- `OPENAI_API_KEY` — Whisper transcription

## Architecture Patterns

### MCP Server Pattern
- Tools use `@tool` decorator from `claude_agent_sdk`
- Server created via `create_sdk_mcp_server()` with tool list
- Tools allowlisted as `mcp__<server-name>__<tool-name>`
- Tool functions: `async def fn(args: dict[str, Any]) -> dict[str, Any]`

### SessionActor Pattern (app/core/session.py)
The web UI isolates each user session in a dedicated asyncio task to avoid SDK context/cancel scope issues:

```python
class SessionActor:
    input_queue: asyncio.Queue   # HTTP handler → agent
    response_queue: asyncio.Queue # agent → HTTP handler

    async def _worker_loop(self):
        async with ClaudeSDKClient(options) as client:
            # Single task owns the client context
            while self.is_running:
                msg = await self.input_queue.get()
                await client.query(msg)
                # ... collect response ...
                await self.response_queue.put(response)
```

This queue-based actor model prevents race conditions when multiple HTTP requests interact with the same session.

### Prompt Management
- Versioned via `PromptVersion` dataclass in `app/agent/prompts/registry.py`
- XML structure: `<role>`, `<context>`, `<workflow>`, `<constraints>`
- Access via `get_prompt(name)` or `get_prompt_content(name)`

### External MCP Server Pattern (mcp_servers/gemini)
Wraps Gemini CLI as an MCP server for Claude Code integration:
- Uses FastMCP framework with `@mcp.tool` decorators
- Subprocess execution: `gemini --approval-mode yolo --model <model> <prompt>`
- Context management via `GEMINI.md` with auto-generation hooks
- Session-based chat via `session_manager.py`

Claude Code hooks handle GEMINI.md lifecycle:
- `SessionStart`: Detects missing context, prompts creation
- `PostToolUse`: Moves generated file to `mcp_servers/gemini/`

See `mcp_servers/gemini/README.md` for full architecture.

## Code Style

- Type hints on all signatures (return types included)
- `str | None` over `Optional[str]`
- `list[str]` over `List[str]`
- `# type: ignore[import-untyped]` for moviepy, pydub
- Google-style docstrings
- Max ~50 lines per function
- `pathlib.Path` over `os.path`

## Error Handling

- MCP tools return `{"content": [{"type": "text", "text": "..."}]}`
- Errors return `{"success": False, "error": "message"}`
- Never raise exceptions that crash the agent loop
- FastAPI endpoints use `HTTPException` with status codes

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `claude-agent-sdk` | MCP server, tool creation |
| `fastapi` | Web API framework |
| `uvicorn` | ASGI server |
| `jinja2` | HTML templating |
| `openai` | Whisper API |
| `moviepy` | Audio extraction |
| `pydub` | Audio segmentation |
| `yt-dlp` | YouTube downloads |
| `fastmcp` | External MCP server framework |

## Implementation Notes

- Audio segments: 5 minutes max, auto-downsamples if >23MB
- YouTube: uses mobile client spoofing via yt-dlp
- Temp files: auto-cleanup via `tempfile.TemporaryDirectory`
- Sessions: file-based persistence via `StorageManager` in `data/sessions/`
- Frontend: `sessionStorage` for session ID (tab isolation)
- Security: UUID v4 validation, Pydantic validators, DOMPurify XSS, blocked system paths
- Cost tracking: SDK's `total_cost_usd` from `ResultMessage`, deduplicated by message ID
- No more 🤖 Generated with Claude Code or Co-Authored-By lines. I'll remember not to add these for future commits in this project since you have the cleanup hook in place.