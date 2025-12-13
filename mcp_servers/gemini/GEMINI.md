# Agent Video to Data

## Project Overview

A Python video transcription web application. Built with the **Claude Agent SDK** and **OpenAI Whisper**, providing MCP-based tools for transcribing local videos and YouTube URLs. The system features smart segmentation for long videos, a transcript library, and real-time cost tracking.

## Tech Stack

- **Language**: Python 3.11+
- **Package Manager**: uv
- **AI Framework**: Claude Agent SDK (MCP support)
- **Web Framework**: FastAPI, Uvicorn, Jinja2
- **Frontend**: Tailwind CSS (CDN), Vanilla JS, DOMPurify
- **Transcription**: OpenAI Whisper API
- **Video/Audio**: MoviePy, Pydub, yt-dlp
- **Storage**: File-based JSON persistence
- **Quality**: mypy (strict), ruff, pytest

## Project Structure

```
app/
├── api/                  # API layer
│   ├── deps.py           # Dependency injection providers
│   ├── errors.py         # Centralized error handling
│   └── routers/          # Endpoint routers (chat, history, transcripts, etc.)
├── services/             # Service layer
│   ├── session_service.py    # SessionActor lifecycle management
│   ├── storage_service.py    # Storage operations wrapper
│   └── transcription_service.py # Transcription orchestration
├── agent/                # MCP tools
│   ├── server.py         # MCP server definition (tools)
│   ├── prompts/          # Versioned system prompts
│   ├── file_tool.py      # File I/O tools
│   ├── transcribe_tool.py # Video transcription logic
│   └── transcript_storage_tools.py # Library management tools
├── core/                 # Shared infrastructure
│   ├── session.py        # SessionActor pattern (async isolation)
│   ├── storage.py        # File-based persistence (data/sessions)
│   ├── cost_tracking.py  # API usage aggregation
│   └── permissions.py    # Path validation & security
├── models/               # Pydantic schemas
│   ├── api.py            # Web API response models
│   ├── requests.py       # Web API request models
│   ├── service.py        # Service layer models
│   └── structured.py     # Agent output structures
├── ui/                   # UI routes
│   └── routes.py         # GET / endpoint
├── static/               # Frontend assets (JS, CSS)
├── templates/            # Jinja2 HTML templates
└── main.py               # FastAPI application entry point (slim)

data/                     # Persistent storage (ignored by git)
├── sessions/             # Chat history JSONs
└── transcripts/          # Transcript metadata & files

mcp_servers/              # Independent MCP servers
└── gemini/               # Gemini-specific MCP tools (if applicable)

tests/                    # Pytest suite
├── test_api.py           # Endpoint tests
├── test_async.py         # Concurrency tests
└── ...
```

## Development Commands

**Run Application:**
```bash
# Web UI (http://127.0.0.1:8000)
uv run python -m app.main
```

**Quality & Testing:**
```bash
# Run all tests
uv run pytest

# Type checking (Strict)
uv run mypy .

# Linting and Formatting
uv run ruff check .
uv run ruff format .
```

## Code Conventions

- **Type Hints**: Mandatory for all functions (args and returns). Use `list[str]` over `List[str]`.
- **Async/Await**: Heavy usage of `asyncio`. The web app uses the **SessionActor** pattern to isolate agent state per user session.
- **Docstrings**: Google-style docstrings for all modules and functions.
- **Path Handling**: Use `pathlib.Path` exclusively; avoid `os.path`.
- **Error Handling**: 
    - MCP tools return `{"content": [...], "isError": True}` on failure.
    - Web endpoints raise `HTTPException`.
    - Never crash the main agent loop.

## Architecture Patterns

### SessionActor Pattern (`app/core/session.py`)
To manage state in the stateless web environment, each user session is wrapped in a `SessionActor`.
- **Structure**: An asyncio Task running a continuous loop.
- **Queues**: `input_queue` (HTTP -> Agent) and `response_queue` (Agent -> HTTP).
- **Isolation**: Each actor owns its `ClaudeSDKClient` instance, preventing context bleeding.
- **Lifecycle**: Managed by `active_sessions` dictionary with TTL-based cleanup.

### MCP Server Integration
- Tools are defined in `app/agent/server.py` using `@tool` decorators.
- The agent connects to these tools via `ClaudeAgentOptions(mcp_servers=...)`.
- **Key Tools**:
    - `transcribe_video`: Handles download (yt-dlp) and transcription (Whisper).
    - `write_file`: Controlled file writing with path validation.
    - `save_transcript` / `get_transcript`: Manages the local transcript library.

### Security
- **Path Validation**: `app/core/permissions.py` ensures file operations stay within allowed directories (`uploads/`, `data/`).
- **Input Sanitization**: Frontend uses `DOMPurify` before rendering Markdown.
- **Upload Limits**: 500MB max file size, restricted extensions.

## Important Context
- **Storage**: Data is stored locally in `data/` as JSON. This is designed for single-instance deployment/local use.
- **Concurrency**: The system handles long-running transcriptions (minutes) while maintaining responsive chat. `asyncio.to_thread` is used for blocking I/O (video processing).
- **Specs**: Detailed specifications for backend and frontend improvements are in `specs/`. Refer to `backend-spec.md` and `frontend-spec.md` for recent/planned changes.
