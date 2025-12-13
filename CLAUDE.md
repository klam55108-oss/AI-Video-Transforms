# Agent Video to Data

AI-powered video transcription web application built with Claude Agent SDK + OpenAI Whisper.

@README for full overview, API endpoints, and architecture diagram.

## Commands

```bash
# Development
uv run python -m app.main              # Web server at http://127.0.0.1:8000

# Quality (run before commits)
uv run mypy .                          # Type checking (strict mode)
uv run ruff check . && ruff format .   # Lint and format
uv run pytest                          # Run all 199 tests
```

## Environment

Required in `.env`:
- `ANTHROPIC_API_KEY` — Claude Agent SDK
- `OPENAI_API_KEY` — Whisper transcription + Codex MCP server

## Architecture

3-tier modular monolith: **API Layer** → **Services Layer** → **Core Layer**

```
app/api/          # Routers, dependency injection, error handlers
app/services/     # SessionService, StorageService, TranscriptionService
app/core/         # SessionActor, StorageManager, cost tracking
app/agent/        # MCP tools and system prompts
```

## Critical Patterns

### SessionActor (app/core/session.py) ⚠️
- **Why**: ClaudeSDKClient must run in single asyncio task to avoid cancel scope errors
- **Pattern**: Queue-based actor model isolates each user session
- **Rule**: Never access ClaudeSDKClient from multiple concurrent tasks

### Dependency Injection (app/api/deps.py)
- Services accessed via `get_services()` → `Depends(get_session_service)`
- Test overrides: `app.dependency_overrides[get_session_service] = mock`
- Never use `patch()` for FastAPI dependencies—it doesn't work

### MCP Tools (app/agent/)
- Success: `{"content": [{"type": "text", "text": "..."}]}`
- Error: `{"success": False, "error": "message"}`
- Rule: Never raise exceptions that crash the agent loop

## Code Style

See @.claude/rules/code-style.md for full guidelines:
- Type hints on ALL signatures (args + return types)
- `str | None` not `Optional[str]`; `list[str]` not `List[str]`
- Google-style docstrings
- `pathlib.Path` over `os.path`

## External MCP Servers

Two servers in `mcp_servers/`:
- **gemini/** — Gemini CLI wrapper for Claude Code integration
- **codex/** — GPT-5.1-Codex-Max via OpenAI Responses API

## Git Workflow

- No attribution lines in commits (cleanup hook removes them)
- Run quality checks before committing
