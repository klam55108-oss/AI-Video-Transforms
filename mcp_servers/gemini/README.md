# Gemini CLI MCP Server

A Model Context Protocol (MCP) server that wraps the [Gemini CLI](https://github.com/google-gemini/gemini-cli), enabling Claude Code to leverage Google's Gemini AI capabilities through a standardized interface.

## Overview

This MCP server acts as a bridge between Claude Code and Gemini CLI, providing:

- **One-shot queries** - General questions and explanations
- **Code generation** - With language and context hints
- **Content analysis** - Code review, security, performance analysis
- **Multi-turn chat** - Persistent conversations with session management

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────┐
│   Claude Code   │  MCP    │  Gemini MCP      │  stdio  │  Gemini     │
│   (Client)      │◄───────►│  Server          │◄───────►│  CLI        │
└─────────────────┘         └──────────────────┘         └─────────────┘
```

## Architecture

### Components

| File | Purpose |
|------|---------|
| `server.py` | FastMCP server with 6 tool definitions |
| `client.py` | Async subprocess wrapper for Gemini CLI |
| `session_manager.py` | Multi-turn conversation state management |
| `GEMINI.md` | Project context file (auto-generated) |

### Server (`server.py`)

Defines the MCP server using [FastMCP](https://github.com/jlowin/fastmcp):

```python
from fastmcp import FastMCP

mcp = FastMCP(name="gemini-cli")

@mcp.tool
async def gemini_query(prompt: str, ...) -> str:
    """Send a general query to Gemini."""
    ...
```

### Client (`client.py`)

Executes Gemini CLI as an async subprocess:

```python
cmd = [
    "gemini",
    "--approval-mode", "yolo",      # Auto-approve all actions
    "--model", model,
    "--include-directories", str(_PROJECT_ROOT),  # Full project visibility
    prompt,
]

process = await asyncio.create_subprocess_exec(
    *cmd,
    cwd=_MODULE_DIR,  # Run from mcp_servers/gemini/ to find GEMINI.md
    ...
)
```

### Session Manager (`session_manager.py`)

Maintains conversation history for `gemini_chat`:

```python
class ChatSession:
    session_id: str
    history: list[dict]  # {"role": "user"|"assistant", "content": "..."}
```

## Available Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `gemini_query` | General queries | `prompt`, `model`, `timeout_seconds` |
| `gemini_code` | Code generation | `request`, `language`, `context` |
| `gemini_analyze` | Content analysis | `content`, `analysis_type`, `focus_areas` |
| `gemini_chat` | Multi-turn conversation | `message`, `session_id` |
| `gemini_chat_clear` | Clear chat session | `session_id` |
| `gemini_list_sessions` | List active sessions | - |

### Example Usage (from Claude Code)

```
User: Use gemini_query to explain async/await in Python

Claude: [calls mcp__gemini-cli__gemini_query with prompt]
```

## GEMINI.md Context System

This MCP server implements an automated context management system that ensures Gemini has full project knowledge while keeping configuration files organized.

### The Challenge

Gemini CLI loads context from `GEMINI.md` files, searching **upward** from its working directory. We needed to:

1. Store `GEMINI.md` in `mcp_servers/gemini/` (organizational preference)
2. Ensure it contains **full project context** (not just MCP server files)
3. Automate creation when missing

### The Solution

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        GEMINI.md CONTEXT FLOW                              │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STEP 1: DETECTION (SessionStart Hook)                               │   │
│  │                                                                     │   │
│  │   Claude Code starts                                                │   │
│  │         │                                                           │   │
│  │         ▼                                                           │   │
│  │   ┌─────────────────────────────────────────┐                       │   │
│  │   │ check-gemini-context.py                 │                       │   │
│  │   │                                         │                       │   │
│  │   │ Does mcp_servers/gemini/GEMINI.md exist?│                       │   │
│  │   └─────────────────┬───────────────────────┘                       │   │
│  │                     │                                               │   │
│  │          ┌──────────┴──────────┐                                    │   │
│  │          │                     │                                    │   │
│  │         YES                   NO                                    │   │
│  │          │                     │                                    │   │
│  │          ▼                     ▼                                    │   │
│  │      (skip)           Inject context prompting                      │   │
│  │                       Claude to create it                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STEP 2: CREATION (Full Project Visibility)                         │   │
│  │                                                                     │   │
│  │   Claude calls gemini_query("Analyze project, create GEMINI.md")   │   │
│  │         │                                                           │   │
│  │         ▼                                                           │   │
│  │   ┌─────────────────────────────────────────┐                       │   │
│  │   │ Gemini CLI runs with:                   │                       │   │
│  │   │                                         │                       │   │
│  │   │  cwd = mcp_servers/gemini/              │  ◄── For GEMINI.md    │   │
│  │   │  --include-directories = /project/root │  ◄── For file access  │   │
│  │   │                                         │                       │   │
│  │   └─────────────────┬───────────────────────┘                       │   │
│  │                     │                                               │   │
│  │                     ▼                                               │   │
│  │   Gemini sees ENTIRE project (app/, tests/, etc.)                  │   │
│  │   Creates GEMINI.md at PROJECT ROOT with full context              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STEP 3: MOVEMENT (PostToolUse Hook)                                 │   │
│  │                                                                     │   │
│  │   After gemini_* tool completes                                    │   │
│  │         │                                                           │   │
│  │         ▼                                                           │   │
│  │   ┌─────────────────────────────────────────┐                       │   │
│  │   │ move-gemini-context.py                  │                       │   │
│  │   │                                         │                       │   │
│  │   │ New GEMINI.md at root?                  │                       │   │
│  │   │ (newer than mcp_servers/gemini/ copy)   │                       │   │
│  │   └─────────────────┬───────────────────────┘                       │   │
│  │                     │                                               │   │
│  │          ┌──────────┴──────────┐                                    │   │
│  │          │                     │                                    │   │
│  │         NO                    YES                                   │   │
│  │          │                     │                                    │   │
│  │          ▼                     ▼                                    │   │
│  │      (skip)           Move file:                                    │   │
│  │                       /project/GEMINI.md                            │   │
│  │                           ──────▶                                   │   │
│  │                       /project/mcp_servers/gemini/GEMINI.md         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STEP 4: LOADING (Future Queries)                                    │   │
│  │                                                                     │   │
│  │   Subsequent gemini_* tool calls                                   │   │
│  │         │                                                           │   │
│  │         ▼                                                           │   │
│  │   ┌─────────────────────────────────────────┐                       │   │
│  │   │ Gemini CLI runs with:                   │                       │   │
│  │   │                                         │                       │   │
│  │   │  cwd = mcp_servers/gemini/              │                       │   │
│  │   │                                         │                       │   │
│  │   └─────────────────┬───────────────────────┘                       │   │
│  │                     │                                               │   │
│  │                     ▼                                               │   │
│  │   Gemini finds GEMINI.md in cwd                                    │   │
│  │   Loads FULL PROJECT CONTEXT                                       │   │
│  │   Responds with complete project knowledge                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Hook Configuration

Located in `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [{
          "type": "command",
          "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-gemini-context.py"
        }]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "mcp__gemini-cli__.*",
        "hooks": [{
          "type": "command",
          "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/move-gemini-context.py"
        }]
      }
    ]
  }
}
```

### Why This Design?

| Requirement | Solution |
|-------------|----------|
| GEMINI.md in `mcp_servers/gemini/` | PostToolUse hook moves file after creation |
| Full project context | `--include-directories` flag during creation |
| Gemini finds the file | `cwd` set to `mcp_servers/gemini/` |
| Automatic setup | SessionStart hook detects missing file |

## Configuration

### MCP Server Registration

In `.mcp.json`:

```json
{
  "mcpServers": {
    "gemini-cli": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_servers.gemini.server"],
      "env": {
        "GEMINI_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google AI API key for Gemini |

### Gemini CLI Installation

```bash
npm install -g @google/gemini-cli
```

## Development

### Running the Server Directly

```bash
uv run python -m mcp_servers.gemini.server
```

### Testing

```bash
# Test a query
uv run python -c "
import asyncio
from mcp_servers.gemini.client import get_client

async def test():
    client = get_client()
    response = await client.query('Hello, Gemini!')
    print(response.output if response.success else response.error)

asyncio.run(test())
"
```

## Troubleshooting

### Gemini CLI Not Found

```
Error: Gemini CLI not found. Install: npm install -g @google/gemini-cli
```

**Solution**: Install Gemini CLI globally or ensure it's in your PATH.

### API Key Missing

```
Error: GEMINI_API_KEY environment variable not set
```

**Solution**: Add `GEMINI_API_KEY` to `.mcp.json` env section or export it.

### GEMINI.md Not Loading

**Symptoms**: Gemini doesn't know about project structure.

**Check**:
1. File exists: `ls mcp_servers/gemini/GEMINI.md`
2. Hook registered: Check `.claude/settings.json`
3. Restart Claude Code session after hook changes

## Dependencies

- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework
- [Gemini CLI](https://github.com/google-gemini/gemini-cli) - Google's AI CLI tool
- Python 3.11+
- asyncio

## License

Part of the Agent Video to Data project.
