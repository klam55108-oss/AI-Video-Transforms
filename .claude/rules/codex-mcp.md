---
paths: mcp_servers/codex/**/*.py
---

# Codex MCP Server Patterns

## Framework
- Use FastMCP with `@mcp.tool` decorators
- Server defined in `mcp_servers/codex/server.py`
- Client wrapper in `mcp_servers/codex/client.py`

## OpenAI Responses API
```python
# Uses Responses API (not Chat Completions) for chain-of-thought
response = await client.responses.create(
    model="gpt-5.2",
    input=input_content,
    reasoning={"effort": effort.value},  # none, low, medium, high, xhigh
)
```

## GPT-5.2 Capabilities
- 400,000 context window for large codebases
- 128,000 max output tokens
- Aug 2025 knowledge cutoff
- Improved instruction following and accuracy

## Reasoning Effort Levels
- `none`: No chain-of-thought (GPT-5.2 default)
- `low`/`medium`: Moderate reasoning
- `high`: Default for our tools (thorough analysis)
- `xhigh`: Maximum reasoning

## Tool Design Philosophy
- `codex_query`: General high-reasoning queries
- `codex_analyzer`: Structured analysis with P0-P3 prioritization
- `codex_fixer`: Root-cause fixes only (NO monkey patches)

## File Collection
- Max 500KB per file, 2MB total for analysis
- Blocks system paths (`/etc`, `/usr`, `/bin`, `/var`, `/root`)
- Filters: no `__pycache__`, `node_modules`, `.git`

## Error Handling (CRITICAL)

- ALWAYS return `CodexResponse` dataclass with `success`, `output`, `error`
- ALWAYS retry with exponential backoff for timeouts/rate limits
- NEVER raise exceptions — return structured errors
- NEVER expose raw API errors to users

## System Prompts
- Defined in `prompts.py` with specialized instructions
- `ANALYZER_PROMPT`: Structured report format (Executive Summary → P0-P3 → Recommendations)
- `FIXER_PROMPT`: Root-cause philosophy (fix at source, not symptoms)
