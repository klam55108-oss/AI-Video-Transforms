# Agent Video to Data

AI-powered video transcription toolkit with CLI and Web interfaces. Built with Claude Agent SDK and OpenAI Whisper.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-84%2F84%20passing-brightgreen.svg)](#testing)

## Features

- **Multi-source transcription** — Local files (mp4, mkv, avi, mov, webm) and YouTube URLs
- **Auto-segmentation** — Long videos split into 5-minute chunks automatically
- **Language detection** — Whisper auto-detects or accepts ISO 639-1 codes
- **Dual interface** — CLI for terminal, Web UI for browser
- **Session management** — Persistent chat history with cost tracking
- **Real-time cost display** — Cumulative API usage shown per message
- **Secure by design** — Path validation, permission controls, XSS protection

## Quick Start

```bash
# Clone and install
git clone https://github.com/costiash/agent-video-to-data.git
cd agent-video-to-data
uv sync

# Configure environment
cp .env.example .env
# Add your API keys to .env

# Run Web UI (recommended)
uv run python web_app.py
# Open http://127.0.0.1:8000

# Or run CLI
uv run python agent_video/agent.py
```

## Configuration

Create `.env` with:

```bash
ANTHROPIC_API_KEY=your-anthropic-key    # Required - Claude Agent SDK
OPENAI_API_KEY=your-openai-key          # Required - Whisper transcription
```

## Architecture

```
agent-video-to-data/
├── agent_video/              # Core transcription package
│   ├── agent.py              # CLI entry point
│   ├── server.py             # MCP server configuration
│   ├── transcribe_tool.py    # Whisper transcription tool
│   ├── file_tool.py          # Secure file operations
│   └── prompts/              # Versioned prompt templates
├── web_app.py                # FastAPI server (SessionActor pattern)
├── web_app_models.py         # Pydantic request/response schemas
├── storage.py                # Session & transcript persistence
├── cost_tracking.py          # API usage tracking with deduplication
├── permissions.py            # File operation permission handler
├── structured_outputs.py     # Agent response schemas
├── validators.py             # UUID & input validation
├── templates/index.html      # Chat UI
├── static/                   # Frontend assets (JS, CSS)
└── tests/                    # Comprehensive test suite
```

## Web API

### Chat Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat/init` | Initialize session, get agent greeting |
| `POST` | `/chat` | Send message, receive response with usage stats |
| `DELETE` | `/chat/{id}` | Close and cleanup session |
| `GET` | `/status/{id}` | Poll session status |

### Data Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/history` | List all chat sessions |
| `GET` | `/history/{id}` | Get session messages |
| `DELETE` | `/history/{id}` | Delete session |
| `GET` | `/transcripts` | List saved transcripts |
| `GET` | `/transcripts/{id}/download` | Download transcript |
| `DELETE` | `/transcripts/{id}` | Delete transcript |
| `POST` | `/upload` | Upload video (500MB max) |
| `GET` | `/cost` | Get global API usage stats |
| `GET` | `/cost/{id}` | Get session cost breakdown |

## MCP Tools

The agent exposes two tools via Model Context Protocol:

**`transcribe_video`** — Transcribe video/audio to text
- `video_source`: Local path or YouTube URL
- `output_file`: Optional save path
- `language`: Optional ISO 639-1 code

**`write_file`** — Write content securely
- `file_path`: Destination path
- `content`: Text content
- `overwrite`: Allow overwrite (default: false)

## Testing

```bash
# Run full test suite (84 tests)
uv run pytest

# With verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_api.py
```

### Test Coverage

| Module | Tests |
|--------|-------|
| `test_api.py` | API endpoints, validation, error handling |
| `test_storage.py` | Session/transcript persistence |
| `test_concurrency.py` | Race conditions, TTL cleanup |
| `test_async.py` | Event loops, timeouts, queue handling |
| `test_cost.py` | Usage tracking, deduplication |
| `test_permissions.py` | File access controls |
| `test_structured.py` | Response schema validation |

## Security

| Layer | Protection |
|-------|------------|
| **Input validation** | UUID v4 format, Pydantic validators |
| **File operations** | Blocked system paths, path traversal prevention |
| **Frontend** | DOMPurify XSS sanitization |
| **Uploads** | 500MB limit, extension allowlist |
| **Error handling** | Safe messages, no internal details leaked |
| **Permissions** | Configurable tool access controls |

## Code Quality

```bash
# Type checking (strict mode)
uv run mypy .

# Lint and format
uv run ruff check .
uv run ruff format .
```

All code passes mypy strict mode and ruff linting with zero warnings.

## Tech Stack

| Component | Technology |
|-----------|------------|
| AI Framework | Claude Agent SDK |
| Transcription | OpenAI Whisper API |
| Backend | FastAPI, Uvicorn, Pydantic |
| Frontend | Tailwind CSS, Vanilla JS, Phosphor Icons |
| Media Processing | MoviePy, Pydub, yt-dlp |
| Quality Tools | mypy, ruff, pytest |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| API key errors | Verify `.env` exists and contains valid keys |
| YouTube 403 | Rate limited; wait a few minutes |
| Long transcription | Normal for 2+ hour videos (auto-segments) |
| Port 8000 in use | `lsof -ti:8000 \| xargs kill -9` |

## License

MIT
