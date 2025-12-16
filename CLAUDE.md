# Agent Video to Data

AI-powered video transcription and knowledge graph extraction.

@README.md for full overview, API endpoints, and architecture.

## Quick Commands

```bash
uv run python -m app.main              # Dev server → http://127.0.0.1:8000
uv run pytest                          # 538 tests
uv run mypy .                          # Type check (strict)
uv run ruff check . && ruff format .   # Lint + format
```

## Environment

```bash
ANTHROPIC_API_KEY=sk-ant-...    # Claude Agent SDK (required)
OPENAI_API_KEY=sk-...            # gpt-4o-transcribe + Codex MCP (required)
```

## Architecture

**3-tier modular monolith**: API → Services → Core

| Layer | Location | Responsibility |
|-------|----------|----------------|
| **API** | `app/api/` | 7 routers, deps, error handlers |
| **Services** | `app/services/` | Session, Storage, Transcription, KnowledgeGraph |
| **Core** | `app/core/` | SessionActor, StorageManager, cost tracking, config |
| **Agent** | `app/agent/` | MCP tools + system prompts |
| **KG** | `app/kg/` | Domain models, graph storage, extraction |

## Critical Patterns

### SessionActor (`app/core/session.py`)

- **Problem**: Claude SDK fails with cancel scope errors when accessed from multiple asyncio tasks
- **Solution**: Queue-based actor model — one dedicated task per session
- **Rule**: NEVER access ClaudeSDKClient from concurrent tasks

### Dependency Injection (`app/api/deps.py`)

- Access services via: `Depends(get_session_service)`, `Depends(get_kg_service)`
- Test mocking: `app.dependency_overrides[get_session_service] = mock`
- **Rule**: NEVER use `patch()` for FastAPI dependencies — it doesn't work

### MCP Tool Returns (`app/agent/`, `app/kg/tools/`)

```python
# Success
{"content": [{"type": "text", "text": "..."}]}

# Error (NEVER raise exceptions)
{"success": False, "error": "message"}
```

- **Rule**: NEVER raise exceptions that escape tools — they crash the agent loop

### Knowledge Graph Service (`app/services/kg_service.py`)

- Accessed via `get_services().kg` from ServiceContainer
- Projects stored in `data/kg_projects/`
- **Rule**: Always use DomainProfile for extraction context

### Configuration (`app/core/config.py`)

- All settings via `get_settings()` singleton
- Environment variables with `APP_` prefix (e.g., `APP_CLAUDE_MODEL`)
- Concurrency control: `APP_CLAUDE_API_MAX_CONCURRENT=2` (prevents cost blowouts)
- **Rule**: NEVER hardcode configurable values — use `get_settings()`

## Code Standards

See `.claude/rules/` for detailed guidelines:

| Rule File | Scope |
|-----------|-------|
| @.claude/rules/code-style.md | Type hints, formatting, imports |
| @.claude/rules/config.md | Centralized configuration, concurrency |
| @.claude/rules/fastapi.md | Router patterns, dependency injection |
| @.claude/rules/testing.md | Pytest patterns, mocking |
| @.claude/rules/mcp-tools.md | MCP tool development |
| @.claude/rules/kg.md | Knowledge graph patterns |
| @.claude/rules/frontend.md | Tailwind, vanilla JS, security |

## External MCP Servers

Two servers in `mcp_servers/` (for Claude Code, not the app agent):

| Server | Purpose | Rule File |
|--------|---------|-----------|
| **codex/** | GPT-5.1-Codex-Max via OpenAI Responses API | @.claude/rules/codex-mcp.md |
| **gemini/** | Gemini CLI wrapper | @.claude/rules/gemini-mcp.md |

## Git Workflow

- Run quality checks before commits: `uv run mypy . && uv run ruff check . && uv run pytest`
- No attribution lines in commits (cleanup hook removes them)
