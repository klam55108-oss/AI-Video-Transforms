# Agent Video to Data

> Transform videos into searchable transcripts and knowledge graphs through an intelligent AI chat interface.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-597%20passing-brightgreen.svg)](#development)
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

### Docker

```bash
docker-compose up -d
# Open http://localhost:8000
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Video Transcription** | Local videos and YouTube URLs via gpt-4o-transcribe |
| **Background Jobs** | Async job queue with real-time progress tracking |
| **Knowledge Graphs** | Auto-bootstrap domain schemas, extract entities/relationships |
| **Graph Visualization** | Interactive Cytoscape.js with search, type filtering, node inspector |
| **Transcript Library** | Save, search, and download transcripts |
| **Chat Interface** | Markdown rendering, dark/light themes, keyboard shortcuts |

---

## Knowledge Graph Workflow

```
Create Project  →  Bootstrap  →  Confirm Discoveries  →  Extract  →  Export
```

1. **Create** — Name your research topic
2. **Bootstrap** — First video auto-infers entity types and relationships
3. **Confirm** — Review and approve/reject discovered patterns
4. **Extract** — Subsequent videos use the confirmed schema
5. **Export** — Download as GraphML (Gephi/Neo4j) or JSON

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                        │
├───────────────────┬─────────────────────┬───────────────────────┤
│    API Layer      │   Services Layer    │     Core Layer        │
│  ─────────────    │   ───────────────   │   ──────────────      │
│  8 Routers        │  SessionService     │  SessionActor         │
│  Dependency Inj.  │  StorageService     │  Cost Tracking        │
│  Error Handlers   │  KnowledgeGraphSvc  │  Config               │
│                   │  JobQueueService    │                       │
├───────────────────┴─────────────────────┴───────────────────────┤
│                 Claude Agent SDK + MCP Tools                    │
└─────────────────────────────────────────────────────────────────┘
```

**SessionActor Pattern** — Queue-based actor model prevents Claude SDK cancel scope errors:

```
HTTP Request → input_queue → [SessionActor] → response_queue → Response
```

---

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Backend** | FastAPI, Uvicorn, Pydantic |
| **AI** | Claude Agent SDK, OpenAI gpt-4o-transcribe |
| **Knowledge Graph** | NetworkX, Cytoscape.js |
| **Media** | FFmpeg, pydub, yt-dlp |
| **Frontend** | ES Modules, Tailwind CSS, Marked.js, DOMPurify |
| **Quality** | mypy (strict), ruff, pytest (597 tests) |

---

## Project Structure

```
app/
├── api/routers/     # 8 endpoint routers
├── services/        # Session, Storage, KG, JobQueue services
├── core/            # SessionActor, config, cost tracking
├── agent/           # MCP tools + system prompts
├── kg/              # Domain models, graph storage, extraction
├── models/          # Pydantic schemas
├── static/js/       # 26 ES modules (chat, kg, jobs, upload)
└── templates/       # Jinja2 HTML

tests/               # 597 tests across 29 modules
data/                # Runtime storage
```

---

## Development

```bash
uv run python -m app.main              # Dev server → http://127.0.0.1:8000
uv run pytest                          # Run tests
uv run mypy .                          # Type check
uv run ruff check . && ruff format .   # Lint + format
```

---

## Configuration

**Required:**

```bash
ANTHROPIC_API_KEY=sk-ant-...    # Claude Agent SDK
OPENAI_API_KEY=sk-...            # gpt-4o-transcribe
```

**Optional:** See [CLAUDE.md](CLAUDE.md) for all configuration options.

---

## Documentation

| Document | Description |
|----------|-------------|
| [CLAUDE.md](CLAUDE.md) | Development guidelines, architecture patterns, configuration |
| [FRONTEND.md](FRONTEND.md) | Frontend ES modules architecture |
| [DOCKER.md](DOCKER.md) | Docker deployment guide |

---

## License

MIT
