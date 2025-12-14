# Agent Video to Data

> Transform videos into searchable transcripts through an intelligent AI chat interface.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-230%20passing-brightgreen.svg)](#testing)
[![Type Check](https://img.shields.io/badge/mypy-strict-blue.svg)](#development)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

AI-powered video transcription web application built with **Claude Agent SDK** and **OpenAI gpt-4o-transcribe**.

---

## Features

| Feature | Description |
|---------|-------------|
| **Multi-Source Input** | Local videos (mp4, mkv, avi, mov, webm, m4v) and YouTube URLs |
| **Smart Segmentation** | Auto-splits long videos into chunks for transcription API compatibility |
| **Transcript Library** | Save, search, and download transcripts with unique 8-char IDs |
| **Real-Time Chat** | Markdown rendering, session isolation, light/dark themes |
| **Cost Tracking** | Per-session and global token usage with USD calculation |
| **Security First** | UUID validation, path traversal prevention, XSS protection |

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
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                      │
├───────────────────┬───────────────────┬─────────────────────┤
│    API Layer      │  Services Layer   │    Core Layer       │
│    ───────────    │  ───────────────  │    ──────────       │
│  • Routers        │  • SessionService │  • SessionActor     │
│  • Dependencies   │  • StorageService │  • StorageManager   │
│  • Error Handling │  • Transcription  │  • Cost Tracking    │
├───────────────────┴───────────────────┴─────────────────────┤
│              Claude Agent SDK + MCP Tools                   │
└─────────────────────────────────────────────────────────────┘
```

### SessionActor Pattern

The core architectural pattern ensuring thread-safe Claude SDK usage:

```
HTTP Request → Queue → [SessionActor] → Queue → Response
                            │
               Single asyncio task per session
               (prevents cancel scope errors)
```

**Why?** The Claude SDK client must run in a single asyncio task context. The actor model isolates each user session with dedicated input/response queues.

---

## Project Structure

```
app/
├── api/                    # HTTP layer
│   ├── routers/            # Endpoints: chat, transcripts, upload, history, cost
│   ├── deps.py             # Dependency injection
│   └── errors.py           # Exception handlers
├── services/               # Business logic
│   ├── session_service.py  # SessionActor lifecycle
│   ├── storage_service.py  # Storage wrapper
│   └── transcription_service.py
├── core/                   # Infrastructure
│   ├── session.py          # SessionActor (critical)
│   ├── storage.py          # Atomic file persistence
│   ├── cost_tracking.py    # Token usage aggregation
│   └── permissions.py      # Path validation
├── agent/                  # MCP tools & prompts
│   ├── server.py           # MCP server definition
│   ├── transcribe_tool.py  # Whisper integration
│   └── prompts/            # Versioned system prompts
├── models/                 # Pydantic schemas
├── static/                 # Frontend assets
└── templates/              # Jinja2 HTML

mcp_servers/                # External MCP servers (for Claude Code)
├── codex/                  # GPT-5.1-Codex-Max integration
└── gemini/                 # Gemini CLI integration

tests/                      # 230 tests across 13 modules
data/                       # Runtime storage (sessions, transcripts)
```

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web dashboard |
| `/chat/init` | POST | Initialize session with greeting |
| `/chat` | POST | Send message to agent |
| `/chat/{session_id}` | DELETE | Close session |
| `/status/{session_id}` | GET | Poll agent status |
| `/transcripts` | GET | List saved transcripts |
| `/transcripts/{id}` | GET | Download transcript |
| `/transcripts/{id}` | DELETE | Delete transcript |
| `/history` | GET | List session history |
| `/history/{session_id}` | GET/DELETE | Session details |
| `/upload` | POST | Upload video (500MB max) |
| `/cost` | GET | Global cost statistics |
| `/cost/{session_id}` | GET | Session cost details |

---

## MCP Tools

Tools exposed to the Claude agent during conversations:

| Tool | Description |
|------|-------------|
| `transcribe_video` | Convert video/audio to text via gpt-4o-transcribe |
| `write_file` | Save content to filesystem (with path validation) |
| `save_transcript` | Persist transcript with unique ID |
| `get_transcript` | Retrieve transcript by ID |
| `list_transcripts` | List all saved transcripts |

---

## Development

### Commands

```bash
# Type checking (strict mode)
uv run mypy .

# Lint & format
uv run ruff check . && ruff format .

# Run tests
uv run pytest

# All quality checks (run before commits)
uv run mypy . && uv run ruff check . && uv run ruff format . && uv run pytest
```

### Testing

**230 tests** across 13 modules covering:

| Category | Tests | Coverage |
|----------|-------|----------|
| API & Integration | 81 | Endpoints, validation, E2E flows |
| Storage | 18 | Persistence, atomicity, data integrity |
| Services | 47 | SessionService, TranscriptionService |
| Concurrency | 9 | Race conditions, TTL cleanup |
| Async | 11 | Timeouts, queue behavior |
| Security | 8 | Permissions, path validation |
| MCP Server | 54 | Codex tools, error handling |

---

## Configuration

### Required Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...    # Claude Agent SDK
OPENAI_API_KEY=sk-...            # Whisper API + Codex MCP
```

### Defaults

| Setting | Value |
|---------|-------|
| Upload max size | 500MB |
| Session TTL | 1 hour |
| Response timeout | 5 minutes |
| Cleanup interval | 5 minutes |
| Video formats | mp4, mkv, avi, mov, webm, m4v |

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

---

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Backend** | FastAPI, Uvicorn, Pydantic |
| **AI** | Claude Agent SDK, OpenAI gpt-4o-transcribe |
| **Media** | Pydub, yt-dlp, FFmpeg |
| **Frontend** | Vanilla JS, Tailwind CSS, Marked.js, DOMPurify |
| **Quality** | mypy (strict), ruff, pytest |
| **Storage** | File-based JSON with atomic writes |

---

## License

MIT
