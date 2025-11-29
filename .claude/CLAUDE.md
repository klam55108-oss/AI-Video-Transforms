# Agent Video to Data

## Project Overview

This is a Python project for video-to-data processing using the Claude Agent SDK.

## Tech Stack

- **Language**: Python 3.11+
- **Package Manager**: uv
- **AI Framework**: Claude Agent SDK (anthropic, claude-agent-sdk)
- **Video Processing**: MoviePy
- **Audio Processing**: Pydub
- **Data Handling**: Pandas, NumPy
- **Type Checking**: mypy
- **Linting/Formatting**: ruff

## Common Commands

```bash
# Install dependencies
uv sync

# Add a new dependency
uv add <package>

# Run the application
uv run python main.py

# Run tests
uv run pytest

# Type checking
uv run mypy .

# Lint code
uv run ruff check .

# Format code
uv run ruff format .
```

## Code Style

- Use type hints for all function signatures
- Follow PEP 8 conventions
- Use descriptive variable and function names
- Keep functions focused and single-purpose
- Write docstrings for public functions and classes

## Project Structure

```
agent-video-to-data/
├── .claude/           # Claude Code configuration
│   ├── settings.json  # Permissions and settings
│   └── CLAUDE.md      # This file (project memory)
├── main.py            # Application entry point
├── pyproject.toml     # Project configuration
├── uv.lock            # Dependency lock file
└── README.md          # Project documentation
```

## Development Guidelines

- Run `uv run ruff check .` before committing
- Run `uv run mypy .` to catch type errors
- Keep dependencies minimal and well-justified
- Document any non-obvious code decisions
