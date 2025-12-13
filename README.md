# Agent Video to Data

AI-powered video transcription web application built with **Claude Agent SDK** and **OpenAI Whisper**.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-199%20passing-brightgreen.svg)](#development)
[![Type Check](https://img.shields.io/badge/mypy-strict-blue.svg)](#development)

Transform local videos and YouTube URLs into searchable transcripts through an intelligent chat interface.

## Features

- **Multi-Source Transcription** — Local videos (mp4, mkv, avi, mov, webm, m4v) and YouTube URLs
- **Smart Segmentation** — Auto-splits long videos into chunks for Whisper API
- **Transcript Library** — Save, search, and download transcripts with unique IDs
- **Real-Time Chat UI** — Markdown rendering, session isolation, toast notifications
- **Cost Tracking** — Per-session and global token usage with USD calculation
- **Security Built-in** — UUID validation, path traversal prevention, XSS protection

## Quick Start

```bash
# Install
git clone https://github.com/costiash/agent-video-to-data.git
cd agent-video-to-data
uv sync

# Configure (.env file)
ANTHROPIC_API_KEY=sk-ant-...    # Required
OPENAI_API_KEY=sk-...            # Required

# Run
uv run python -m app.main        # http://127.0.0.1:8000
```

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     FastAPI Application                       │
├──────────────────────────────────────────────────────────────┤
│  API Layer          │  Services Layer     │  Core Layer      │
│  ────────────       │  ───────────────    │  ────────────    │
│  • Routers          │  • SessionService   │  • SessionActor  │
│  • Dependencies     │  • StorageService   │  • StorageManager│
│  • Error Handling   │  • Transcription    │  • Cost Tracking │
├──────────────────────────────────────────────────────────────┤
│                   Claude Agent SDK + MCP Tools                │
└──────────────────────────────────────────────────────────────┘
```

### SessionActor Pattern

Queue-based actor model ensuring thread-safe Claude SDK usage:

```
HTTP Request → input_queue → [SessionActor Task] → response_queue → Response
                                    │
                          Single asyncio task per session
```

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web dashboard |
| `/chat/init` | POST | Initialize session |
| `/chat` | POST | Send message to agent |
| `/chat/{id}` | DELETE | Close session |
| `/status/{id}` | GET | Poll agent status |
| `/transcripts` | GET | List all transcripts |
| `/transcripts/{id}/download` | GET | Download transcript |
| `/transcripts/{id}` | DELETE | Delete transcript |
| `/history` | GET | List session history |
| `/history/{id}` | GET/DELETE | Session details |
| `/upload` | POST | Upload video (500MB max) |
| `/cost` | GET | Global cost statistics |
| `/cost/{id}` | GET | Session cost details |

## MCP Tools

| Tool | Description |
|------|-------------|
| `transcribe_video` | Convert video/audio to text via Whisper |
| `write_file` | Save content to filesystem |
| `save_transcript` | Persist transcript with unique ID |
| `get_transcript` | Retrieve transcript by ID |
| `list_transcripts` | List all saved transcripts |

## Project Structure

```
app/
├── api/              # FastAPI routers & dependency injection
│   ├── routers/      # chat, transcripts, upload, history, cost
│   ├── deps.py       # Service providers
│   └── errors.py     # Exception handlers
├── services/         # Business logic layer
│   ├── session_service.py
│   ├── storage_service.py
│   └── transcription_service.py
├── core/             # Infrastructure
│   ├── session.py    # SessionActor (critical pattern)
│   ├── storage.py    # File-based persistence
│   └── cost_tracking.py
├── agent/            # MCP tools & system prompts
├── models/           # Pydantic schemas
├── ui/               # Frontend route
├── static/           # JS, CSS
└── templates/        # Jinja2 HTML

data/                 # Runtime storage (auto-created)
├── sessions/         # Chat history JSON
└── transcripts/      # Saved transcript files

tests/                # 199 tests
```

## Development

```bash
uv run mypy .                           # Type checking (strict)
uv run ruff check . && ruff format .    # Lint + format
uv run pytest                           # Run all 199 tests
```

### Test Coverage

| Module | Tests | Focus |
|--------|-------|-------|
| API & Integration | 81 | Endpoints, validation, service layer |
| Storage | 18 | Persistence, atomicity |
| Concurrency | 9 | Race conditions, TTL cleanup |
| Async | 11 | Timeouts, queue behavior |
| Cost Tracking | 8 | Usage aggregation |
| Permissions | 8 | Access controls |
| Structured Output | 10 | Schema validation |
| MCP Server | 54 | Codex tools, security |

## Security

| Layer | Protection |
|-------|------------|
| Input | UUID v4 validation, Pydantic schemas |
| Files | System path blocklist, traversal prevention |
| Frontend | DOMPurify XSS sanitization |
| Uploads | 500MB limit, extension allowlist |
| Sessions | 1-hour TTL, auto-cleanup |

## Tech Stack

| Category | Technologies |
|----------|-------------|
| **Backend** | FastAPI, Uvicorn, Pydantic |
| **AI/ML** | Claude Agent SDK, OpenAI Whisper |
| **Media** | MoviePy, Pydub, yt-dlp |
| **Frontend** | Vanilla JS, Tailwind CSS (CDN), DOMPurify |
| **Quality** | mypy (strict), ruff, pytest |
| **Storage** | File-based JSON (atomic writes) |

## License

MIT
