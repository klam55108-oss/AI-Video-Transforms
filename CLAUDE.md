# Agent Video to Data

AI-powered video transcription and knowledge graph extraction.

## Quick Commands

```bash
uv run python -m app.main              # Dev server → http://127.0.0.1:8000
uv run pytest                          # 612 tests
uv run mypy .                          # Type check (strict)
uv run ruff check . && ruff format .   # Lint + format
```

## Environment

```bash
ANTHROPIC_API_KEY=sk-ant-...    # Required: Claude Agent SDK
OPENAI_API_KEY=sk-...           # Required: gpt-4o-transcribe
```

## Architecture

**3-tier modular monolith**: API → Services → Core

| Layer | Location | Purpose |
|-------|----------|---------|
| API | `app/api/` | 8 routers, dependency injection, error handlers |
| Services | `app/services/` | Session, Storage, KG, JobQueue |
| Core | `app/core/` | SessionActor, config, cost tracking |
| Agent | `app/agent/` | MCP tools, system prompts |
| KG | `app/kg/` | Domain models, graph storage, extraction |
| Frontend | `app/static/js/` | 26 ES modules (chat, kg, jobs, upload) |

## Critical Patterns

### SessionActor — NEVER access Claude SDK from concurrent tasks

```
HTTP Request → input_queue → [SessionActor] → response_queue → Response
```

Queue-based actor model prevents Claude SDK cancel scope errors. See `app/core/session.py`.

### MCP Tools — NEVER raise exceptions

```python
# ✅ Success
return {"content": [{"type": "text", "text": "..."}]}

# ✅ Error
return {"success": False, "error": "message"}
```

Exceptions crash the agent loop. Always return structured responses.

### FastAPI Dependencies — NEVER use patch()

```python
# ✅ Correct
app.dependency_overrides[get_session_service] = lambda: mock

# ❌ Wrong
with patch("app.api.deps.get_session_service"):  # Doesn't work
```

### Configuration — NEVER hardcode values

```python
from app.core.config import get_settings
settings = get_settings()  # Singleton with APP_ prefix env vars
```

### Job Auto-Continuation — Seamless async workflow

```
Agent creates job → Frontend detects Job ID → Sidebar shows progress
                                                      ↓
Agent auto-responds with results ← Hidden callback message ← Job completes
```

When background jobs complete, `triggerJobCompletionCallback()` sends a hidden message to the agent. This creates seamless conversation flow where async work automatically continues the chat.

## Code Standards

See `.claude/rules/` for detailed guidelines:

| Rule | Scope | Key Points |
|------|-------|------------|
| @.claude/rules/code-style.md | `**/*.py` | Type hints, `str \| None`, pathlib |
| @.claude/rules/fastapi.md | `app/api/**` | Routers, Depends(), Pydantic |
| @.claude/rules/testing.md | `tests/**` | pytest, dependency_overrides |
| @.claude/rules/mcp-tools.md | `app/agent/**` | Tool structure, error handling |
| @.claude/rules/kg.md | `app/kg/**` | Domain models, extraction |
| @.claude/rules/frontend.md | `app/static/**` | XSS protection, ES modules |
| @.claude/rules/config.md | — | Settings, env vars, caching |

## External MCP Servers

For Claude Code (not the app agent):

| Server | Purpose |
|--------|---------|
| `mcp_servers/codex/` | GPT-5.2 via OpenAI Responses API (@.claude/rules/codex-mcp.md) |
| `mcp_servers/gemini/` | Gemini CLI wrapper (@.claude/rules/gemini-mcp.md) |

## Documentation

| Document | Purpose |
|----------|---------|
| @README.md | Project overview, quick start |
