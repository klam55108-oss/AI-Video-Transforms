# Claude Agent SDK - Overview & Quickstart

> **Version:** v0.1.0+ (Docs v0.5.0, December 2025)
> **Package:** `claude-agent-sdk` (migrated from `claude-code-sdk`)
> **Official Docs:** https://docs.anthropic.com/en/docs/agent-sdk/overview
> **Python GitHub:** https://github.com/anthropics/claude-agent-sdk-python

---

## Table of Contents

1. [What is the Claude Agent SDK?](#what-is-the-claude-agent-sdk)
2. [Key Capabilities](#key-capabilities)
3. [Installation & Setup](#installation--setup)
4. [Quick Start Example](#quick-start-example)
5. [SDK vs Other Claude Tools](#sdk-vs-other-claude-tools)
6. [Migration from claude-code-sdk](#migration-from-claude-code-sdk)

---

## What is the Claude Agent SDK?

The Claude Agent SDK provides **Claude Code as a library** - the same tools, agent loop, and context management that power Claude Code, but programmable in Python and TypeScript.

### Key Differences from Standard Claude API

| Aspect | Standard Claude API | Claude Agent SDK |
|--------|---------------------|------------------|
| **State** | Stateless | Stateful (long-running process) |
| **Tools** | You implement the tool loop | Built-in + extensible tools |
| **Context** | Manual management | Automatic compaction |
| **Sessions** | Not supported | Full session management |
| **Multi-agent** | Not supported | Native subagent support |

### Architecture

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

## Key Capabilities

### Built-in Tools

| Tool | Description |
|------|-------------|
| **Read** | Read any file in the working directory |
| **Write** | Create new files |
| **Edit** | Make precise edits to existing files |
| **Bash** | Run terminal commands, scripts, git operations |
| **Glob** | Find files by pattern (`**/*.ts`, `src/**/*.py`) |
| **Grep** | Search file contents with regex |
| **WebSearch** | Search the web for current information |
| **WebFetch** | Fetch and parse web page content |
| **Task** | Launch subagents for parallel work |
| **TodoWrite** | Track task progress |
| **NotebookEdit** | Edit Jupyter notebooks |

### Additional Features

- **Hooks**: Run custom code at key points (PreToolUse, PostToolUse, etc.)
- **Subagents**: Spawn specialized agents for focused subtasks
- **MCP Integration**: Connect to external systems via Model Context Protocol
- **Permissions**: Fine-grained control over tool access
- **Sessions**: Maintain context across multiple exchanges, resume later
- **Skills**: Filesystem-based specialized capabilities
- **Plugins**: Extend with custom commands, agents, and MCP servers

---

## Installation & Setup

### Prerequisites

- Python 3.10+
- Node.js 18+ (required by Claude Code CLI)
- Claude Code CLI

### Step 1: Install Claude Code CLI

```bash
# Option 1: Direct install (macOS/Linux/WSL)
curl -fsSL https://claude.ai/install.sh | bash

# Option 2: Homebrew
brew install --cask claude-code

# Option 3: npm
npm install -g @anthropic-ai/claude-code
```

### Step 2: Install Python SDK

```bash
pip install claude-agent-sdk

# Or with uv (recommended)
uv add claude-agent-sdk
```

### Step 3: Set API Key

```bash
export ANTHROPIC_API_KEY=your-api-key
```

Get your key from the [Anthropic Console](https://console.anthropic.com/).

### Alternative Authentication Methods

```python
import os

# Option 1: Direct API Key (recommended)
os.environ["ANTHROPIC_API_KEY"] = "your-api-key"

# Option 2: Amazon Bedrock
os.environ["CLAUDE_CODE_USE_BEDROCK"] = "1"
# + Configure AWS credentials

# Option 3: Google Vertex AI
os.environ["CLAUDE_CODE_USE_VERTEX"] = "1"
# + Configure Google Cloud credentials

# Option 4: Microsoft Foundry
os.environ["CLAUDE_CODE_USE_FOUNDRY"] = "1"
# + Configure Azure credentials
```

---

## Quick Start Example

### Minimal Example

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    async for message in query(
        prompt="What files are in this directory?",
        options=ClaudeAgentOptions(allowed_tools=["Bash", "Glob"])
    ):
        print(message)

asyncio.run(main())
```

### Bug-Finding Agent

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

async def find_and_fix_bugs():
    options = ClaudeAgentOptions(
        system_prompt="You are an expert Python developer",
        permission_mode='acceptEdits',
        cwd="/path/to/project",
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
    )

    async for message in query(
        prompt="Find and fix bugs in auth.py",
        options=options
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)

asyncio.run(find_and_fix_bugs())
```

### Code Analysis Agent (Read-Only)

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def analyze_codebase():
    async for message in query(
        prompt="Analyze this codebase for security vulnerabilities",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Glob", "Grep", "Task"],  # Task enables subagents
            permission_mode="bypassPermissions"  # Safe for read-only tools
        )
    ):
        print(message)

asyncio.run(analyze_codebase())
```

---

## SDK vs Other Claude Tools

### Agent SDK vs Anthropic Client SDK

| Aspect | Anthropic Client SDK | Claude Agent SDK |
|--------|---------------------|------------------|
| **Tool Loop** | You implement it | Claude handles it |
| **Built-in Tools** | None | File, shell, web, etc. |
| **Use Case** | Custom tool implementations | Agentic automation |

```python
# Client SDK: You implement the tool loop
response = client.messages.create(...)
while response.stop_reason == "tool_use":
    result = your_tool_executor(response.tool_use)
    response = client.messages.create(tool_result=result, ...)

# Agent SDK: Claude handles tools autonomously
async for message in query(prompt="Fix the bug in auth.py"):
    print(message)
```

### Agent SDK vs Claude Code CLI

| Use Case | Best Choice |
|----------|-------------|
| Interactive development | CLI |
| CI/CD pipelines | SDK |
| Custom applications | SDK |
| One-off tasks | CLI |
| Production automation | SDK |

---

## Migration from claude-code-sdk

### Package Changes

```bash
# Uninstall old package
pip uninstall claude-code-sdk

# Install new package
pip install claude-agent-sdk
```

### Import Changes

```python
# BEFORE (v0.0.x)
from claude_code_sdk import query, ClaudeCodeOptions

# AFTER (v0.1.0+)
from claude_agent_sdk import query, ClaudeAgentOptions
```

### Breaking Changes in v0.1.0

#### 1. System Prompt is Empty by Default

```python
# BEFORE: Used Claude Code's system prompt by default
options = ClaudeCodeOptions()

# AFTER: Must explicitly request Claude Code preset
options = ClaudeAgentOptions(
    system_prompt={"type": "preset", "preset": "claude_code"}
)
```

**Why:** Provides better control and isolation for SDK applications.

#### 2. Settings Sources No Longer Loaded by Default

```python
# BEFORE: Loaded all filesystem settings automatically
options = ClaudeCodeOptions()

# AFTER: Must explicitly configure setting_sources
options = ClaudeAgentOptions(
    setting_sources=["user", "project", "local"]  # To get old behavior
)
```

**Why:** Ensures predictable behavior independent of local configurations. Important for:
- CI/CD environments
- Deployed applications
- Multi-tenant systems

#### 3. Type Renamed

```python
# BEFORE
ClaudeCodeOptions(...)

# AFTER
ClaudeAgentOptions(...)
```

### Quick Migration Checklist

- [ ] Update package: `pip install claude-agent-sdk`
- [ ] Change imports: `claude_code_sdk` → `claude_agent_sdk`
- [ ] Rename type: `ClaudeCodeOptions` → `ClaudeAgentOptions`
- [ ] Add `system_prompt={"type": "preset", "preset": "claude_code"}` if you want Claude Code's behavior
- [ ] Add `setting_sources=["project"]` if you need CLAUDE.md or filesystem settings

---

## Official Resources

- **Overview**: https://docs.anthropic.com/en/docs/agent-sdk/overview
- **Python SDK**: https://docs.anthropic.com/en/docs/agent-sdk/python
- **Custom Tools**: https://docs.anthropic.com/en/docs/agent-sdk/custom-tools
- **MCP Integration**: https://docs.anthropic.com/en/docs/agent-sdk/mcp
- **Sessions**: https://docs.anthropic.com/en/docs/agent-sdk/sessions
- **Permissions**: https://docs.anthropic.com/en/docs/agent-sdk/permissions
- **Hosting**: https://docs.anthropic.com/en/docs/agent-sdk/hosting
- **Secure Deployment**: https://docs.anthropic.com/en/docs/agent-sdk/secure-deployment
- **Cost Tracking**: https://docs.anthropic.com/en/docs/agent-sdk/cost-tracking
- **Migration Guide**: https://docs.anthropic.com/en/docs/agent-sdk/migration-guide

---

*See also: [02_CORE_API_TOOLS.md](./02_CORE_API_TOOLS.md) for detailed API usage*
