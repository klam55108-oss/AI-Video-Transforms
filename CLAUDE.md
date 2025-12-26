# Agent Video to Data

AI-powered video transcription and knowledge graph extraction.

## Quick Commands

```bash
uv run python -m app.main              # Dev server → http://127.0.0.1:8000
uv run pytest                          # 647 tests
uv run mypy .                          # Type check (strict)
uv run ruff check . && ruff format .   # Lint + format
```

## Environment

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...    # Claude Agent SDK
OPENAI_API_KEY=sk-...           # gpt-4o-transcribe

# Optional (for Claude Code skills)
GEMINI_API_KEY=...              # Gemini 3 Flash skill (querying-gemini)
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
| Frontend | `app/static/js/` | 32 ES modules (chat, kg, jobs, upload, workspace) |

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

**Race Condition Handling**: Jobs may complete while `state.isProcessing` is still true from a prior request. The `sendMessageWhenReady()` function in `jobs/jobs.js` retries at 500ms intervals (max 20 attempts / 10 seconds) until processing clears, preventing silent callback drops.

### Job Persistence — Jobs survive server restarts

```
Job Created → Persist to data/jobs/{id}.json
                        ↓
Progress Update (10%) → Persist state outside lock
                        ↓
Server Restart → restore_pending_jobs() recovers PENDING/RUNNING jobs
```

Jobs are persisted at creation, every 10% progress, and on completion. On startup, `restore_pending_jobs()` recovers in-progress jobs.

### Activity Streaming — Real-time agent status via SSE

```
Message sent → SSE connection opens → SessionActor emits ActivityEvents
                                              ↓
Frontend updates loading indicator ← Event stream: thinking → tool_use → completed
```

During message processing, `SessionActor._emit_activity()` broadcasts real-time events (thinking, tool_use, tool_result, subagent, completed) to SSE subscribers. Frontend falls back to polling if SSE unavailable.

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

## SDK Agent Resources

The runtime agent (not Claude Code) uses resources from `app/agent/resources/`:

```
app/agent/resources/
├── CLAUDE.md                 # Agent instructions (loaded via setting_sources)
├── README.md                 # Documentation
└── .claude/
    ├── settings.json         # Agent permissions
    └── skills/
        ├── transcription-helper/SKILL.md
        ├── kg-bootstrap/SKILL.md
        ├── error-recovery/SKILL.md
        └── content-saver/SKILL.md
```

| Resource | Purpose |
|----------|---------|
| `CLAUDE.md` | Agent instructions loaded via `setting_sources=["project"]` |
| `.claude/skills/` | Reusable workflow skills invocable by the agent |
| `.claude/settings.json` | Agent permissions (MCP tool allowlist) |

**SessionActor configuration** (`app/core/session.py`):
- `cwd` → Points to `app/agent/resources/`
- `setting_sources=["project"]` → Loads CLAUDE.md from cwd
- `"Skill"` in `allowed_tools` → Enables skill invocation

## Claude Code Skills

For Claude Code (not the app agent), these skills provide multi-model AI capabilities:

| Skill | Location | Purpose |
|-------|----------|---------|
| `querying-gemini` | `.claude/skills/querying-gemini/` | Gemini 3 Flash for code analysis, generation, and bug fixing |
| `querying-gpt52` | `.claude/skills/querying-gpt52/` | GPT-5.2 for high-reasoning analysis and comprehensive output |
| `council-advice` | `.claude/skills/council-advice/` | Multi-model advisory council (Gemini + GPT-5.2 → Opus Judge) |
| `frontend-design` | `.claude/skills/frontend-design/` | Frontend design patterns and best practices |

**Usage**: Skills are invoked via their script files in `scripts/` subdirectories.

**API Keys Required**:
- `GEMINI_API_KEY` or `GOOGLE_API_KEY` for Gemini skills
- `OPENAI_API_KEY` for GPT-5.2 skills
- `ANTHROPIC_API_KEY` for Opus Judge in council-advice

## Documentation

| Document | Purpose |
|----------|---------|
| @README.md | Project overview, quick start |
