# Agent Video to Data

AI-powered video transcription toolkit with CLI and Web interfaces. Built with Claude Agent SDK and OpenAI Whisper.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-88%20passing-brightgreen.svg)](#testing)
[![Type Check](https://img.shields.io/badge/mypy-strict-blue.svg)](#code-quality)

## Features

- **Multi-source transcription** - Local videos (mp4, mkv, avi, mov, webm, m4v) and YouTube URLs
- **Smart segmentation** - Auto-splits long videos into 5-minute chunks
- **Transcript library** - Save, retrieve, and manage transcriptions by ID
- **Dual interface** - CLI for terminal, Web UI for browser
- **Real-time cost tracking** - Per-session and cumulative API usage display
- **Secure by design** - Path validation, permission controls, XSS protection

## Quick Start

```bash
# Clone and install
git clone https://github.com/costiash/agent-video-to-data.git
cd agent-video-to-data
uv sync

# Configure environment
cp .env.example .env
# Add your API keys to .env

# Run Web UI
uv run python -m app.main          # http://127.0.0.1:8000

# Or run CLI
uv run python -m app.agent.agent
```

## Configuration

Create `.env` with:

```bash
ANTHROPIC_API_KEY=your-key    # Claude Agent SDK
OPENAI_API_KEY=your-key       # Whisper transcription
```

## Project Structure

```
app/
├── agent/           # Agent core
│   ├── agent.py     # CLI entry point
│   ├── server.py    # MCP server (5 tools)
│   └── prompts/     # Versioned system prompts
├── core/            # Shared modules
│   ├── session.py   # SessionActor pattern
│   ├── storage.py   # File-based persistence
│   └── permissions.py
├── models/          # Pydantic schemas
└── main.py          # FastAPI web app
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `transcribe_video` | Transcribe local video or YouTube URL |
| `write_file` | Save content to file with security controls |
| `save_transcript` | Persist transcription to library, returns ID |
| `get_transcript` | Retrieve full transcript by ID (lazy loading) |
| `list_transcripts` | Show available transcripts with metadata |

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
| GET | `/history` | List sessions |
| GET/DELETE | `/history/{id}` | Get/delete session |
| GET | `/transcripts` | List transcripts |
| GET | `/transcripts/{id}/download` | Download file |
| DELETE | `/transcripts/{id}` | Delete transcript |
| POST | `/upload` | Upload video (500MB max) |
| GET | `/cost`, `/cost/{id}` | Usage statistics |

## Testing

```bash
uv run pytest           # 88 tests
uv run pytest -v        # Verbose output
```

| Test Module | Coverage |
|-------------|----------|
| `test_api.py` | 20 tests - endpoints, validation |
| `test_storage.py` | 18 tests - persistence, atomicity |
| `test_concurrency.py` | 9 tests - race conditions, TTL |
| `test_async.py` | 11 tests - timeouts, queues |
| `test_cost.py` | 8 tests - usage tracking |
| `test_permissions.py` | 8 tests - access controls |
| `test_structured.py` | 10 tests - schema validation |
| `test_api_integration.py` | 4 tests - integration flows |

## Security

| Layer | Protection |
|-------|------------|
| Input | UUID v4 validation, Pydantic schemas |
| Files | Blocked system paths (`/etc`, `/usr`, `/bin`), traversal prevention |
| Frontend | DOMPurify XSS sanitization, CSP headers |
| Uploads | 500MB limit, extension allowlist |
| Sessions | TTL expiration (1 hour), isolated storage |

## Code Quality

```bash
uv run mypy .           # Strict type checking
uv run ruff check .     # Linting
uv run ruff format .    # Formatting
```

All code passes mypy strict mode and ruff with zero warnings.

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| AI | Claude Agent SDK, OpenAI Whisper |
| Backend | FastAPI, Uvicorn, Pydantic |
| Frontend | Tailwind CSS, Vanilla JS |
| Media | MoviePy, Pydub, yt-dlp |
| Quality | mypy, ruff, pytest |

## License

MIT
