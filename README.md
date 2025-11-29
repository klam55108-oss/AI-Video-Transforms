# Agent Video to Data

An interactive AI-powered video transcription agent built with the Claude Agent SDK and OpenAI Whisper. Transcribe local video files or YouTube URLs through a conversational interface, then analyze the results with follow-up queries.

## Features

- **Multi-source support** — Transcribe local video files (mp4, mkv, avi, mov, webm) or YouTube URLs
- **Automatic language detection** — Whisper auto-detects the spoken language, or specify one manually
- **Long video handling** — Automatically segments audio into 5-minute chunks for reliable processing
- **Conversational interface** — Multi-turn agent that guides you through transcription and analysis
- **Built-in analysis** — Summarize transcriptions, extract key points, or view full text

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- OpenAI API key (for Whisper transcription)
- Anthropic API key (for Claude agent)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/agent-video-to-data.git
cd agent-video-to-data

# Install dependencies
uv sync
```

### Configuration

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
```

### Usage

```bash
uv run python agent_video/agent.py
```

The agent will:

1. Greet you and ask for a video source (file path or YouTube URL)
2. Optionally ask about the video's language
3. Transcribe the video using Whisper
4. Offer follow-up options: summarize, extract key points, or show full text
5. Continue the conversation for additional requests

## Project Structure

```text
agent-video-to-data/
├── agent_video/
│   ├── agent.py              # Interactive agent entry point
│   ├── server.py             # MCP server configuration
│   ├── transcribe_tool.py    # Core transcription logic
│   └── prompts/
│       ├── registry.py       # Prompt version management
│       └── video_transcription.py
├── .claude/                  # Claude Code configuration
├── main.py                   # Placeholder entry point
├── pyproject.toml            # Project dependencies
└── uv.lock                   # Dependency lock file
```

## Architecture

The project uses three main components:

- **agent.py** — Runs the interactive conversation loop using the Claude Agent SDK. Validates environment variables, manages the session, and formats output.

- **server.py** — Creates an MCP (Model Context Protocol) server that exposes the transcription tool to Claude. This allows the agent to call the tool during conversation.

- **transcribe_tool.py** — The core transcription engine. Handles:
  - YouTube downloads via yt-dlp
  - Audio extraction via MoviePy
  - Audio segmentation via Pydub
  - Transcription via OpenAI Whisper API

## Transcription Tool

The `transcribe_video` tool accepts these parameters:

| Parameter      | Required | Description                            |
|----------------|----------|----------------------------------------|
| `video_source` | Yes      | Local file path or YouTube URL         |
| `output_file`  | No       | Path to save transcription as `.txt`   |
| `language`     | No       | ISO 639-1 code (e.g., `en`, `es`, `ru`)|

**Example inputs:**

```text
/path/to/video.mp4
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://youtu.be/dQw4w9WgXcQ
```

## Development

```bash
# Install dependencies
uv sync

# Run type checking
uv run mypy .

# Run linter
uv run ruff check .

# Format code
uv run ruff format .

# Run tests
uv run pytest
```

## Tech Stack

| Category         | Tools                          |
|------------------|--------------------------------|
| AI Framework     | Claude Agent SDK, Anthropic API|
| Transcription    | OpenAI Whisper                 |
| Video Processing | MoviePy, yt-dlp                |
| Audio Processing | Pydub                          |
| Type Checking    | mypy                           |
| Linting          | ruff                           |

## Troubleshooting

**"OPENAI_API_KEY not set"**
Ensure your `.env` file exists and contains a valid OpenAI API key.

**"ANTHROPIC_API_KEY not set"**
Ensure your `.env` file exists and contains a valid Anthropic API key.

**YouTube download fails with 403**
The tool uses yt-dlp with mobile client spoofing, but YouTube occasionally blocks requests. Try again or use a different video.

**Transcription fails for long videos**
The tool automatically segments audio into 5-minute chunks. If a single segment exceeds 25MB, it reduces quality automatically. For very long videos (2+ hours), expect longer processing times.

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run `uv run ruff check .` and `uv run mypy .` before committing
4. Submit a pull request
