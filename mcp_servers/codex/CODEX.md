# GPT-5.1-Codex-Max MCP Server

MCP server providing GPT-5.1-Codex-Max integration for Claude Code.

## Tools

### 1. `codex_query`
General-purpose queries with high reasoning capabilities.

**Use for:**
- One-off questions about code
- Code generation requests
- Explanations of complex concepts
- Algorithm design

**Parameters:**
- `prompt` (required): The question or request
- `reasoning_effort`: 'none', 'low', 'medium', 'high', 'xhigh' (default: 'high')
- `timeout_seconds`: Max wait time (default: 300s)

### 2. `codex_analyzer`
Comprehensive code analysis for single files or complete projects.

**Use for:**
- Code quality reviews
- Architecture analysis
- Security audits
- Performance analysis
- Pre-merge code reviews

**Parameters:**
- `target` (required): File or directory path relative to project root
- `focus_areas`: Comma-separated focus areas ('security', 'performance', 'architecture', 'testing', 'quality', 'all')
- `analysis_type`: 'quick', 'comprehensive', 'deep' (default: 'comprehensive')
- `timeout_seconds`: Max wait time (default: 600s)

**Output:** Structured report with prioritized findings (P0-P3) and actionable recommendations.

### 3. `codex_fixer`
Root-cause bug fixing (NOT monkey patches).

**Use for:**
- Bug fixes that address root causes
- Refactoring problematic code patterns
- Security vulnerability fixes
- Performance issue resolution

**Parameters:**
- `target` (required): File or directory containing the issue
- `issues` (required): Detailed description of the problem (include error messages, stack traces)
- `fix_scope`: 'root_cause', 'minimal', 'comprehensive' (default: 'root_cause')
- `timeout_seconds`: Max wait time (default: 600s)

**Output:** Root cause analysis with before/after code fixes and testing guidance.

## Configuration

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "codex": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_servers.codex.server"],
      "env": {
        "OPENAI_API_KEY": "your-openai-api-key"
      }
    }
  }
}
```

## Requirements

- `OPENAI_API_KEY` environment variable
- `openai>=2.8.1` Python package (already in pyproject.toml)
- `fastmcp>=2.0.0` (already in pyproject.toml)

## Usage Examples

### Analyze a module
```
codex_analyzer(target="app/core/", focus_areas="architecture,quality")
```

### Fix a specific bug
```
codex_fixer(
    target="app/api/endpoints.py",
    issues="TypeError: 'NoneType' object is not subscriptable on line 45 when session expires"
)
```

### Ask a coding question
```
codex_query(prompt="How should I implement retry logic with exponential backoff in Python?")
```
