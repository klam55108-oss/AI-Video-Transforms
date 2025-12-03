# Agent Video to Data

AI-powered video transcription toolkit with CLI and Web interfaces. Built with Claude Agent SDK and OpenAI Whisper.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Features

| Feature | Description |
|---------|-------------|
| **Multi-source** | Local files (mp4, mkv, avi, mov, webm) and YouTube URLs |
| **Auto-segmentation** | Long videos split into 5-minute chunks automatically |
| **Language detection** | Whisper auto-detects or accepts ISO 639-1 codes |
| **Dual interface** | CLI for terminal, Web UI for browser |
| **Session history** | Persist and restore chat sessions |
| **Secure file handling** | Path validation, size limits, XSS protection |

## Quick Start

```bash
# Clone and install
git clone https://github.com/costiash/agent-video-to-data.git
cd agent-video-to-data
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run CLI
uv run python agent_video/agent.py

# Or run Web UI
uv run python web_app.py
# Open http://127.0.0.1:8000
```

## Configuration

Create `.env` with:

```bash
ANTHROPIC_API_KEY=your-anthropic-key    # Required - Claude Agent SDK
OPENAI_API_KEY=your-openai-key          # Required - Whisper transcription
```

## Project Structure

```
agent-video-to-data/
├── agent_video/           # Core transcription package
│   ├── agent.py           # CLI entry point
│   ├── server.py          # MCP server config
│   ├── transcribe_tool.py # Whisper transcription
│   └── file_tool.py       # Safe file operations
├── web_app.py             # FastAPI server (SessionActor pattern)
├── storage.py             # Session/transcript persistence
├── templates/index.html   # Chat UI (Tailwind + Phosphor Icons)
├── static/
│   ├── script.js          # Frontend logic
│   └── style.css          # Custom styles
├── tests/                 # Pytest test suite
├── data/                  # Runtime session storage
└── uploads/               # User file uploads
```

## Web API

### Chat Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat/init` | Initialize session, get greeting |
| `POST` | `/chat` | Send message, receive response |
| `DELETE` | `/chat/{id}` | Close and cleanup session |
| `GET` | `/status/{id}` | Poll session status (ready/processing) |

### History & Transcripts

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/history` | List all chat sessions |
| `GET` | `/history/{id}` | Get full session messages |
| `DELETE` | `/history/{id}` | Delete session history |
| `GET` | `/transcripts` | List saved transcripts |
| `GET` | `/transcripts/{id}/download` | Download transcript file |
| `DELETE` | `/transcripts/{id}` | Delete transcript |
| `POST` | `/upload` | Upload video file (500MB max) |

## MCP Tools

The agent exposes two tools via the Model Context Protocol:

**`transcribe_video`** — Transcribe video/audio to text
- `video_source` (required): Local path or YouTube URL
- `output_file` (optional): Save transcript to file
- `language` (optional): ISO 639-1 code (e.g., `en`, `es`, `ja`)

**`write_file`** — Write content to file safely
- `file_path` (required): Destination path
- `content` (required): Text to write
- `overwrite` (optional): Allow overwrite (default: false)

## Development

```bash
# Install dependencies
uv sync

# Run tests (57 tests)
uv run pytest

# Type checking
uv run mypy .

# Lint and format
uv run ruff check .
uv run ruff format .
```

### Test Coverage

| Test File | Coverage |
|-----------|----------|
| `test_api.py` | API endpoints, validation, error handling |
| `test_storage.py` | Session/transcript persistence |
| `test_concurrency.py` | Async operations, race conditions |
| `test_async.py` | Event loops, queue handling |

## Security

- **UUID v4 validation** on all session/transcript IDs
- **Pydantic validators** for request payload sanitization
- **DOMPurify** XSS protection on frontend markdown rendering
- **Path traversal prevention** in file operations
- **500MB file size limit** on uploads
- **Safe error messages** (no internal details leaked)

## Tech Stack

| Layer | Technology |
|-------|------------|
| AI | Claude Agent SDK, OpenAI Whisper |
| Backend | FastAPI, Uvicorn, Pydantic |
| Frontend | Tailwind CSS, Vanilla JS, Phosphor Icons |
| Media | MoviePy, Pydub, yt-dlp |
| Quality | mypy, ruff, pytest |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ANTHROPIC_API_KEY not set` | Check `.env` file exists and is readable |
| YouTube 403 errors | Rate limited; wait or try different video |
| Long transcription time | Normal for 2+ hour videos; auto-segments |
| Port 8000 in use | Kill existing process: `fuser -k 8000/tcp` |

## License

MIT
