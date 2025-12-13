# Claude Agent SDK - API Reference

> **Reference:** Python SDK v0.1.0+
> **Focus:** Complete type definitions, message types, errors, skills, plugins, cost tracking

---

## Table of Contents

1. [ClaudeAgentOptions](#claudeagentoptions)
2. [Message Types](#message-types)
3. [Content Blocks](#content-blocks)
4. [Error Types](#error-types)
5. [Skills](#skills)
6. [Plugins](#plugins)
7. [Cost Tracking](#cost-tracking)
8. [Slash Commands](#slash-commands)

---

## ClaudeAgentOptions

### Complete Field Reference

```python
from dataclasses import dataclass
from typing import Callable, Literal, Any
from pathlib import Path

@dataclass
class ClaudeAgentOptions:
    # ─── Tool Configuration ───────────────────────────────────
    allowed_tools: list[str] = []
    """Tools Claude can use. Empty = all available tools."""

    disallowed_tools: list[str] = []
    """Tools Claude cannot use. Takes precedence over allowed_tools."""

    # ─── System Prompt ────────────────────────────────────────
    system_prompt: str | SystemPromptPreset | None = None
    """Custom system prompt or preset configuration.
    Default: None (empty system prompt, NOT Claude Code preset!)
    """

    # ─── Session Management ───────────────────────────────────
    continue_conversation: bool = False
    """Continue from last conversation in cwd (ClaudeSDKClient only)."""

    resume: str | None = None
    """Session ID to resume. Overrides continue_conversation."""

    fork_session: bool = False
    """If resuming, create new branch instead of continuing."""

    # ─── Model & Execution ────────────────────────────────────
    model: str | None = None
    """Model to use: 'opus', 'sonnet', 'haiku', or full ID."""

    max_turns: int | None = None
    """Maximum conversation turns. Prevents infinite loops."""

    # ─── Working Environment ──────────────────────────────────
    cwd: str | Path | None = None
    """Working directory for file operations."""

    add_dirs: list[str | Path] = []
    """Additional directories Claude can access."""

    env: dict[str, str] = {}
    """Environment variables for subprocess execution."""

    # ─── MCP & Extensions ─────────────────────────────────────
    mcp_servers: dict[str, McpServerConfig] = {}
    """MCP server configurations. Keys become server names."""

    agents: dict[str, AgentDefinition] | None = None
    """Programmatic subagent definitions."""

    plugins: list[SdkPluginConfig] = []
    """Plugin configurations to load."""

    # ─── Permissions ──────────────────────────────────────────
    permission_mode: PermissionMode | None = None
    """'default', 'acceptEdits', 'bypassPermissions'"""

    can_use_tool: CanUseTool | None = None
    """Custom permission callback function."""

    # ─── Hooks ────────────────────────────────────────────────
    hooks: dict[HookEvent, list[HookMatcher]] | None = None
    """Event hooks for tool use and other events."""

    # ─── Settings Sources ─────────────────────────────────────
    setting_sources: list[SettingSource] | None = None
    """Where to load settings from: ['user', 'project', 'local']
    Default: None (no filesystem settings loaded!)
    """

    settings: str | None = None
    """Path to settings.json file."""

    # ─── Output ───────────────────────────────────────────────
    output_format: OutputFormat | None = None
    """Structured output format (JSON schema)."""

    include_partial_messages: bool = False
    """Include streaming partial messages."""

    # ─── User & Sandbox ───────────────────────────────────────
    user: str | None = None
    """User identifier for multi-tenant systems."""

    sandbox: SandboxSettings | None = None
    """Sandbox configuration for command execution."""

    # ─── Advanced ─────────────────────────────────────────────
    extra_args: dict[str, str | None] = {}
    """Additional CLI arguments (advanced use)."""
```

### SystemPromptPreset

```python
from typing import TypedDict, Literal

class SystemPromptPreset(TypedDict):
    type: Literal["preset"]
    preset: Literal["claude_code"]
    append: str | None  # Optional text to append to preset
```

### AgentDefinition

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class AgentDefinition:
    description: str
    """When to invoke this agent. Used for automatic selection."""

    prompt: str
    """System prompt for the agent."""

    tools: list[str] | None = None
    """Allowed tools. None = inherit all from parent."""

    model: Literal["sonnet", "opus", "haiku", "inherit"] | None = None
    """Model override. None = inherit from parent."""
```

### PermissionMode

```python
from typing import Literal

PermissionMode = Literal["default", "acceptEdits", "bypassPermissions", "plan"]
# Note: "plan" is NOT currently supported in Python SDK
```

### HookEvent

```python
from typing import Literal

HookEvent = Literal[
    "PreToolUse",
    "PostToolUse",
    "UserPromptSubmit",
    "Stop",
    "SubagentStop",
    "PreCompact"
]
# NOT supported: SessionStart, SessionEnd, Notification
```

### SettingSource

```python
from typing import Literal

SettingSource = Literal["user", "project", "local"]
```

### SandboxSettings

```python
from typing import TypedDict

class SandboxNetworkConfig(TypedDict, total=False):
    allowLocalBinding: bool
    allowUnixSockets: list[str]

class SandboxIgnoreViolations(TypedDict, total=False):
    fakeRoot: bool
    network: bool
    filesystem: list[str]

class SandboxSettings(TypedDict, total=False):
    enabled: bool
    autoAllowBashIfSandboxed: bool
    excludedCommands: list[str]
    network: SandboxNetworkConfig
    ignoreViolations: SandboxIgnoreViolations
```

---

## Message Types

### Message Union

```python
from typing import Union

Message = Union[
    SystemMessage,
    UserMessage,
    AssistantMessage,
    ResultMessage
]
```

### SystemMessage

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class SystemMessage:
    type: str = "system"
    subtype: str  # 'init', 'info', 'warning', 'error'
    data: dict[str, Any]

    # Available in subtype='init':
    # - session_id: str
    # - plugins: list[dict]
    # - slash_commands: list[str]
```

### UserMessage

```python
from dataclasses import dataclass
from typing import Union

@dataclass
class UserMessage:
    type: str = "user"
    content: str | list[ContentBlock]
```

### AssistantMessage

```python
from dataclasses import dataclass

@dataclass
class AssistantMessage:
    type: str = "assistant"
    id: str  # Message ID (same for all parts of one response)
    content: list[ContentBlock]
    model: str
    usage: dict[str, Any] | None = None
```

### ResultMessage

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class ResultMessage:
    type: str = "result"
    subtype: str  # 'success', 'error', 'interrupted'
    session_id: str
    duration_ms: int
    duration_api_ms: int
    is_error: bool
    num_turns: int
    result: str | None = None
    total_cost_usd: float | None = None
    usage: dict[str, Any] | None = None
```

---

## Content Blocks

### ContentBlock Union

```python
from typing import Union

ContentBlock = Union[
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    ToolResultBlock
]
```

### TextBlock

```python
from dataclasses import dataclass

@dataclass
class TextBlock:
    type: str = "text"
    text: str
```

### ThinkingBlock

```python
from dataclasses import dataclass

@dataclass
class ThinkingBlock:
    type: str = "thinking"
    thinking: str
    signature: str
```

### ToolUseBlock

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class ToolUseBlock:
    type: str = "tool_use"
    id: str  # Tool use ID
    name: str  # Tool name (e.g., "Read", "mcp__server__tool")
    input: dict[str, Any]  # Tool parameters
```

### ToolResultBlock

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class ToolResultBlock:
    type: str = "tool_result"
    tool_use_id: str  # Links to ToolUseBlock.id
    content: str | list[dict[str, Any]] | None = None
    is_error: bool | None = None
```

---

## Error Types

### Exception Hierarchy

```python
from claude_agent_sdk import (
    ClaudeSDKError,      # Base exception
    CLINotFoundError,    # Claude Code CLI not installed
    ProcessError,        # CLI process failed
    CLIJSONDecodeError,  # Invalid JSON from CLI
)
```

### Error Handling Examples

```python
from claude_agent_sdk import (
    query,
    ClaudeSDKError,
    CLINotFoundError,
    ProcessError,
    CLIJSONDecodeError
)

try:
    async for message in query(prompt="Hello"):
        print(message)

except CLINotFoundError:
    print("Claude Code CLI not installed!")
    print("Run: npm install -g @anthropic-ai/claude-code")

except ProcessError as e:
    print(f"Process failed with exit code: {e.exit_code}")
    print(f"stderr: {e.stderr}")

except CLIJSONDecodeError as e:
    print(f"Failed to parse response: {e.line}")

except ClaudeSDKError as e:
    print(f"SDK error: {e}")
```

---

## Skills

### Overview

Skills are filesystem-based capabilities that Claude autonomously invokes when relevant.

**Important:** Skills are NOT loaded by default. You must configure `setting_sources`.

### Loading Skills

```python
from claude_agent_sdk import query, ClaudeAgentOptions

options = ClaudeAgentOptions(
    cwd="/path/to/project",  # Must contain .claude/skills/
    setting_sources=["user", "project"],  # REQUIRED to load skills!
    allowed_tools=["Skill", "Read", "Write", "Bash"]  # Enable Skill tool
)

async for message in query(
    prompt="Help me process this PDF",
    options=options
):
    print(message)
```

### Skill Locations

| Source | Path | Description |
|--------|------|-------------|
| Project | `.claude/skills/*/SKILL.md` | Shared via git |
| User | `~/.claude/skills/*/SKILL.md` | Personal, all projects |
| Plugin | Via plugin directories | Bundled with plugins |

### SKILL.md Format

```markdown
---
description: Process PDF documents and extract text/tables
name: pdf-processor
---

You are a PDF processing specialist.

When processing PDFs:
1. Use appropriate tools to extract text
2. Preserve formatting where possible
3. Extract tables as markdown
```

### Discovering Available Skills

```python
async for message in query(
    prompt="What Skills are available?",
    options=ClaudeAgentOptions(
        setting_sources=["user", "project"],
        allowed_tools=["Skill"]
    )
):
    print(message)
```

---

## Plugins

### Overview

Plugins extend Claude with custom commands, agents, skills, hooks, and MCP servers.

### Loading Plugins

```python
from claude_agent_sdk import query, ClaudeAgentOptions

options = ClaudeAgentOptions(
    plugins=[
        {"type": "local", "path": "./my-plugin"},
        {"type": "local", "path": "/absolute/path/to/plugin"}
    ]
)

async for message in query(prompt="Hello", options=options):
    if message.type == "system" and message.subtype == "init":
        print("Plugins:", message.data.get("plugins"))
        print("Commands:", message.data.get("slash_commands"))
```

### Plugin Structure

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json          # Required manifest
├── commands/                 # Custom slash commands
│   └── my-command.md
├── agents/                   # Custom agents
│   └── specialist.md
├── skills/                   # Agent Skills
│   └── my-skill/
│       └── SKILL.md
├── hooks/                    # Event handlers
│   └── hooks.json
└── .mcp.json                # MCP server definitions
```

### Using Plugin Commands

Plugin commands are namespaced: `plugin-name:command-name`

```python
async for message in query(
    prompt="/my-plugin:custom-command",  # Use plugin command
    options=ClaudeAgentOptions(
        plugins=[{"type": "local", "path": "./my-plugin"}]
    )
):
    print(message)
```

---

## Cost Tracking

### Understanding Usage Data

```python
# Usage object fields
usage = {
    "input_tokens": int,                    # Base input tokens
    "output_tokens": int,                   # Generated tokens
    "cache_creation_input_tokens": int,     # Cache creation
    "cache_read_input_tokens": int,         # Cache reads
    "service_tier": str,                    # e.g., "standard"
}

# ResultMessage has total cost
result.total_cost_usd  # Authoritative source!
```

### Critical Rules

1. **Same ID = Same Usage**: All messages with same `id` have identical usage
2. **Charge Once Per Step**: Don't charge for each message, only once per unique ID
3. **ResultMessage is Authoritative**: Contains cumulative usage from all steps
4. **Deduplicate by Message ID**: Track processed IDs to avoid double-counting

### Cost Tracking Implementation

```python
from claude_agent_sdk import query, AssistantMessage, ResultMessage
from datetime import datetime

class CostTracker:
    def __init__(self):
        self.processed_ids: set[str] = set()
        self.step_usages: list[dict] = []

    async def track(self, prompt: str) -> dict:
        result = None

        async for message in query(prompt=prompt):
            self.process_message(message)
            if isinstance(message, ResultMessage):
                result = message

        return {
            "result": result,
            "steps": self.step_usages,
            "total_cost": result.total_cost_usd if result else 0
        }

    def process_message(self, message):
        if not isinstance(message, AssistantMessage):
            return
        if not hasattr(message, 'usage') or not message.usage:
            return

        message_id = getattr(message, 'id', None)
        if not message_id or message_id in self.processed_ids:
            return  # Skip duplicates!

        self.processed_ids.add(message_id)
        self.step_usages.append({
            "id": message_id,
            "timestamp": datetime.now().isoformat(),
            "usage": message.usage,
            "cost": self.calculate_cost(message.usage)
        })

    def calculate_cost(self, usage: dict) -> float:
        # Example pricing (check actual rates)
        input_cost = usage.get("input_tokens", 0) * 0.00003
        output_cost = usage.get("output_tokens", 0) * 0.00015
        cache_read = usage.get("cache_read_input_tokens", 0) * 0.0000075
        return input_cost + output_cost + cache_read


# Usage
async def main():
    tracker = CostTracker()
    result = await tracker.track("Analyze this codebase")
    print(f"Steps: {len(result['steps'])}")
    print(f"Total: ${result['total_cost']:.4f}")
```

### Message Flow Example

```
Step 1: Claude responds with parallel tool uses
├── AssistantMessage (id="msg_1", usage={...})  ← Charge this
├── AssistantMessage (id="msg_1", usage={...})  ← Skip (same ID)
└── AssistantMessage (id="msg_1", usage={...})  ← Skip (same ID)

Step 2: Claude responds with text
└── AssistantMessage (id="msg_2", usage={...})  ← Charge this

Step 3: Final result
└── ResultMessage (total_cost_usd=0.0034)       ← Authoritative total
```

---

## Slash Commands

### Built-in Commands

| Command | Description |
|---------|-------------|
| `/compact` | Compact conversation history |
| `/clear` | Clear conversation, start fresh |
| `/help` | Show available commands |

### Using Slash Commands

```python
# Compact conversation
async for message in query(prompt="/compact"):
    pass

# Clear conversation
async for message in query(prompt="/clear"):
    pass
```

### Custom Commands

Create `.claude/commands/my-command.md`:

```markdown
---
description: Run linting and type checking
argument-hint: [path]
---

Run linting with ruff and type checking with mypy on $1 or the entire project.

Steps:
1. Run ruff check
2. Run mypy
3. Report any issues found
```

Use with:
```python
async for message in query(
    prompt="/my-command src/",
    options=ClaudeAgentOptions(setting_sources=["project"])
):
    print(message)
```

---

## Quick Reference Tables

### Built-in Tools

| Tool | Read | Write | Execute | Description |
|------|------|-------|---------|-------------|
| Read | ✅ | | | Read any file |
| Write | | ✅ | | Create new files |
| Edit | | ✅ | | Modify existing files |
| Bash | | | ✅ | Run shell commands |
| Glob | ✅ | | | Find files by pattern |
| Grep | ✅ | | | Search file contents |
| WebSearch | ✅ | | | Search the web |
| WebFetch | ✅ | | | Fetch web pages |
| Task | | | ✅ | Spawn subagents |
| TodoWrite | | ✅ | | Track progress |
| NotebookEdit | | ✅ | | Edit Jupyter notebooks |

### Model Selection

| Model | Speed | Cost | Best For |
|-------|-------|------|----------|
| `haiku` | Fastest | Lowest | Simple tasks, high volume |
| `sonnet` | Medium | Medium | General use, balanced |
| `opus` | Slowest | Highest | Complex reasoning |

### Common Patterns

```python
# Read-only analysis
ClaudeAgentOptions(
    allowed_tools=["Read", "Grep", "Glob", "Task"],
    permission_mode="bypassPermissions"
)

# Automated code modification
ClaudeAgentOptions(
    allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    permission_mode="acceptEdits"
)

# Full automation in sandbox
ClaudeAgentOptions(
    allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"],
    permission_mode="bypassPermissions",
    sandbox={"enabled": True}
)

# Interactive with custom permissions
ClaudeAgentOptions(
    allowed_tools=["Read", "Write", "Edit", "Bash"],
    permission_mode="default",
    can_use_tool=custom_permission_handler
)
```

---

*Documentation based on Claude Agent SDK v0.1.0+ (December 2025)*
