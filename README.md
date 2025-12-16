# Agent Video to Data

> Transform videos into searchable transcripts and knowledge graphs through an intelligent AI chat interface.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-538%20passing-brightgreen.svg)](#testing)
[![Type Check](https://img.shields.io/badge/mypy-strict-blue.svg)](#development)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Built with **Claude Agent SDK** and **OpenAI gpt-4o-transcribe**.

---

## Quick Start

```bash
git clone https://github.com/costiash/agent-video-to-data.git
cd agent-video-to-data
uv sync

cp .env.example .env
# Add your API keys to .env:
#   ANTHROPIC_API_KEY=sk-ant-...
#   OPENAI_API_KEY=sk-...

uv run python -m app.main
# Open http://127.0.0.1:8000
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Video Transcription** | Local videos (mp4, mkv, avi, mov, webm, m4v) and YouTube URLs via gpt-4o-transcribe |
| **Knowledge Graphs** | Auto-bootstrap domain schemas, extract entities/relationships, export to GraphML/JSON |
| **Transcript Library** | Save, search, and download transcripts with unique 8-char IDs |
| **Real-Time Chat** | Markdown rendering, session isolation, dark/light themes, cost tracking |

---

## Knowledge Graph Workflow

```
1. Create Project  →  2. Bootstrap (first video)  →  3. Confirm Discoveries  →  4. Extract  →  5. Export
```

| Step | What Happens |
|------|--------------|
| **Create** | Name your research topic — project starts in `CREATED` state |
| **Bootstrap** | First video auto-infers entity types (Person, Organization...) and relationships |
| **Confirm** | Review and approve/reject discovered patterns |
| **Extract** | Subsequent videos use the confirmed schema for consistent extraction |
| **Export** | Download as GraphML (for Gephi/Neo4j) or JSON |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                        │
├───────────────────┬─────────────────────┬───────────────────────┤
│    API Layer      │   Services Layer    │     Core Layer        │
│  ─────────────    │   ───────────────   │   ──────────────      │
│  7 Routers        │  SessionService     │  SessionActor         │
│  Dependency Inj.  │  StorageService     │  Atomic Storage       │
│  Error Handlers   │  KnowledgeGraph     │  Cost Tracking        │
├───────────────────┴─────────────────────┴───────────────────────┤
│                 Claude Agent SDK + MCP Tools                    │
└─────────────────────────────────────────────────────────────────┘
```

**SessionActor Pattern** — Each session runs in a dedicated asyncio task with queue-based message passing, preventing Claude SDK cancel scope errors:

```
HTTP Request → input_queue → [SessionActor] → response_queue → Response
```

---

## API Reference

### Chat & Sessions

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
| `/transcripts` | GET | List all transcripts |
| `/transcripts/{id}/download` | GET | Download transcript |
| `/transcripts/{id}` | DELETE | Delete transcript |

### Knowledge Graph

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/kg/projects` | GET | List all projects |
| `/kg/projects` | POST | Create project |
| `/kg/projects/{id}` | GET | Get project status |
| `/kg/projects/{id}/bootstrap` | POST | Bootstrap from transcript |
| `/kg/projects/{id}/confirm` | POST | Confirm discoveries |
| `/kg/projects/{id}/extract` | POST | Extract from transcript |
| `/kg/projects/{id}/export` | POST | Export (GraphML/JSON) |
| `/kg/projects/{id}/nodes` | GET | Query nodes |
| `/kg/projects/{id}/neighbors` | GET | Get node neighbors |

### History & Cost

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/history` | GET | List sessions |
| `/history/{session_id}` | GET | Session details |
| `/history/{session_id}` | DELETE | Delete session |
| `/cost` | GET | Global cost stats |
| `/cost/{session_id}` | GET | Session cost |

---

## MCP Tools

Tools available to the Claude agent:

| Tool | Description |
|------|-------------|
| `transcribe_video` | Video/audio → text via gpt-4o-transcribe |
| `save_transcript` | Persist with unique 8-char ID |
| `get_transcript` | Retrieve by ID |
| `list_transcripts` | List all transcripts |
| `write_file` | Save content (path validated) |
| `create_kg_project` | Create KG project |
| `bootstrap_kg_project` | Infer domain from transcript |
| `extract_to_kg` | Extract entities/relationships |
| `list_kg_projects` | List projects with stats |
| `get_kg_stats` | Graph statistics by type |

---

## Development

```bash
uv run python -m app.main              # Dev server
uv run pytest                          # 538 tests
uv run mypy .                          # Type check (strict)
uv run ruff check . && ruff format .   # Lint + format
```

See [CLAUDE.md](CLAUDE.md) for development guidelines and code standards.

---

## Configuration

### Required

```bash
ANTHROPIC_API_KEY=sk-ant-...    # Claude Agent SDK
OPENAI_API_KEY=sk-...            # gpt-4o-transcribe
```

### Optional (with defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_CLAUDE_MODEL` | `claude-opus-4-5` | Claude model |
| `APP_CLAUDE_API_MAX_CONCURRENT` | `2` | Max concurrent API calls |
| `APP_RESPONSE_TIMEOUT` | `300.0` | Agent timeout (seconds) |
| `APP_SESSION_TTL` | `3600.0` | Session expiry (1 hour) |
| `APP_CLEANUP_INTERVAL` | `300.0` | Cleanup interval (5 min) |
| `APP_KG_POLL_INTERVAL_MS` | `5000` | KG status poll interval (ms) |
| `APP_STATUS_POLL_INTERVAL_MS` | `3000` | Agent status poll interval (ms) |

---

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Backend** | FastAPI, Uvicorn, Pydantic |
| **AI** | Claude Agent SDK, OpenAI gpt-4o-transcribe |
| **Knowledge Graph** | NetworkX, Pydantic domain models |
| **Media** | FFmpeg, pydub, yt-dlp |
| **Frontend** | Vanilla JS, Tailwind CSS, Marked.js, DOMPurify |
| **Quality** | mypy (strict), ruff, pytest |

---

## Project Structure

```
app/
├── api/routers/     # 7 endpoint routers
├── services/        # SessionService, StorageService, KnowledgeGraphService
├── core/            # SessionActor, config, storage, cost tracking
├── agent/           # MCP tools + system prompts
├── kg/              # Domain models, graph storage, extraction tools
├── models/          # Pydantic schemas
├── static/          # Frontend JS/CSS
└── templates/       # Jinja2 HTML

tests/               # 538 tests across 27 modules
data/                # Runtime storage (sessions, transcripts, kg_projects)
```

---

## License

MIT
