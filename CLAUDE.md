# Agent Video to Data

## Project Overview

A Python video-to-data processing toolkit built with the Claude Agent SDK. The project provides MCP-based tools for transcribing video content using OpenAI's Whisper model, with support for both local video files and YouTube URLs.

## Tech Stack

- **Language**: Python 3.11+
- **Package Manager**: uv (universal virtualenv)
- **AI Framework**: Claude Agent SDK (claude-agent-sdk)
- **Transcription**: OpenAI Whisper API
- **Video Processing**: MoviePy for audio extraction
- **Audio Processing**: Pydub for audio segmentation
- **YouTube Support**: yt-dlp for video downloading
- **Type Checking**: mypy with strict mode
- **Linting/Formatting**: ruff

## Project Structure

```
agent-video-to-data/
├── agent_video/           # Main package
│   ├── __init__.py        # Package exports: video_tools_server, transcribe_video
│   ├── agent.py           # Interactive multi-turn agent entry point
│   ├── server.py          # MCP server configuration
│   ├── transcribe_tool.py # Core transcription tool implementation
│   └── prompts/           # Versioned prompt management system
│       ├── __init__.py    # Prompt registry exports
│       ├── registry.py    # PromptVersion dataclass and registry
│       └── video_transcription.py  # Agent system prompt
├── .claude/               # Claude Code configuration
│   ├── settings.json      # Permissions and tool allowlists
│   └── CLAUDE.md          # Claude Code project memory (legacy location)
├── CLAUDE.md              # Project memory (primary location)
├── pyproject.toml         # Project configuration and dependencies
├── uv.lock                # Locked dependency versions
└── README.md              # User-facing documentation
```

## Common Commands

```bash
# Install dependencies
uv sync

# Run the interactive transcription agent
uv run python ./agent_video/agent.py

# Add a new dependency
uv add <package>

# Run tests
uv run pytest

# Type checking (strict mode)
uv run mypy .

# Lint code
uv run ruff check .

# Format code
uv run ruff format .

# Run linter with auto-fix
uv run ruff check . --fix
```

## Environment Variables

Required environment variables (create `.env` file from `.env.example`):

- `ANTHROPIC_API_KEY`: Required for Claude Agent SDK
- `OPENAI_API_KEY`: Required for Whisper transcription

## Architecture Patterns

### MCP Server Pattern
- Tools are created using the `@tool` decorator from `claude_agent_sdk`
- MCP servers are created via `create_sdk_mcp_server()` with named tools
- The server is consumed in `ClaudeAgentOptions.mcp_servers` dict
- Tools are allowlisted in `ClaudeAgentOptions.allowed_tools` using format: `mcp__<server-name>__<tool-name>`

### Prompt Management
- Prompts are versioned using `PromptVersion` dataclass in `agent_video/prompts/registry.py`
- Register prompts via `register_prompt(name, version, content, description)`
- Retrieve prompts via `get_prompt(name)` or `get_prompt_content(name)`
- System prompts follow XML structure with `<role>`, `<context>`, `<workflow>`, `<constraints>` tags

### Async Patterns
- Tools must be `async def` functions accepting `args: dict[str, Any]`
- Agent client uses async context manager: `async with ClaudeSDKClient(options)`
- Response streaming via `async for message in client.receive_response()`

## Code Style

- Use type hints for all function signatures including return types
- Follow PEP 8 conventions
- Use descriptive variable names (avoid single-letter names except for indices)
- Keep functions focused and single-purpose (max ~50 lines)
- Write docstrings for all public functions and classes using Google style
- Use `from __future__ import annotations` for forward references
- Prefer `pathlib.Path` over `os.path` for new code

## Type Annotations

- Use `str | None` instead of `Optional[str]`
- Use `list[str]` instead of `List[str]` (Python 3.9+ style)
- Add `# type: ignore[import-untyped]` for untyped third-party libs (moviepy, pydub)
- Tool functions return `dict[str, Any]` with MCP response format

## Testing Guidelines

- Test files go in `tests/` directory mirroring `agent_video/` structure
- Use pytest fixtures for common setup (mock API clients, temp files)
- Mock external API calls (OpenAI, YouTube downloads) in unit tests
- Integration tests can use real APIs with appropriate rate limiting

## Error Handling

- Return structured error responses from tools: `{"success": False, "error": "message"}`
- Never raise exceptions that would crash the agent loop
- Provide actionable error messages with troubleshooting steps
- Validate required environment variables early in execution

## Git Workflow

- Branch naming: `feature/<name>`, `fix/<name>`, `refactor/<name>`
- Run `uv run ruff check .` and `uv run mypy .` before committing
- Keep commits focused on single logical changes
- Write descriptive commit messages with context

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `claude-agent-sdk` | MCP server and tool creation |
| `anthropic` | Claude API client |
| `openai` | Whisper transcription API |
| `moviepy` | Extract audio from video files |
| `pydub` | Split audio into segments |
| `yt-dlp` | Download YouTube video audio |
| `python-dotenv` | Load environment variables |

## Important Implementation Details

- Audio is split into 5-minute segments to stay under OpenAI's 25MB limit
- If segment exceeds 23MB, audio is downsampled to 16kHz mono
- YouTube downloads use Android/iOS player clients for better compatibility
- Temporary files are cleaned up automatically via `tempfile.TemporaryDirectory`
