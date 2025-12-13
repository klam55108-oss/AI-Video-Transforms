---
paths: app/agent/**/*.py
---

# MCP Tool Development

## Tool Structure
- Use `@tool(name, description, schema)` decorator from `claude_agent_sdk`
- Tool functions must be `async def fn(args: dict[str, Any]) -> dict[str, Any]`
- Create servers via `create_sdk_mcp_server(name, version, tools=[...])`

## Return Format
```python
# Success
return {"content": [{"type": "text", "text": "Result message"}]}

# Error (never raise exceptions)
return {"success": False, "error": "Human-readable error message"}
```

## Tool Naming
- Allowlist format: `mcp__<server-name>__<tool-name>`
- Example: `mcp__video-tools__transcribe_video`

## Error Handling
- Catch ALL exceptions inside tool functions
- Return structured error responses
- Never let exceptions escape and crash the agent loop

## Schema Definition
- Use simple type mapping: `{"param": str, "count": int}`
- Or full JSON Schema for complex validation
