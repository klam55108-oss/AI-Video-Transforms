---
paths: app/agent/**/*.py
---

# MCP Tool Development

## Tool Structure

```python
from claude_agent_sdk import tool

@tool(name="my_tool", description="...", schema={"param": str})
async def my_tool(args: dict[str, Any]) -> dict[str, Any]:
    ...
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

```python
async def my_tool(args: dict[str, Any]) -> dict[str, Any]:
    try:
        result = await do_work(args)
        return {"content": [{"type": "text", "text": result}]}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

## Tool Naming

- Allowlist format: `mcp__<server-name>__<tool-name>`
- Example: `mcp__video-tools__transcribe_video`
