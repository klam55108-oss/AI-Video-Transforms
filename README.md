# Agent Video to Data

AI-powered video transcription agent built with the Claude Agent SDK and OpenAI Whisper. Transcribe local videos or YouTube URLs through a conversational interface.

## Features

- **Multi-source support** — Local files (mp4, mkv, avi, mov, webm) and YouTube URLs
- **Auto language detection** — Whisper detects spoken language, or specify manually
- **Long video handling** — Auto-segments audio into 5-minute chunks
- **Two interfaces** — CLI for terminal users, Web UI for browser-based interaction
- **Built-in analysis** — Summarize, extract key points, save to files

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- OpenAI API key (Whisper)
- Anthropic API key (Claude)

### Installation

```bash
git clone https://github.com/yourusername/agent-video-to-data.git
cd agent-video-to-data
uv sync
```

### Configuration

Create a `.env` file:

```bash
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
```

### Usage

**CLI Interface:**
```bash
uv run python agent_video/agent.py
```

**Web Interface:**
```bash
uv run python web_app.py
# Open http://127.0.0.1:8000
```

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                      Entry Points                               │
├─────────────────────────┬──────────────────────────────────────┤
│  agent.py (CLI)         │  web_app.py (FastAPI)                │
│  Multi-turn terminal    │  SessionActor pattern                │
│  conversation           │  REST API + chat UI                  │
└─────────────────────────┴──────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────┐
│                  server.py (MCP Server)                         │
│           Exposes tools via create_sdk_mcp_server()             │
└────────────────────────────┬───────────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
┌───────────────────────┐        ┌───────────────────────┐
│  transcribe_tool.py   │        │     file_tool.py      │
│  - YouTube download   │        │  - Path validation    │
│  - Audio extraction   │        │  - Safe file writing  │
│  - Whisper API        │        │                       │
└───────────────────────┘        └───────────────────────┘
```

## Project Structure

```
agent-video-to-data/
├── agent_video/
│   ├── __init__.py           # Package exports
│   ├── agent.py              # CLI entry point
│   ├── server.py             # MCP server configuration
│   ├── transcribe_tool.py    # Transcription tool
│   ├── file_tool.py          # File writing tool
│   └── prompts/
│       ├── registry.py       # PromptRegistry
│       └── video_transcription.py
├── web_app.py                # FastAPI web server
├── templates/
│   └── index.html            # Chat UI template
├── static/
│   ├── script.js             # Frontend logic
│   └── style.css             # Custom styles
├── pyproject.toml
└── uv.lock
```

## API Reference

### MCP Tools

**transcribe_video**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `video_source` | Yes | Local path or YouTube URL |
| `output_file` | No | Save transcription to file |
| `language` | No | ISO 639-1 code (e.g., `en`, `es`) |

**write_file**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `file_path` | Yes | Destination path |
| `content` | Yes | Text content |
| `overwrite` | No | Allow overwrite (default: false) |

### Web API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Chat UI |
| POST | `/chat/init` | Initialize session, get greeting |
| POST | `/chat` | Send message, receive response |
| DELETE | `/chat/{session_id}` | Close session |

## Development

```bash
uv sync                 # Install dependencies
uv run mypy .           # Type checking
uv run ruff check .     # Lint
uv run ruff format .    # Format
uv run pytest           # Test
```

## Tech Stack

| Category | Tools |
|----------|-------|
| AI Framework | Claude Agent SDK |
| Transcription | OpenAI Whisper |
| Web Framework | FastAPI, Uvicorn, Jinja2 |
| Video/Audio | MoviePy, Pydub, yt-dlp |
| Frontend | Tailwind CSS, Vanilla JS |
| Quality | mypy, ruff |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| API key errors | Verify `.env` file exists with valid keys |
| YouTube 403 | Rate limited; retry or use different video |
| Long video timeout | Normal for 2+ hour videos; tool auto-segments |

## License

MIT
