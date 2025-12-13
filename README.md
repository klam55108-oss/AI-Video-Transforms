# Agent Video to Data

AI-powered video transcription with CLI and Web interfaces. Transcribe local videos and YouTube URLs using Claude Agent SDK and OpenAI Whisper.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-88%20passing-brightgreen.svg)](#testing)
[![Type Check](https://img.shields.io/badge/mypy-strict-blue.svg)](#development)

## Features

- **Multi-source transcription** — Local videos (mp4, mkv, avi, mov, webm) and YouTube URLs
- **Smart segmentation** — Auto-splits long videos into 5-minute chunks for Whisper
- **Transcript library** — Save, retrieve, and manage transcriptions with unique IDs
- **Dual interface** — Interactive CLI or responsive Web UI
- **Cost tracking** — Real-time token usage and cost display (per-session and global)
- **Secure by design** — Path validation, permission controls, XSS protection

## Quick Start

```bash
# Clone and install
git clone https://github.com/costiash/agent-video-to-data.git
cd agent-video-to-data
uv sync

# Configure
cp .env.example .env
# Add your API keys to .env

# Run
uv run python -m app.main              # Web UI at http://127.0.0.1:8000
uv run python -m app.agent.agent       # CLI agent
```

## Configuration

### Required Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...    # Claude API
OPENAI_API_KEY=sk-...            # Whisper API
```

### Optional (External MCP Servers)

```bash
GEMINI_API_KEY=...               # For Gemini CLI integration
```

## Project Structure

```
app/
├── agent/           # MCP tools + CLI entry point
│   ├── server.py    # 5 transcription tools
│   └── prompts/     # Versioned system prompts
├── core/            # Infrastructure
│   ├── session.py   # SessionActor (async concurrency)
│   ├── storage.py   # File persistence
│   └── permissions.py
├── models/          # Pydantic schemas
├── static/          # Frontend JS/CSS
├── templates/       # Jinja2 HTML
└── main.py          # FastAPI (15 endpoints)

mcp_servers/
├── gemini/          # Gemini CLI wrapper (6 tools)
└── codex/           # GPT-5.1-Codex-Max (3 tools)

tests/               # 88 tests
```

## MCP Tools

### Core Tools (app/agent)

| Tool | Description |
|------|-------------|
| `transcribe_video` | Transcribe local video or YouTube URL |
| `write_file` | Save content with security validation |
| `save_transcript` | Persist transcript, returns 8-char ID |
| `get_transcript` | Retrieve transcript by ID |
| `list_transcripts` | List all saved transcripts |

### External MCP Servers

| Server | Tools | Purpose |
|--------|-------|---------|
| **gemini/** | 6 | Gemini CLI for code generation, analysis, chat |
| **codex/** | 3 | High-reasoning analysis and root-cause bug fixing |

## Web API

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat/init` | Initialize session |
| POST | `/chat` | Send message |
| DELETE | `/chat/{id}` | Close session |
| GET | `/status/{id}` | Poll status |

### Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/transcripts` | List transcripts |
| GET | `/transcripts/{id}/download` | Download transcript |
| POST | `/upload` | Upload video (500MB max) |
| GET | `/cost` | Usage statistics |

<details>
<summary>Example Requests</summary>

```bash
# Initialize session
curl -X POST http://127.0.0.1:8000/chat/init \
  -H "Content-Type: application/json" \
  -d '{"session_id": "550e8400-e29b-41d4-a716-446655440000"}'

# Send message
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "...", "message": "Transcribe https://youtube.com/watch?v=..."}'

# Upload video
curl -X POST http://127.0.0.1:8000/upload \
  -F "file=@video.mp4" \
  -F "session_id=..."
```
</details>

## Development

```bash
# Testing (88 tests)
uv run pytest                    # All tests
uv run pytest -v                 # Verbose

# Code quality
uv run mypy .                    # Type checking (strict)
uv run ruff check .              # Linting
uv run ruff format .             # Formatting
```

### Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| `test_api.py` | 20 | Endpoints, validation |
| `test_storage.py` | 18 | Persistence, atomicity |
| `test_concurrency.py` | 9 | Race conditions, TTL |
| `test_async.py` | 11 | Timeouts, queues |
| `test_cost.py` | 8 | Usage tracking |
| `test_permissions.py` | 8 | Access controls |
| `test_structured.py` | 10 | Schema validation |

## Architecture

### SessionActor Pattern

The Web UI uses a queue-based actor model to handle Claude SDK's single-task requirement:

```
HTTP Handlers ──> input_queue ──> [SessionActor] ──> response_queue ──> Response
```

Each session runs in a dedicated asyncio task, preventing cancel scope errors when multiple requests interact with the same agent.

### Security

| Layer | Protection |
|-------|------------|
| Input | UUID v4 validation, Pydantic schemas |
| Files | Blocked system paths, traversal prevention |
| Frontend | DOMPurify XSS sanitization |
| Uploads | 500MB limit, extension allowlist |
| Sessions | 1-hour TTL, isolated storage |

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| AI | Claude Agent SDK, OpenAI Whisper |
| Backend | FastAPI, Uvicorn, Pydantic |
| Frontend | Tailwind CSS (CDN), Vanilla JS |
| Media | MoviePy, Pydub, yt-dlp |
| Quality | mypy (strict), ruff, pytest |

## License

MIT
