# Agent Video to Data

> Transform videos into searchable transcripts and knowledge graphs through an intelligent AI chat interface.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-534%20passing-brightgreen.svg)](#testing)
[![Type Check](https://img.shields.io/badge/mypy-strict-blue.svg)](#development)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

AI-powered video transcription and knowledge extraction built with **Claude Agent SDK** and **OpenAI gpt-4o-transcribe**.

---

## Features

| Feature | Description |
|---------|-------------|
| **Video Transcription** | Local videos (mp4, mkv, avi, mov, webm, m4v) and YouTube URLs with smart segmentation |
| **Knowledge Graphs** | Auto-bootstrap semantic graphs from transcripts with entity/relationship extraction |
| **Transcript Library** | Save, search, and download transcripts with unique 8-char IDs |
| **Real-Time Chat** | Markdown rendering, session isolation, dark/light themes |
| **Cost Tracking** | Per-session and global token usage with USD calculation |

---

## Quick Start

```bash
# Clone & install
git clone https://github.com/costiash/agent-video-to-data.git
cd agent-video-to-data
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your API keys:
#   ANTHROPIC_API_KEY=sk-ant-...
#   OPENAI_API_KEY=sk-...

# Run
uv run python -m app.main
# Open http://127.0.0.1:8000
```

---

## Architecture

**3-Tier Modular Monolith** — Clean separation between HTTP handling, business logic, and infrastructure.

```
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                        │
├───────────────────┬─────────────────────┬───────────────────────┤
│    API Layer      │   Services Layer    │     Core Layer        │
│    ───────────    │   ───────────────   │     ──────────        │
│  • Routers (7)    │  • SessionService   │  • SessionActor       │
│  • Dependencies   │  • StorageService   │  • StorageManager     │
│  • Error Handling │  • Transcription    │  • Cost Tracking      │
│                   │  • KnowledgeGraph   │  • Permissions        │
├───────────────────┴─────────────────────┴───────────────────────┤
│                 Claude Agent SDK + MCP Tools                    │
└─────────────────────────────────────────────────────────────────┘
```

### SessionActor Pattern

The Claude SDK client must run in a single asyncio task context. The actor model isolates each user session with dedicated input/response queues:

```
HTTP Request → input_queue → [SessionActor] → response_queue → Response
                                    │
                       Single asyncio task per session
                       (prevents cancel scope errors)
```

---

## Project Structure

```
app/
├── api/                    # HTTP layer
│   ├── routers/            # chat, transcripts, upload, history, cost, kg
│   ├── deps.py             # Dependency injection
│   └── errors.py           # Exception handlers
├── services/               # Business logic
│   ├── session_service.py  # SessionActor lifecycle
│   ├── storage_service.py  # Storage operations
│   ├── transcription_service.py
│   └── kg_service.py       # Knowledge graph orchestration
├── core/                   # Infrastructure
│   ├── config.py           # Centralized configuration (pydantic-settings)
│   ├── session.py          # SessionActor (critical)
│   ├── storage.py          # Atomic file persistence
│   ├── cost_tracking.py    # Token usage aggregation
│   └── permissions.py      # Path validation
├── agent/                  # MCP tools & prompts
│   ├── server.py           # MCP server definition
│   ├── transcribe_tool.py  # Whisper integration
│   ├── kg_tool.py          # Knowledge graph tools
│   └── prompts/            # Versioned system prompts
├── kg/                     # Knowledge graph module
│   ├── domain.py           # ThingType, ConnectionType, KGProject
│   ├── knowledge_base.py   # Graph storage (NetworkX)
│   ├── models.py           # Node, Edge, Source
│   ├── schemas.py          # Extraction output schemas
│   └── tools/              # Bootstrap & extraction tools
├── models/                 # Pydantic schemas
├── static/                 # Frontend assets
└── templates/              # Jinja2 HTML

mcp_servers/                # External MCP servers (for Claude Code)
├── codex/                  # GPT-5.1-Codex-Max
└── gemini/                 # Gemini CLI

tests/                      # 534 tests across 27 modules
data/                       # Runtime storage (sessions, transcripts, kg_projects)
```

---

## Knowledge Graph System

The KG bootstrap system automatically infers domain-specific entity types and relationships from your first video, then extracts structured knowledge from subsequent videos.

**Workflow:**
1. **Create Project** — Name your research topic
2. **Bootstrap** — First video auto-infers entity types (Person, Organization, etc.) and relationships
3. **Confirm** — Review and approve discovered patterns
4. **Extract** — Process additional videos using the learned schema
5. **Export** — Download as GraphML or JSON

**Domain Models:**
- `ThingType` — Entity categories to extract (e.g., Person, Project, Technology)
- `ConnectionType` — Relationship types (e.g., worked_for, funded_by, created)
- `SeedEntity` — Key entities for canonical naming consistency
- `DomainProfile` — Auto-inferred domain configuration

---

## API Reference

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web dashboard |
| `/chat/init` | POST | Initialize session |
| `/chat` | POST | Send message to agent |
| `/chat/{session_id}` | DELETE | Close session |
| `/status/{session_id}` | GET | Poll agent status |
| `/upload` | POST | Upload video (500MB max) |

### Transcripts

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/transcripts` | GET | List saved transcripts |
| `/transcripts/{id}/download` | GET | Download transcript |
| `/transcripts/{id}` | DELETE | Delete transcript |

### Knowledge Graph

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/kg/projects` | POST | Create KG project |
| `/kg/projects/{id}` | GET | Get project status |
| `/kg/projects/{id}/bootstrap` | POST | Bootstrap from transcript |
| `/kg/projects/{id}/confirm` | POST | Confirm discoveries |
| `/kg/projects/{id}/extract` | POST | Extract from transcript |
| `/kg/projects/{id}/export` | POST | Export (GraphML/JSON) |

### History & Cost

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/history` | GET | List sessions |
| `/history/{session_id}` | GET/DELETE | Session details |
| `/cost` | GET | Global cost stats |
| `/cost/{session_id}` | GET | Session cost |

---

## MCP Tools

Tools exposed to the Claude agent during conversations:

### Transcription
| Tool | Description |
|------|-------------|
| `transcribe_video` | Convert video/audio to text via gpt-4o-transcribe |
| `save_transcript` | Persist transcript with unique ID |
| `get_transcript` | Retrieve transcript by ID (lazy loading) |
| `list_transcripts` | List all saved transcripts |

### Knowledge Graph
| Tool | Description |
|------|-------------|
| `extract_to_kg` | Extract entities/relationships from transcript |
| `list_kg_projects` | List all projects with stats |
| `create_kg_project` | Create new KG project |
| `bootstrap_kg_project` | Bootstrap domain from first transcript |
| `get_kg_stats` | Get graph statistics by type |

### File Operations
| Tool | Description |
|------|-------------|
| `write_file` | Save content to filesystem (with path validation) |

---

## Development

### Commands

```bash
uv run python -m app.main              # Dev server → http://127.0.0.1:8000
uv run pytest                          # Run all tests
uv run mypy .                          # Type check (strict)
uv run ruff check . && ruff format .   # Lint + format

# All quality checks (run before commits)
uv run mypy . && uv run ruff check . && uv run ruff format . && uv run pytest
```

### Testing

**534 tests** across 27 modules:

| Category | Coverage |
|----------|----------|
| API & Integration | Endpoints, validation, E2E flows |
| Services | SessionService, StorageService, Transcription |
| Knowledge Graph | Domain models, extraction, persistence, tools |
| Concurrency | Race conditions, TTL cleanup, queue behavior |
| Security | Permissions, path validation |

---

## Configuration

### Required Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...    # Claude Agent SDK (required)
OPENAI_API_KEY=sk-...            # Whisper API (required)
```

### Optional Configuration

All settings have sensible defaults. Override via environment variables with `APP_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_CLAUDE_MODEL` | `claude-opus-4-5` | Claude model ID |
| `APP_CLAUDE_API_MAX_CONCURRENT` | `2` | Max concurrent Claude API calls |
| `APP_RESPONSE_TIMEOUT` | `300.0` | Agent response timeout (seconds) |
| `APP_SESSION_TTL` | `3600.0` | Session expiry (1 hour) |
| `APP_CLEANUP_INTERVAL` | `300.0` | Cleanup task interval (5 min) |
| `APP_QUEUE_MAX_SIZE` | `10` | Max pending messages per session |
| `APP_KG_PROJECT_CACHE_MAX_SIZE` | `100` | LRU cache size for KG projects |

### Defaults

| Setting | Value |
|---------|-------|
| Upload max size | 500MB |
| Video formats | mp4, mkv, avi, mov, webm, m4v |

---

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Backend** | FastAPI, Uvicorn, Pydantic |
| **AI** | Claude Agent SDK, OpenAI gpt-4o-transcribe |
| **Knowledge Graph** | NetworkX, Pydantic domain models |
| **Media** | Pydub, yt-dlp, FFmpeg |
| **Frontend** | Vanilla JS, Tailwind CSS, Marked.js, DOMPurify |
| **Quality** | mypy (strict), ruff, pytest |
| **Storage** | File-based JSON with atomic writes |

---

## Security

| Layer | Protection |
|-------|------------|
| **Input** | UUID v4 validation, Pydantic schemas |
| **Files** | System path blocklist (`/etc`, `/usr`, `/bin`, etc.) |
| **Uploads** | Extension allowlist, 500MB limit |
| **Frontend** | DOMPurify XSS sanitization |
| **Storage** | Atomic writes (write-to-temp-then-rename) |
| **Sessions** | 1-hour TTL with auto-cleanup |
| **API Calls** | Concurrency limits prevent cost blowouts (default: 2) |

---

## License

MIT
