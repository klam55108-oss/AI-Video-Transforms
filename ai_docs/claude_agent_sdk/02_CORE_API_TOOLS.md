# Claude Agent SDK - Core API & Custom Tools

> **Reference:** Python SDK v0.1.0+ (Docs v0.5.0)
> **Focus:** query(), ClaudeSDKClient, Custom Tools, MCP, Multi-Agent Systems

---

## Table of Contents

1. [Core API: query() vs ClaudeSDKClient](#core-api-query-vs-claudesdkclient)
2. [Streaming vs Single Message Mode](#streaming-vs-single-message-mode)
3. [Custom Tools with @tool Decorator](#custom-tools-with-tool-decorator)
4. [MCP Server Integration](#mcp-server-integration)
5. [Multi-Agent Systems (Subagents)](#multi-agent-systems-subagents)
6. [System Prompts & Configuration](#system-prompts--configuration)

---

## Core API: query() vs ClaudeSDKClient

### Comparison Table

| Feature | `query()` | `ClaudeSDKClient` |
|---------|-----------|-------------------|
| **Session** | New each time | Persistent |
| **Conversation** | Single exchange | Multi-turn |
| **Streaming Input** | ✅ | ✅ |
| **Interrupts** | ❌ | ✅ |
| **Hooks** | ✅ (via options) | ✅ |
| **Custom Tools** | ✅ (via mcp_servers) | ✅ |
| **Plugins** | ✅ (via options) | ✅ |
| **Continue Chat** | ❌ New session each time | ✅ Maintains conversation |
| **Use Case** | One-off tasks, automation | Interactive apps |

### When to Use Each

**Use `query()` for:**
- One-off questions without conversation history
- Independent tasks that don't require context
- Automation scripts with hooks and custom tools
- Stateless environments (Lambda functions)
- CI/CD pipelines and batch processing

**Use `ClaudeSDKClient` for:**
- Continuing conversations with context
- Follow-up questions building on previous responses
- Interactive applications and chat interfaces
- When you need interrupt support
- Long-running sessions with multiple exchanges

---

## Using query() - One-Shot Tasks

### Basic Usage

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def one_shot_task():
    options = ClaudeAgentOptions(
        system_prompt="You are an expert Python developer",
        permission_mode='acceptEdits',
        cwd="/path/to/project",
        allowed_tools=["Read", "Write", "Edit", "Bash"],
        max_turns=10
    )

    async for message in query(
        prompt="Create a Flask web server with a /health endpoint",
        options=options
    ):
        print(message)

asyncio.run(one_shot_task())
```

### With Structured Output

```python
from claude_agent_sdk import query, ClaudeAgentOptions
from pydantic import BaseModel

class Issue(BaseModel):
    severity: str  # 'low', 'medium', 'high'
    description: str
    file: str

class AnalysisResult(BaseModel):
    summary: str
    issues: list[Issue]
    score: int

async for message in query(
    prompt="Analyze the codebase for security issues",
    options=ClaudeAgentOptions(
        output_format={
            "type": "json_schema",
            "schema": AnalysisResult.model_json_schema()
        }
    )
):
    # Check for successful structured output
    if message.type == "result" and message.subtype == "success":
        if hasattr(message, 'structured_output') and message.structured_output:
            result = AnalysisResult.model_validate(message.structured_output)
            print(f"Score: {result.score}")
            for issue in result.issues:
                print(f"[{issue.severity}] {issue.file}: {issue.description}")

    # Handle structured output failures
    elif message.type == "result" and message.subtype == "error_max_structured_output_retries":
        print("Error: Could not produce valid structured output")
```

**When to Use Structured Outputs:**
- Use when you need validated JSON after an agent completes a multi-turn workflow with tools
- For single API calls without tool use, use the standard Anthropic API structured outputs

---

## Using ClaudeSDKClient - Multi-Turn Conversations

### Basic Multi-Turn Example

```python
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock

async def multi_turn_conversation():
    options = ClaudeAgentOptions(
        system_prompt="You are a helpful coding assistant",
        allowed_tools=["Read", "Grep", "Glob"]
    )

    async with ClaudeSDKClient(options) as client:
        # First message
        await client.query("What files are in the src/ directory?")
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"Claude: {block.text}")

        # Follow-up (Claude remembers context!)
        await client.query("Which of those files contain async functions?")
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"Claude: {block.text}")

asyncio.run(multi_turn_conversation())
```

### Using Interrupts

```python
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async def interruptible_task():
    options = ClaudeAgentOptions(
        allowed_tools=["Bash"],
        permission_mode="acceptEdits"
    )

    async with ClaudeSDKClient(options) as client:
        # Start a long-running task
        await client.query("Count from 1 to 100 slowly")

        # Let it run briefly
        await asyncio.sleep(2)

        # Interrupt!
        await client.interrupt()
        print("Task interrupted!")

        # Continue with something else
        await client.query("Just say hello instead")
        async for message in client.receive_response():
            print(message)

asyncio.run(interruptible_task())
```

---

## Streaming vs Single Message Mode

### Streaming Input Mode (Recommended)

Streaming input allows dynamic message generation, image attachments, and hooks support.

```python
import asyncio
from claude_agent_sdk import ClaudeSDKClient

async def message_generator():
    """Generate messages dynamically."""
    yield {"type": "text", "text": "Analyze the following data:"}
    await asyncio.sleep(0.5)
    yield {"type": "text", "text": "Temperature: 25°C, Humidity: 60%"}
    await asyncio.sleep(0.5)
    yield {"type": "text", "text": "What patterns do you see?"}

async def streaming_example():
    async with ClaudeSDKClient() as client:
        await client.query(message_generator())
        async for message in client.receive_response():
            print(message)

        # Follow-up in same session
        await client.query("Should we be concerned about these readings?")
        async for message in client.receive_response():
            print(message)

asyncio.run(streaming_example())
```

### Comparison

| Feature | Streaming Mode | Single Message Mode |
|---------|----------------|---------------------|
| Image uploads | ✅ | ❌ |
| Queued messages | ✅ | ❌ |
| Real-time interrupts | ✅ | ❌ |
| Hooks support | ✅ | ❌ |
| Custom MCP tools | ✅ | ✅ |
| Session resumption | ✅ | ✅ (via `resume`) |

---

## Custom Tools with @tool Decorator

### Basic Tool Definition

```python
from claude_agent_sdk import tool
from typing import Any

@tool(
    "tool_name",           # Unique identifier
    "Tool description",    # What it does (shown to Claude)
    {"param": str}         # Input schema
)
async def my_tool(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{
            "type": "text",
            "text": "Result here"
        }]
    }
```

### Input Schema Options

**Option 1: Simple Type Mapping (Recommended)**
```python
{"name": str, "count": int, "enabled": bool, "items": list}
```

**Option 2: JSON Schema (Complex Validation)**
```python
{
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "count": {"type": "integer", "minimum": 0, "maximum": 100},
        "format": {"type": "string", "enum": ["json", "csv", "xml"]}
    },
    "required": ["name", "count"]
}
```

### Complete Weather Tool Example

```python
from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeSDKClient, ClaudeAgentOptions
from typing import Any
import aiohttp

@tool(
    "get_weather",
    "Get current weather for a location",
    {"city": str, "units": str}
)
async def get_weather(args: dict[str, Any]) -> dict[str, Any]:
    city = args["city"]
    units = args.get("units", "metric")

    try:
        api_key = "your-api-key"
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&units={units}&appid={api_key}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Error: Could not fetch weather for {city}"
                        }]
                    }
                data = await response.json()

        temp = data["main"]["temp"]
        description = data["weather"][0]["description"]

        return {
            "content": [{
                "type": "text",
                "text": f"Weather in {city}: {temp}°{'C' if units == 'metric' else 'F'}, {description}"
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error fetching weather: {str(e)}"
            }]
        }
```

### Error Handling Best Practices

```python
@tool("risky_operation", "Perform a risky operation", {"target": str})
async def risky_operation(args: dict[str, Any]) -> dict[str, Any]:
    try:
        result = await perform_operation(args["target"])
        return {
            "content": [{
                "type": "text",
                "text": f"Success: {result}"
            }]
        }
    except ValidationError as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Validation Error: {str(e)}"
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Unexpected Error: {str(e)}"
            }]
        }
```

**Key Rules:**
- Always return the `{"content": [{"type": "text", "text": "..."}]}` format
- Never raise exceptions that crash the agent loop
- Handle all errors gracefully within the tool

---

## MCP Server Integration

### Creating an SDK MCP Server

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("add", "Add two numbers", {"a": float, "b": float})
async def add(args):
    return {
        "content": [{
            "type": "text",
            "text": f"Sum: {args['a'] + args['b']}"
        }]
    }

@tool("multiply", "Multiply two numbers", {"a": float, "b": float})
async def multiply(args):
    return {
        "content": [{
            "type": "text",
            "text": f"Product: {args['a'] * args['b']}"
        }]
    }

# Create the server
calculator = create_sdk_mcp_server(
    name="calculator",
    version="2.0.0",
    tools=[add, multiply]
)

# Use with Claude
options = ClaudeAgentOptions(
    mcp_servers={"calc": calculator},
    allowed_tools=["mcp__calc__add", "mcp__calc__multiply"]
)
```

### Tool Naming Convention

When exposed to Claude, MCP tools follow this pattern:
```
mcp__{server_name}__{tool_name}
```

Example:
- Server: `my-tools`
- Tool: `get_weather`
- Full name: `mcp__my-tools__get_weather`

### Connecting External MCP Servers

```python
options = ClaudeAgentOptions(
    mcp_servers={
        # Stdio-based server
        "playwright": {
            "command": "npx",
            "args": ["@playwright/mcp@latest"]
        },
        # Python module server
        "filesystem": {
            "command": "python",
            "args": ["-m", "mcp_server_filesystem"],
            "env": {
                "ALLOWED_PATHS": "/Users/me/projects"
            }
        },
        # SSE-based remote server
        "remote_api": {
            "type": "sse",
            "url": "https://api.example.com/mcp",
            "headers": {"Authorization": "Bearer ${API_TOKEN}"}
        },
        # HTTP-based remote server
        "http_service": {
            "type": "http",
            "url": "https://api.example.com/mcp",
            "headers": {"X-API-Key": "${API_KEY}"}
        }
    }
)
```

### MCP Resource Management

MCP servers can expose resources that Claude can list and read:

```python
from claude_agent_sdk import query, ClaudeAgentOptions

async for message in query(
    prompt="What resources are available from the database server?",
    options=ClaudeAgentOptions(
        mcp_servers={
            "database": {
                "command": "python",
                "args": ["-m", "mcp_server_database"]
            }
        },
        allowed_tools=["mcp__list_resources", "mcp__read_resource"]
    )
):
    if hasattr(message, 'type') and message.type == "result":
        print(message.result)
```

### MCP Error Handling

Handle MCP connection failures gracefully:

```python
from claude_agent_sdk import query, ClaudeAgentOptions

async for message in query(
    prompt="Process data",
    options=ClaudeAgentOptions(
        mcp_servers={"data-processor": data_server}
    )
):
    # Check MCP server status on init
    if message.type == "system" and message.subtype == "init":
        mcp_servers = message.data.get("mcp_servers", [])
        failed_servers = [
            s for s in mcp_servers
            if s.get("status") != "connected"
        ]

        if failed_servers:
            print(f"Warning: Failed to connect to MCP servers: {failed_servers}")

    # Handle execution errors
    if message.type == "result" and message.subtype == "error_during_execution":
        print("Execution failed")
```

---

## Plugins

Plugins allow you to extend the SDK with custom functionality that can be shared across projects.

### What Plugins Can Include

- **Commands**: Custom slash commands
- **Agents**: Specialized subagents for specific tasks
- **Skills**: Model-invoked capabilities Claude uses autonomously
- **Hooks**: Event handlers that respond to tool use
- **MCP servers**: External tool integrations

### Loading Plugins

```python
from claude_agent_sdk import query, ClaudeAgentOptions

async for message in query(
    prompt="Hello",
    options=ClaudeAgentOptions(
        plugins=[
            {"type": "local", "path": "./my-plugin"},
            {"type": "local", "path": "/absolute/path/to/another-plugin"}
        ]
    )
):
    print(message)
```

### Plugin Structure

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json          # Required: plugin manifest
├── commands/                 # Custom slash commands
│   └── custom-cmd.md
├── agents/                   # Custom agents
│   └── specialist.md
├── skills/                   # Agent Skills
│   └── my-skill/
│       └── SKILL.md
├── hooks/                    # Event handlers
│   └── hooks.json
└── .mcp.json                # MCP server definitions
```

### Verifying Plugin Installation

```python
async for message in query(
    prompt="Hello",
    options=ClaudeAgentOptions(
        plugins=[{"type": "local", "path": "./my-plugin"}]
    )
):
    if message.type == "system" and message.subtype == "init":
        print("Plugins:", message.data.get("plugins"))
        print("Commands:", message.data.get("slash_commands"))
```

### Using Plugin Commands

Plugin commands are namespaced: `plugin-name:command-name`

```python
async for message in query(
    prompt="/my-plugin:custom-command",
    options=ClaudeAgentOptions(
        plugins=[{"type": "local", "path": "./my-plugin"}]
    )
):
    print(message)
```

---

## Multi-Agent Systems (Subagents)

### Why Use Subagents?

| Benefit | Description |
|---------|-------------|
| **Context Management** | Separate context prevents information overload |
| **Parallelization** | Multiple subagents run concurrently |
| **Specialized Instructions** | Tailored prompts for specific expertise |
| **Tool Restrictions** | Limited tools reduce unintended actions |

### Defining Subagents Programmatically

```python
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

async def multi_agent_system():
    options = ClaudeAgentOptions(
        agents={
            # Security-focused code reviewer
            'security-reviewer': AgentDefinition(
                description='Use for security vulnerability analysis. MUST BE USED when reviewing authentication, authorization, or data handling code.',
                prompt='''You are a security expert specializing in code review.

When analyzing code:
1. Check for OWASP Top 10 vulnerabilities
2. Identify injection risks (SQL, XSS, Command)
3. Review authentication/authorization logic
4. Check for sensitive data exposure
5. Verify input validation

Provide severity ratings: CRITICAL, HIGH, MEDIUM, LOW''',
                tools=['Read', 'Grep', 'Glob'],
                model='sonnet'
            ),

            # Test runner
            'test-runner': AgentDefinition(
                description='Runs and analyzes test suites. Invoke when tests need to be executed.',
                prompt='''You are a test execution specialist.

Responsibilities:
- Run test suites using pytest
- Analyze test output and failures
- Identify flaky tests
- Suggest fixes for failing tests''',
                tools=['Bash', 'Read', 'Grep'],
                model='haiku'  # Cheaper model for simpler tasks
            ),

            # Documentation writer
            'doc-writer': AgentDefinition(
                description='Use for generating or updating documentation.',
                prompt='''You are a technical documentation specialist.

Guidelines:
- Write clear, concise documentation
- Include code examples where appropriate
- Follow Google-style docstrings for Python''',
                tools=['Read', 'Write', 'Edit', 'Glob'],
                model='sonnet'
            )
        }
    )

    async for message in query(
        prompt="Review the authentication module for security issues, then run the tests",
        options=options
    ):
        print(message)
```

### AgentDefinition Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | `str` | Yes | When to use this agent |
| `prompt` | `str` | Yes | System prompt for the agent |
| `tools` | `list[str]` | No | Allowed tools (inherits all if omitted) |
| `model` | `"sonnet" \| "opus" \| "haiku" \| "inherit"` | No | Model override |

### Common Tool Combinations

```python
# Read-only agents (analysis, review)
read_only_tools = ['Read', 'Grep', 'Glob']

# Test execution agents
test_tools = ['Bash', 'Read', 'Grep']

# Code modification agents
code_mod_tools = ['Read', 'Edit', 'Write', 'Grep', 'Glob']

# Full access agents (use sparingly)
full_tools = ['Read', 'Write', 'Edit', 'Bash', 'Grep', 'Glob']
```

### Filesystem-Based Agents (Alternative)

Create `.claude/agents/code-reviewer.md`:

```markdown
---
name: code-reviewer
description: Expert code review specialist. Use for quality and security reviews.
tools: Read, Grep, Glob
---

You are an expert code reviewer.

For every code submission:
1. Check for bugs and security issues
2. Evaluate performance
3. Suggest improvements
4. Rate code quality (1-10)
```

**Note:** Programmatically defined agents take precedence over filesystem-based agents with the same name.

---

## System Prompts & Configuration

### System Prompt Options

**Important:** The SDK uses an **empty system prompt by default** for maximum flexibility.

```python
from claude_agent_sdk import ClaudeAgentOptions

# Option 1: Empty (SDK default)
options = ClaudeAgentOptions()

# Option 2: Claude Code preset (recommended for coding tasks)
options = ClaudeAgentOptions(
    system_prompt={
        "type": "preset",
        "preset": "claude_code"
    }
)

# Option 3: Claude Code preset + additions
options = ClaudeAgentOptions(
    system_prompt={
        "type": "preset",
        "preset": "claude_code",
        "append": "Always include type hints in Python code."
    }
)

# Option 4: Fully custom
options = ClaudeAgentOptions(
    system_prompt="""You are a Python coding specialist.
Guidelines:
- Write clean, documented code
- Use type hints
- Follow PEP 8"""
)
```

### Loading CLAUDE.md Files

**Critical:** The `claude_code` preset does NOT automatically load CLAUDE.md files.

```python
# Must specify setting_sources to load CLAUDE.md
options = ClaudeAgentOptions(
    system_prompt={
        "type": "preset",
        "preset": "claude_code"
    },
    setting_sources=["project"]  # Required to load CLAUDE.md!
)
```

### Setting Sources

| Source | Location | Description |
|--------|----------|-------------|
| `"user"` | `~/.claude/settings.json` | Global user settings |
| `"project"` | `.claude/settings.json` | Shared project settings |
| `"local"` | `.claude/settings.local.json` | Local (gitignored) settings |

```python
# Default behavior (v0.1.0+): NO settings loaded!
options = ClaudeAgentOptions()

# Load all settings (legacy behavior)
options = ClaudeAgentOptions(
    setting_sources=["user", "project", "local"]
)

# Load only project settings (good for CI)
options = ClaudeAgentOptions(
    setting_sources=["project"]
)
```

### Settings Precedence

When multiple sources are loaded (highest to lowest):
1. Local settings (`.claude/settings.local.json`)
2. Project settings (`.claude/settings.json`)
3. User settings (`~/.claude/settings.json`)

Programmatic options always override filesystem settings.

---

*See also:*
- *[03_SESSION_PERMISSIONS_HOSTING.md](./03_SESSION_PERMISSIONS_HOSTING.md) for session management and security*
- *[05_FILE_CHECKPOINTING.md](./05_FILE_CHECKPOINTING.md) for file versioning and rollback*
