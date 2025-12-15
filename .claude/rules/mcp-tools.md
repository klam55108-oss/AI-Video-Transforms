---
paths: app/agent/**/*.py, app/kg/tools/**/*.py
---

# MCP Tool Development

## Tool Locations

| Location | Tools |
|----------|-------|
| `app/agent/` | transcribe_video, write_file, save_transcript, get_transcript, list_transcripts |
| `app/kg/tools/` | Bootstrap tools, extraction tools |

## Tool Structure

```python
from typing import Any

async def my_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Tool description for agent context."""
    try:
        result = await do_work(args)
        return {"content": [{"type": "text", "text": result}]}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

## Return Format (CRITICAL)

```python
# ✅ Success
return {"content": [{"type": "text", "text": "Result message"}]}

# ✅ Error — ALWAYS return structured errors
return {"success": False, "error": "Human-readable error message"}

# ❌ NEVER raise exceptions — they crash the agent loop!
raise ValueError("...")  # NEVER do this
```

## Error Handling Rules

- ALWAYS wrap tool body in try/except
- ALWAYS return structured error responses
- NEVER let exceptions escape the tool function
- NEVER use bare `raise` without catching

## Tool Registration (server.py)

```python
# Tools registered in app/agent/server.py
mcp_server = Server("video-transcription")

# Add tool handlers
mcp_server.add_tool("transcribe_video", transcribe_video_handler)
mcp_server.add_tool("save_transcript", save_transcript_handler)
# ... etc
```

## Transcription Tools

| Tool | Description |
|------|-------------|
| `transcribe_video` | Video/audio → text via gpt-4o-transcribe |
| `save_transcript` | Persist with unique 8-char ID |
| `get_transcript` | Retrieve by ID (lazy loading) |
| `list_transcripts` | List all saved transcripts |
| `write_file` | Save content with path validation |

## Knowledge Graph Tools

| Tool | Description |
|------|-------------|
| `create_kg_project` | Create new KG project |
| `bootstrap_kg_project` | Infer domain from first transcript |
| `extract_to_kg` | Extract entities/relationships |
| `list_kg_projects` | List projects with stats |
| `get_kg_stats` | Get graph statistics |

## Tool Naming (for allowlists)

- Format: `mcp__<server-name>__<tool-name>`
- Example: `mcp__video-tools__transcribe_video`

## Best Practices

- Keep tools focused on single responsibility
- Validate inputs before processing
- Return informative error messages
- Log errors for debugging (don't expose to user)
- Use async for I/O-bound operations
