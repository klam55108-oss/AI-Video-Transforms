# Claude Agent SDK for Python - Complete Reference Guide

> **Version:** Based on official documentation as of November 2025
> **SDK Package:** `claude-agent-sdk`
> **Official Docs:** https://docs.anthropic.com/en/docs/agent-sdk

---

## Table of Contents

1. [Overview & Architecture](#1-overview--architecture)
2. [Installation & Setup](#2-installation--setup)
3. [Core API: query() vs ClaudeSDKClient](#3-core-api-query-vs-claudesdkclient)
4. [Multi-Agent Systems (Subagents)](#4-multi-agent-systems-subagents)
5. [Custom Tools & MCP Servers](#5-custom-tools--mcp-servers)
6. [Session Management](#6-session-management)
7. [Permissions & Security](#7-permissions--security)
8. [Monitoring & Cost Tracking](#8-monitoring--cost-tracking)
9. [Structured Outputs](#9-structured-outputs)
10. [System Prompts & Configuration](#10-system-prompts--configuration)
11. [Production Hosting](#11-production-hosting)
12. [Best Practices & Patterns](#12-best-practices--patterns)
13. [Quick Reference Tables](#13-quick-reference-tables)
14. [Complete Examples](#14-complete-examples)

---

## 1. Overview & Architecture

### What is the Claude Agent SDK?

The Claude Agent SDK is built on the same agent harness that powers **Claude Code**. It provides:

- **Automatic Context Management** - Compaction prevents running out of context
- **Prompt Caching** - Automatic performance optimizations
- **Rich Tool Ecosystem** - File operations, code execution, web search, MCP extensibility
- **Advanced Permissions** - Fine-grained control over agent capabilities
- **Session Management** - Built-in state persistence and resumption

### Key Differences from Standard API

| Aspect | Standard Claude API | Claude Agent SDK |
|--------|---------------------|------------------|
| State | Stateless | Stateful (long-running process) |
| Tools | Manual implementation | Built-in + extensible |
| Context | Manual management | Automatic compaction |
| Sessions | Not supported | Full session management |
| Multi-agent | Not supported | Native subagent support |

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Your Application                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  query()    │  │ ClaudeSDK   │  │  Custom MCP Tools   │  │
│  │  (one-shot) │  │ Client      │  │  (@tool decorator)  │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
├─────────┴────────────────┴───────────────────┴──────────────┤
│                    Claude Agent SDK                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  • Session Management    • Permission System          │   │
│  │  • Subagent Orchestration • Cost Tracking             │   │
│  │  • Context Compaction    • Tool Execution             │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    Claude API (Anthropic)                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Installation & Setup

### Installation

```bash
pip install claude-agent-sdk
```

### Authentication

```python
import os

# Option 1: Direct API Key (recommended)
os.environ["ANTHROPIC_API_KEY"] = "your-api-key"

# Option 2: Amazon Bedrock
os.environ["CLAUDE_CODE_USE_BEDROCK"] = "1"
# + Configure AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, etc.)

# Option 3: Google Vertex AI
os.environ["CLAUDE_CODE_USE_VERTEX"] = "1"
# + Configure Google Cloud credentials
```

### Minimal Example

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    async for message in query(
        prompt="Hello, Claude!",
        options=ClaudeAgentOptions()
    ):
        print(message)

asyncio.run(main())
```

---

## 3. Core API: query() vs ClaudeSDKClient

### Comparison Table

| Feature | `query()` | `ClaudeSDKClient` |
|---------|-----------|-------------------|
| Session | New each time | Persistent |
| Conversation | Single exchange | Multi-turn |
| Streaming Input | ✅ | ✅ |
| Interrupts | ❌ | ✅ |
| Hooks | ❌ | ✅ |
| Custom Tools | ❌ | ✅ |
| Use Case | One-off tasks | Interactive apps |

### Using query() - One-Shot Tasks

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

### Using ClaudeSDKClient - Multi-Turn Conversations

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

### Streaming Input Mode (Required for MCP Tools)

```python
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async def streaming_input_example():
    async def message_generator():
        yield {"type": "text", "text": "Analyze the following data:"}
        await asyncio.sleep(0.5)
        yield {"type": "text", "text": "Temperature: 25°C, Humidity: 60%"}
        yield {"type": "text", "text": "What patterns do you see?"}

    async with ClaudeSDKClient() as client:
        await client.query(message_generator())
        async for message in client.receive_response():
            print(message)

asyncio.run(streaming_input_example())
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

## 4. Multi-Agent Systems (Subagents)

### Why Use Subagents?

| Benefit | Description |
|---------|-------------|
| **Context Management** | Separate context prevents information overload |
| **Parallelization** | Multiple subagents can run concurrently |
| **Specialized Instructions** | Tailored prompts for specific expertise |
| **Tool Restrictions** | Limited tools reduce unintended actions |

### AgentDefinition Structure

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class AgentDefinition:
    description: str  # REQUIRED: When to use this agent
    prompt: str       # REQUIRED: System prompt for the agent
    tools: list[str] | None = None  # Optional: Allowed tools
    model: Literal["sonnet", "opus", "haiku", "inherit"] | None = None
```

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

            # Test runner and analyzer
            'test-runner': AgentDefinition(
                description='Use for running and analyzing test suites. Invoke when tests need to be executed or coverage analyzed.',
                prompt='''You are a test execution specialist.

Responsibilities:
- Run test suites using pytest
- Analyze test output and failures
- Identify flaky tests
- Suggest fixes for failing tests
- Report on code coverage''',
                tools=['Bash', 'Read', 'Grep'],
                model='haiku'  # Cheaper model for simpler tasks
            ),

            # Documentation writer
            'doc-writer': AgentDefinition(
                description='Use for generating or updating documentation. Invoke when docstrings, README files, or API docs need work.',
                prompt='''You are a technical documentation specialist.

Guidelines:
- Write clear, concise documentation
- Include code examples where appropriate
- Follow Google-style docstrings for Python
- Ensure README files are comprehensive''',
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

### Common Tool Combinations for Subagents

```python
# Read-only agents (analysis, review, research)
read_only_tools = ['Read', 'Grep', 'Glob']

# Test execution agents
test_tools = ['Bash', 'Read', 'Grep']

# Code modification agents
code_mod_tools = ['Read', 'Edit', 'Write', 'Grep', 'Glob']

# Full access agents (use sparingly)
full_tools = ['Read', 'Write', 'Edit', 'Bash', 'Grep', 'Glob']
```

### Dynamic Agent Configuration

```python
def create_reviewer_agent(focus_area: str, strict: bool = False) -> AgentDefinition:
    """Factory function for creating specialized reviewers."""
    return AgentDefinition(
        description=f'Use for {focus_area} code review',
        prompt=f'''You are a {"strict " if strict else ""}code reviewer focusing on {focus_area}.

{"Be very thorough and flag any potential issues." if strict else "Focus on major issues only."}''',
        tools=['Read', 'Grep', 'Glob'],
        model='opus' if strict else 'sonnet'
    )

# Usage
options = ClaudeAgentOptions(
    agents={
        'security': create_reviewer_agent('security', strict=True),
        'performance': create_reviewer_agent('performance'),
        'accessibility': create_reviewer_agent('accessibility'),
    }
)
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

---

## 5. Custom Tools & MCP Servers

### The @tool Decorator

```python
from claude_agent_sdk import tool
from typing import Any

@tool(
    "tool_name",           # Unique identifier
    "Tool description",    # What it does (shown to Claude)
    {"param": str}         # Input schema (simple or JSON Schema)
)
async def my_tool(args: dict[str, Any]) -> dict[str, Any]:
    # Tool implementation
    return {
        "content": [{
            "type": "text",
            "text": "Result here"
        }]
    }
```

### Input Schema Options

```python
# Option 1: Simple type mapping (recommended for most cases)
{"name": str, "count": int, "enabled": bool, "items": list}

# Option 2: Full JSON Schema (for complex validation)
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

### Complete Custom Tool Example

```python
from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeSDKClient, ClaudeAgentOptions
from typing import Any
import aiohttp
import json

# Weather API tool
@tool(
    "get_weather",
    "Get current weather for a location",
    {"city": str, "units": str}
)
async def get_weather(args: dict[str, Any]) -> dict[str, Any]:
    city = args["city"]
    units = args.get("units", "metric")

    # In production, use a real API key
    api_key = "your-api-key"
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&units={units}&appid={api_key}"

    try:
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

# Database query tool
@tool(
    "query_database",
    "Execute a read-only SQL query",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "SQL SELECT query"},
            "limit": {"type": "integer", "default": 100, "maximum": 1000}
        },
        "required": ["query"]
    }
)
async def query_database(args: dict[str, Any]) -> dict[str, Any]:
    query = args["query"]
    limit = args.get("limit", 100)

    # Validate it's a SELECT query
    if not query.strip().upper().startswith("SELECT"):
        return {
            "content": [{
                "type": "text",
                "text": "Error: Only SELECT queries are allowed"
            }]
        }

    # Add LIMIT if not present
    if "LIMIT" not in query.upper():
        query = f"{query} LIMIT {limit}"

    # Execute query (pseudo-code)
    # results = await db.execute(query)
    results = [{"id": 1, "name": "Example"}]  # Placeholder

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(results, indent=2)
        }]
    }

# Create MCP server with tools
my_server = create_sdk_mcp_server(
    name="my-tools",
    version="1.0.0",
    tools=[get_weather, query_database]
)

# Use the tools
async def main():
    options = ClaudeAgentOptions(
        mcp_servers={"my-tools": my_server},
        allowed_tools=[
            "mcp__my-tools__get_weather",
            "mcp__my-tools__query_database"
        ]
    )

    async with ClaudeSDKClient(options) as client:
        await client.query("What's the weather in Tokyo?")
        async for msg in client.receive_response():
            print(msg)
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
    except PermissionError as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Permission Denied: {str(e)}"
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

---

## 6. Session Management

### Session Lifecycle

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Start New   │────▶│   Active     │────▶│   Ended      │
│   Session    │     │   Session    │     │   Session    │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │   Resume     │
                     │   Session    │
                     └──────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
       ┌──────────────┐           ┌──────────────┐
       │  Continue    │           │    Fork      │
       │  (same ID)   │           │  (new ID)    │
       └──────────────┘           └──────────────┘
```

### Capturing Session ID

```python
from claude_agent_sdk import query, ClaudeAgentOptions

session_id = None

async for message in query(
    prompt="Start a new project analysis",
    options=ClaudeAgentOptions(model="claude-sonnet-4-5")
):
    # First message contains session ID
    if hasattr(message, 'subtype') and message.subtype == 'init':
        session_id = message.data.get('session_id')
        print(f"Session ID: {session_id}")
        # Save this for later resumption!

    print(message)
```

### Resuming a Session

```python
# Later, resume the session with full context
async for message in query(
    prompt="Continue with the next step",
    options=ClaudeAgentOptions(
        resume=session_id,  # Session ID from earlier
        model="claude-sonnet-4-5"
    )
):
    print(message)
```

### Forking a Session

```python
# Fork to explore an alternative approach
async for message in query(
    prompt="Let's try a different approach using GraphQL",
    options=ClaudeAgentOptions(
        resume=original_session_id,
        fork_session=True  # Creates NEW session ID
    )
):
    if hasattr(message, 'subtype') and message.subtype == 'init':
        forked_session_id = message.data.get('session_id')
        # Original session remains unchanged!

# Can still continue the original
async for message in query(
    prompt="Continue with the REST API approach",
    options=ClaudeAgentOptions(
        resume=original_session_id,
        fork_session=False  # Default: continue original
    )
):
    print(message)
```

### Session Storage Pattern

```python
import json
from pathlib import Path

class SessionStore:
    def __init__(self, storage_path: str = ".sessions"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)

    def save(self, name: str, session_id: str, metadata: dict = None):
        data = {
            "session_id": session_id,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat()
        }
        (self.storage_path / f"{name}.json").write_text(json.dumps(data))

    def load(self, name: str) -> str | None:
        path = self.storage_path / f"{name}.json"
        if path.exists():
            data = json.loads(path.read_text())
            return data["session_id"]
        return None

# Usage
store = SessionStore()
store.save("feature-auth", session_id, {"description": "Authentication feature"})

# Later
saved_id = store.load("feature-auth")
if saved_id:
    async for msg in query(prompt="Continue", options=ClaudeAgentOptions(resume=saved_id)):
        print(msg)
```

---

## 7. Permissions & Security

### Permission Flow Diagram

```
Tool Request
     │
     ▼
┌────────────────┐
│ PreToolUse     │──▶ Allow ──▶ Execute
│    Hook        │──▶ Deny  ──▶ Denied
└───────┬────────┘──▶ Ask   ──▶ canUseTool
        │ Continue
        ▼
┌────────────────┐
│  Deny Rules    │──▶ Match ──▶ Denied
└───────┬────────┘
        │ No Match
        ▼
┌────────────────┐
│  Allow Rules   │──▶ Match ──▶ Execute
└───────┬────────┘
        │ No Match
        ▼
┌────────────────┐
│   Ask Rules    │──▶ Match ──▶ canUseTool
└───────┬────────┘
        │ No Match
        ▼
┌────────────────┐
│ Permission     │──▶ bypassPermissions ──▶ Execute
│    Mode        │──▶ Other modes ──────▶ canUseTool
└────────────────┘
```

### Permission Modes

| Mode | Behavior |
|------|----------|
| `default` | Standard permission checks apply |
| `acceptEdits` | Auto-approve file edits and filesystem ops |
| `bypassPermissions` | Bypass ALL checks (dangerous!) |

### Setting Permission Mode

```python
from claude_agent_sdk import ClaudeAgentOptions

# Standard mode
options = ClaudeAgentOptions(permission_mode='default')

# Auto-accept edits (good for trusted automation)
options = ClaudeAgentOptions(permission_mode='acceptEdits')

# Bypass all (only for controlled environments!)
options = ClaudeAgentOptions(permission_mode='bypassPermissions')
```

### Custom Permission Handler (can_use_tool)

```python
async def permission_handler(
    tool_name: str,
    input_data: dict,
    context: dict
) -> dict:
    """
    Custom permission logic.

    Returns:
        {
            "behavior": "allow" | "deny",
            "updatedInput": dict,  # Optional: modified input
            "message": str,        # Optional: denial reason
            "interrupt": bool      # Optional: stop execution
        }
    """

    # Example: Block system directory writes
    if tool_name == "Write":
        path = input_data.get("file_path", "")
        if path.startswith("/etc/") or path.startswith("/system/"):
            return {
                "behavior": "deny",
                "message": "Cannot write to system directories",
                "interrupt": True
            }

    # Example: Sandbox file operations
    if tool_name in ["Write", "Edit"]:
        path = input_data.get("file_path", "")
        if not path.startswith("./sandbox/"):
            sandboxed_path = f"./sandbox/{path.lstrip('/')}"
            return {
                "behavior": "allow",
                "updatedInput": {**input_data, "file_path": sandboxed_path}
            }

    # Example: Log all bash commands
    if tool_name == "Bash":
        command = input_data.get("command", "")
        print(f"[AUDIT] Bash command: {command}")

    # Allow by default
    return {"behavior": "allow", "updatedInput": input_data}

# Use the handler
options = ClaudeAgentOptions(
    can_use_tool=permission_handler,
    allowed_tools=["Read", "Write", "Edit", "Bash"]
)
```

### Tool Allow/Disallow Lists

```python
options = ClaudeAgentOptions(
    # Explicitly allow only these tools
    allowed_tools=["Read", "Grep", "Glob"],

    # OR explicitly block these tools
    disallowed_tools=["Bash", "Write"],
)
```

---

## 8. Monitoring & Cost Tracking

### Usage Data Structure

```python
{
    "input_tokens": 1500,
    "output_tokens": 500,
    "cache_creation_input_tokens": 200,
    "cache_read_input_tokens": 1000,
    "service_tier": "standard",
    "total_cost_usd": 0.0045  # Only in result message
}
```

### Cost Tracking Implementation

```python
from claude_agent_sdk import query, AssistantMessage, ResultMessage
from datetime import datetime
from typing import Any

class CostTracker:
    def __init__(self):
        self.processed_ids: set[str] = set()
        self.steps: list[dict[str, Any]] = []

    async def track(self, prompt: str, options=None) -> dict:
        result = None

        async for message in query(prompt=prompt, options=options):
            self._process_message(message)
            if isinstance(message, ResultMessage):
                result = message

        return {
            "result": result,
            "steps": self.steps,
            "total_cost": getattr(result, 'total_cost_usd', 0) if result else 0,
            "total_input_tokens": sum(s["usage"].get("input_tokens", 0) for s in self.steps),
            "total_output_tokens": sum(s["usage"].get("output_tokens", 0) for s in self.steps),
        }

    def _process_message(self, message):
        if not isinstance(message, AssistantMessage):
            return
        if not hasattr(message, 'usage') or not message.usage:
            return

        msg_id = getattr(message, 'id', None)
        if not msg_id or msg_id in self.processed_ids:
            return  # Deduplicate!

        self.processed_ids.add(msg_id)
        self.steps.append({
            "message_id": msg_id,
            "timestamp": datetime.now().isoformat(),
            "usage": message.usage
        })

    def calculate_cost(self, usage: dict) -> float:
        """Calculate cost based on current pricing."""
        # Adjust these rates based on current API pricing
        input_rate = 0.00003  # per token
        output_rate = 0.00015  # per token
        cache_read_rate = 0.0000075  # per token

        cost = (
            usage.get("input_tokens", 0) * input_rate +
            usage.get("output_tokens", 0) * output_rate +
            usage.get("cache_read_input_tokens", 0) * cache_read_rate
        )
        return cost

# Usage
async def main():
    tracker = CostTracker()
    result = await tracker.track("Analyze this codebase for issues")

    print(f"Steps: {len(result['steps'])}")
    print(f"Total tokens: {result['total_input_tokens']} in, {result['total_output_tokens']} out")
    print(f"Total cost: ${result['total_cost']:.4f}")
```

### Key Cost Tracking Rules

1. **Deduplicate by message ID** - Same ID = same usage data
2. **Charge once per step** - Not per individual message
3. **Use result message for totals** - Contains authoritative `total_cost_usd`

---

## 9. Structured Outputs

### Basic Usage with JSON Schema

```python
from claude_agent_sdk import query, ClaudeAgentOptions

schema = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    "description": {"type": "string"},
                    "file": {"type": "string"},
                    "line": {"type": "integer"}
                },
                "required": ["severity", "description"]
            }
        },
        "score": {"type": "integer", "minimum": 0, "maximum": 100}
    },
    "required": ["summary", "issues", "score"]
}

async for message in query(
    prompt="Analyze the codebase for security issues",
    options=ClaudeAgentOptions(
        output_format={
            "type": "json_schema",
            "schema": schema
        }
    )
):
    if hasattr(message, 'structured_output'):
        data = message.structured_output
        print(f"Score: {data['score']}/100")
        print(f"Found {len(data['issues'])} issues")
```

### Using Pydantic (Recommended for Python)

```python
from pydantic import BaseModel
from claude_agent_sdk import query, ClaudeAgentOptions

class Issue(BaseModel):
    severity: str
    description: str
    file: str
    line: int | None = None

class AnalysisResult(BaseModel):
    summary: str
    issues: list[Issue]
    score: int

async for message in query(
    prompt="Analyze the codebase",
    options=ClaudeAgentOptions(
        output_format={
            "type": "json_schema",
            "schema": AnalysisResult.model_json_schema()
        }
    )
):
    if hasattr(message, 'structured_output'):
        # Validate and get typed result
        result = AnalysisResult.model_validate(message.structured_output)
        print(f"Score: {result.score}")
        for issue in result.issues:
            print(f"[{issue.severity}] {issue.file}: {issue.description}")
```

---

## 10. System Prompts & Configuration

### System Prompt Options

```python
from claude_agent_sdk import ClaudeAgentOptions

# Option 1: Empty (SDK default)
options = ClaudeAgentOptions()  # No system prompt

# Option 2: Claude Code preset
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

```python
# IMPORTANT: Must specify setting_sources to load CLAUDE.md
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
# Load all settings
options = ClaudeAgentOptions(
    setting_sources=["user", "project", "local"]
)

# Load only project settings (good for CI)
options = ClaudeAgentOptions(
    setting_sources=["project"]
)
```

---

## 11. Production Hosting

### Deployment Patterns

| Pattern | Description | Use Cases |
|---------|-------------|-----------|
| **Ephemeral** | New container per task | Bug fixes, one-off processing |
| **Long-Running** | Persistent containers | Chatbots, email agents |
| **Hybrid** | Ephemeral + state hydration | Research agents, project managers |

### System Requirements

| Component | Requirement |
|-----------|-------------|
| Python | 3.10+ |
| Node.js | 18+ |
| Claude Code CLI | `npm install -g @anthropic-ai/claude-code` |
| RAM | ~1 GiB minimum |
| Disk | ~5 GiB |
| Network | Outbound HTTPS to `api.anthropic.com` |

### Sandbox Providers

- Cloudflare Sandboxes
- Modal Sandboxes
- Daytona
- E2B
- Fly Machines
- Vercel Sandbox

### Container Deployment Example

```python
# Dockerfile
"""
FROM python:3.11-slim

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . /app
WORKDIR /app

CMD ["python", "main.py"]
"""
```

---

## 12. Best Practices & Patterns

### Multi-Agent Design

1. **Write descriptive agent descriptions** - Main agent uses these for routing
2. **Restrict tools appropriately** - Read-only agents shouldn't write
3. **Choose models wisely**:
   - `haiku`: Simple tasks, cheaper
   - `sonnet`: Most tasks
   - `opus`: Complex reasoning

### Custom Tool Development

1. **Always return structured content**:
```python
return {"content": [{"type": "text", "text": "..."}]}
```

2. **Handle all errors gracefully** - Return error in content, don't raise

3. **Use async/await** - All handlers must be async

4. **Validate inputs** - Use JSON Schema for complex cases

### Session Management

1. **Always capture session IDs** for potential resumption
2. **Use forking for experiments** - Don't modify originals
3. **Implement cleanup** - Use async context managers

### Security

1. **Use sandboxed containers** in production
2. **Set appropriate permission modes** - `default` usually
3. **Implement can_use_tool** for custom validation
4. **Restrict tool access** per subagent

### Cost Optimization

1. **Use `haiku` for simple subagents**
2. **Set `max_turns`** to prevent runaway
3. **Monitor usage per message ID** to deduplicate
4. **Leverage prompt caching** (automatic)

---

## 13. Quick Reference Tables

### ClaudeAgentOptions Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `allowed_tools` | `list[str]` | `[]` | Allowed tool names |
| `disallowed_tools` | `list[str]` | `[]` | Blocked tool names |
| `system_prompt` | `str \| dict` | `None` | System prompt config |
| `mcp_servers` | `dict` | `{}` | MCP server configs |
| `permission_mode` | `str` | `None` | `default`, `acceptEdits`, `bypassPermissions` |
| `max_turns` | `int` | `None` | Max conversation turns |
| `model` | `str` | `None` | Model to use |
| `cwd` | `str` | `None` | Working directory |
| `resume` | `str` | `None` | Session ID to resume |
| `fork_session` | `bool` | `False` | Fork when resuming |
| `agents` | `dict` | `None` | Subagent definitions |
| `output_format` | `dict` | `None` | Structured output schema |
| `can_use_tool` | `Callable` | `None` | Permission callback |
| `setting_sources` | `list` | `None` | Settings to load |

### Built-in Tools

| Tool | Description |
|------|-------------|
| `Read` | Read file contents |
| `Write` | Create/overwrite files |
| `Edit` | Modify existing files |
| `Glob` | Find files by pattern |
| `Grep` | Search file contents |
| `Bash` | Execute shell commands |
| `WebSearch` | Search the web |
| `WebFetch` | Fetch URL content |

### Message Types

| Type | Description |
|------|-------------|
| `AssistantMessage` | Claude's response |
| `UserMessage` | User input |
| `ToolUseMessage` | Tool invocation |
| `ToolResultMessage` | Tool output |
| `ResultMessage` | Final result with totals |
| `SystemMessage` | System events (init, etc.) |

---

## 14. Complete Examples

### Example 1: Code Review Agent with Custom Tools

```python
import asyncio
from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions, AgentDefinition,
    tool, create_sdk_mcp_server, AssistantMessage, TextBlock
)
from typing import Any
import subprocess
import json

# Custom tool: Run linting
@tool("run_linter", "Run code linter on specified files", {"path": str, "fix": bool})
async def run_linter(args: dict[str, Any]) -> dict[str, Any]:
    cmd = ["ruff", "check", args["path"]]
    if args.get("fix"):
        cmd.append("--fix")

    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout or result.stderr or "No issues found"

    return {"content": [{"type": "text", "text": output}]}

# Custom tool: Run tests
@tool("run_tests", "Execute pytest on specified path", {"path": str, "verbose": bool})
async def run_tests(args: dict[str, Any]) -> dict[str, Any]:
    cmd = ["pytest", args["path"], "-v" if args.get("verbose") else "-q"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    return {"content": [{"type": "text", "text": result.stdout + result.stderr}]}

# Create MCP server
dev_tools = create_sdk_mcp_server(
    name="dev-tools",
    version="1.0.0",
    tools=[run_linter, run_tests]
)

async def code_review_session():
    options = ClaudeAgentOptions(
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": """You are a senior code reviewer. For each review:
1. Check code style and run linter
2. Look for security issues
3. Run tests to verify functionality
4. Provide actionable feedback"""
        },
        mcp_servers={"dev-tools": dev_tools},
        allowed_tools=[
            "Read", "Grep", "Glob",
            "mcp__dev-tools__run_linter",
            "mcp__dev-tools__run_tests"
        ],
        agents={
            'security-scanner': AgentDefinition(
                description='Use for detailed security analysis',
                prompt='You are a security expert. Look for OWASP Top 10 vulnerabilities.',
                tools=['Read', 'Grep'],
                model='sonnet'
            )
        },
        permission_mode='default'
    )

    async with ClaudeSDKClient(options) as client:
        await client.query("Review the authentication module in src/auth/")

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)

asyncio.run(code_review_session())
```

### Example 2: Research Agent with Session Persistence

```python
import asyncio
import json
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

class ResearchSession:
    def __init__(self, name: str):
        self.name = name
        self.session_file = Path(f".sessions/{name}.json")
        self.session_file.parent.mkdir(exist_ok=True)

    def save(self, session_id: str, notes: list[str]):
        data = {"session_id": session_id, "notes": notes}
        self.session_file.write_text(json.dumps(data))

    def load(self) -> tuple[str | None, list[str]]:
        if self.session_file.exists():
            data = json.loads(self.session_file.read_text())
            return data.get("session_id"), data.get("notes", [])
        return None, []

async def research_topic(topic: str, session_name: str):
    session = ResearchSession(session_name)
    existing_id, notes = session.load()

    options = ClaudeAgentOptions(
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": f"""You are a research assistant investigating: {topic}

Previous research notes:
{chr(10).join(f'- {n}' for n in notes) if notes else 'None yet'}"""
        },
        agents={
            'web-researcher': AgentDefinition(
                description='Use for web searches and fetching online resources',
                prompt='You are a web research specialist. Find authoritative sources.',
                tools=['WebSearch', 'WebFetch'],
                model='haiku'
            ),
            'summarizer': AgentDefinition(
                description='Use for summarizing long documents or findings',
                prompt='You are an expert summarizer. Create concise, informative summaries.',
                tools=['Read'],
                model='haiku'
            )
        },
        resume=existing_id,
        allowed_tools=["Read", "Write", "Grep", "Glob", "WebSearch", "WebFetch"]
    )

    new_session_id = None

    async for message in query(
        prompt=f"Continue research on: {topic}. Find new information and update notes.",
        options=options
    ):
        if hasattr(message, 'subtype') and message.subtype == 'init':
            new_session_id = message.data.get('session_id')
        print(message)

    if new_session_id:
        session.save(new_session_id, notes + [f"Researched: {topic}"])
        print(f"Session saved: {new_session_id}")

asyncio.run(research_topic("Claude Agent SDK best practices", "sdk-research"))
```

### Example 3: Structured Output Pipeline

```python
import asyncio
from pydantic import BaseModel
from claude_agent_sdk import query, ClaudeAgentOptions

class CodeMetrics(BaseModel):
    total_files: int
    total_lines: int
    languages: dict[str, int]  # language -> line count
    complexity_score: float
    maintainability_grade: str

class SecurityFinding(BaseModel):
    severity: str
    category: str
    file: str
    line: int | None
    description: str
    recommendation: str

class AnalysisReport(BaseModel):
    project_name: str
    metrics: CodeMetrics
    security_findings: list[SecurityFinding]
    recommendations: list[str]
    overall_health: str

async def analyze_project(project_path: str) -> AnalysisReport:
    options = ClaudeAgentOptions(
        system_prompt={
            "type": "preset",
            "preset": "claude_code"
        },
        allowed_tools=["Read", "Grep", "Glob", "Bash"],
        output_format={
            "type": "json_schema",
            "schema": AnalysisReport.model_json_schema()
        }
    )

    async for message in query(
        prompt=f"""Analyze the project at {project_path}:
        1. Count files and lines per language
        2. Estimate complexity and maintainability
        3. Scan for security issues
        4. Provide recommendations

        Return a comprehensive analysis report.""",
        options=options
    ):
        if hasattr(message, 'structured_output'):
            return AnalysisReport.model_validate(message.structured_output)

    raise RuntimeError("No structured output received")

async def main():
    report = await analyze_project("./src")

    print(f"Project: {report.project_name}")
    print(f"Health: {report.overall_health}")
    print(f"Files: {report.metrics.total_files}")
    print(f"Lines: {report.metrics.total_lines}")
    print(f"Grade: {report.metrics.maintainability_grade}")

    if report.security_findings:
        print(f"\nSecurity Issues ({len(report.security_findings)}):")
        for finding in report.security_findings:
            print(f"  [{finding.severity}] {finding.category}: {finding.description}")

asyncio.run(main())
```

---

## Official Resources

- **Documentation**: https://docs.anthropic.com/en/docs/agent-sdk
- **Python SDK GitHub**: https://github.com/anthropics/claude-agent-sdk-python
- **TypeScript SDK GitHub**: https://github.com/anthropics/claude-agent-sdk-typescript
- **Bug Reports**: https://github.com/anthropics/claude-agent-sdk-python/issues

---

*Last updated: November 2025*
