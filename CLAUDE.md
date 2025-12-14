# Agent Video to Data

AI-powered video transcription web application using Claude Agent SDK + OpenAI gpt-4o-transcribe.

@README.md for full overview, API endpoints, and architecture diagram.

## Quick Commands

```bash
uv run python -m app.main              # Dev server → http://127.0.0.1:8000
uv run pytest                          # 230 tests
uv run mypy .                          # Type check (strict)
uv run ruff check . && ruff format .   # Lint + format
```

## Environment

```bash
ANTHROPIC_API_KEY=sk-ant-...    # Claude Agent SDK
OPENAI_API_KEY=sk-...            # gpt-4o-transcribe + Codex MCP
```

## Architecture

**3-tier modular monolith**: API Layer → Services Layer → Core Layer

```
app/api/          # Routers, deps, error handlers
app/services/     # SessionService, StorageService, TranscriptionService
app/core/         # SessionActor, StorageManager, cost tracking
app/agent/        # MCP tools + system prompts
```

## Critical Patterns ⚠️

### SessionActor (`app/core/session.py`)

- **Problem**: ClaudeSDKClient fails with cancel scope errors when accessed from multiple asyncio tasks
- **Solution**: Queue-based actor model — one dedicated task per session
- **Rule**: NEVER access ClaudeSDKClient from concurrent tasks

### Dependency Injection (`app/api/deps.py`)

- Access services: `Depends(get_session_service)`
- Test mocking: `app.dependency_overrides[get_session_service] = mock`
- **Rule**: NEVER use `patch()` for FastAPI dependencies — it doesn't work

### MCP Tool Returns (`app/agent/`)

```python
# Success
{"content": [{"type": "text", "text": "..."}]}

# Error (never raise exceptions)
{"success": False, "error": "message"}
```

- **Rule**: NEVER raise exceptions that escape tools — they crash the agent loop

## Code Rules

See @.claude/rules/ for detailed guidelines:
- @.claude/rules/code-style.md — Type hints, formatting, imports
- @.claude/rules/fastapi.md — Router patterns, dependency injection
- @.claude/rules/testing.md — Pytest patterns, mocking
- @.claude/rules/mcp-tools.md — Tool development patterns

**Key conventions**:
- Type hints on ALL signatures (args + return types)
- `str | None` not `Optional[str]`
- `pathlib.Path` over `os.path`
- Google-style docstrings for public functions

## External MCP Servers

Two servers in `mcp_servers/`:
- **gemini/** — Gemini CLI wrapper (@.claude/rules/gemini-mcp.md)
- **codex/** — GPT-5.1-Codex-Max via OpenAI Responses API (@.claude/rules/codex-mcp.md)

## Git Workflow

- Run quality checks before commits: `uv run mypy . && uv run ruff check . && uv run pytest`
- No attribution lines in commits (cleanup hook removes them)
