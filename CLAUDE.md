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
agent-video-to-data/
├── agent_video/              # Core package
│   ├── __init__.py           # Exports: video_tools_server, transcribe_video
│   ├── agent.py              # CLI entry point
│   ├── server.py             # MCP server configuration
│   ├── transcribe_tool.py    # Transcription tool
│   ├── file_tool.py          # File writing tool
│   └── prompts/
│       ├── registry.py       # PromptVersion dataclass
│       └── video_transcription.py
├── web_app.py                # FastAPI web server with SessionActor
├── templates/
│   └── index.html            # Chat UI (Tailwind + Phosphor Icons)
├── static/
│   ├── script.js             # Session management, markdown rendering
│   └── style.css             # Custom scrollbar, message bubbles
├── .claude/
│   ├── settings.json         # Permissions
│   └── agents/               # Custom subagent definitions
├── pyproject.toml
└── uv.lock
```

## Commands

```bash
# CLI agent
uv run python agent_video/agent.py

# Web server (http://127.0.0.1:8000)
uv run python web_app.py

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

### SessionActor Pattern (web_app.py)
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
- Versioned via `PromptVersion` dataclass in `prompts/registry.py`
- XML structure: `<role>`, `<context>`, `<workflow>`, `<constraints>`
- Access via `get_prompt(name)` or `get_prompt_content(name)`

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

## Implementation Notes

- Audio segments: 5 minutes max, auto-downsamples if >23MB
- YouTube: uses mobile client spoofing via yt-dlp
- Temp files: auto-cleanup via `tempfile.TemporaryDirectory`
- Web sessions: stored in-memory dict, cleaned on DELETE endpoint
- Frontend: localStorage for session ID persistence
