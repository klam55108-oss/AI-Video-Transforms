# Agent Video to Data

Video transcription toolkit with CLI and Web UI. Built with Claude Agent SDK + OpenAI Whisper.

@README for full overview and API documentation.

## Commands

```bash
# Development
uv run python -m app.main              # Web server at http://127.0.0.1:8000
uv run python -m app.agent.agent       # CLI agent

# Quality (run before commits)
uv run mypy .                          # Type checking (strict mode)
uv run ruff check . && ruff format .   # Lint and format
uv run pytest                          # Tests (88 total)
```

## Environment

Required in `.env`:
- `ANTHROPIC_API_KEY` — Claude Agent SDK
- `OPENAI_API_KEY` — Whisper transcription + Codex MCP server

## External MCP Servers

Two external MCP servers in `mcp_servers/`:
- **gemini/** — Wraps Gemini CLI via subprocess for Claude Code integration
- **codex/** — Wraps GPT-5.1-Codex-Max via OpenAI Responses API for high-reasoning tasks

See `mcp_servers/*/README.md` or `CODEX.md`/`GEMINI.md` for tool documentation.

## Critical Patterns

### SessionActor (app/core/session.py)
- **Why**: ClaudeSDKClient must run in single asyncio task to avoid cancel scope errors
- **Pattern**: Queue-based actor model isolates each user session
- **Rule**: Never access ClaudeSDKClient from multiple concurrent tasks

### MCP Tools (app/agent/)
- Tool return format: `{"content": [{"type": "text", "text": "..."}]}`
- Error format: `{"success": False, "error": "message"}`
- Never raise exceptions that crash the agent loop

### Cost Tracking
- Use `ResultMessage.total_cost_usd` from SDK (authoritative source)
- Deduplicate by message ID to avoid double-counting

## Code Style

- Type hints on ALL signatures including return types
- `str | None` not `Optional[str]`; `list[str]` not `List[str]`
- `# type: ignore[import-untyped]` for moviepy, pydub
- Google-style docstrings
- Max ~50 lines per function
- `pathlib.Path` over `os.path`

## Git Workflow

- No attribution lines in commits (cleanup hook removes them)
- Run quality checks before committing
