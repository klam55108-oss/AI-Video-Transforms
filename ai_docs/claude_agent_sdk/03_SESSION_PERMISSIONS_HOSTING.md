# Claude Agent SDK - Sessions, Permissions & Production Hosting

> **Reference:** Python SDK v0.1.0+ (Docs v0.5.0)
> **Focus:** Session lifecycle, permissions, security, sandbox, production deployment
> **See Also:** [Secure Deployment](https://docs.anthropic.com/en/docs/agent-sdk/secure-deployment) for network controls, credential management, and isolation

---

## Table of Contents

1. [Session Management](#session-management)
2. [Permissions & Security](#permissions--security)
3. [Hooks System](#hooks-system)
4. [Sandbox Configuration](#sandbox-configuration)
5. [Production Hosting](#production-hosting)

---

## Session Management

### Session Lifecycle

Sessions maintain conversation state and enable resumption across multiple interactions.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Start Query │ ──▶ │  System     │ ──▶ │ Multi-turn  │
│ (new session)│     │  Init Msg   │     │ Conversation│
└─────────────┘     │ session_id! │     └─────────────┘
                    └─────────────┘             │
                                                ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Resume    │ ◀── │ Store       │ ◀── │  Result     │
│ (later)     │     │ session_id  │     │  Message    │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Getting the Session ID

```python
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

session_id = None

async for message in query(
    prompt="Help me build a web application",
    options=ClaudeAgentOptions(model="sonnet")
):
    # Method 1: From system init message
    if hasattr(message, 'subtype') and message.subtype == 'init':
        session_id = message.data.get('session_id')
        print(f"Session started: {session_id}")

    # Method 2: From result message (always available)
    if isinstance(message, ResultMessage):
        session_id = message.session_id
        print(f"Session completed: {session_id}")
```

### Resuming Sessions

```python
from claude_agent_sdk import query, ClaudeAgentOptions

# Resume a previous session
async for message in query(
    prompt="Continue implementing the authentication",
    options=ClaudeAgentOptions(
        resume="session-abc123",  # ID from previous session
        model="sonnet",
        allowed_tools=["Read", "Edit", "Write", "Bash"]
    )
):
    print(message)
```

### Forking Sessions

Fork creates a new session branch while preserving the original.

| Behavior | `fork_session=False` (default) | `fork_session=True` |
|----------|-------------------------------|---------------------|
| Session ID | Same as original | New ID generated |
| History | Appends to original | Creates new branch |
| Original | Modified | Preserved unchanged |
| Use Case | Continue linear work | Explore alternatives |

```python
# Original session
async for message in query(
    prompt="Help me design a REST API",
    options=ClaudeAgentOptions(model="sonnet")
):
    if isinstance(message, ResultMessage):
        original_session = message.session_id

# Fork to try GraphQL approach
async for message in query(
    prompt="Actually, let's redesign this as GraphQL",
    options=ClaudeAgentOptions(
        resume=original_session,
        fork_session=True,  # Creates new branch!
        model="sonnet"
    )
):
    if isinstance(message, ResultMessage):
        graphql_session = message.session_id

# Original session is unchanged - can still resume
async for message in query(
    prompt="Add pagination to the REST API",
    options=ClaudeAgentOptions(
        resume=original_session,
        fork_session=False  # Continue original
    )
):
    print(message)
```

### When to Fork

- Explore different implementation approaches
- Create backup points before risky changes
- Run A/B tests on different strategies
- Maintain separate branches for different features

---

## Permissions & Security

### Permission Flow

```
Tool Request
     │
     ▼
┌─────────────────┐
│ PreToolUse Hook │ ──▶ Allow/Deny/Ask/Continue
└────────┬────────┘
         │ Continue
         ▼
┌─────────────────┐
│   Deny Rules    │ ──▶ Match → Denied
└────────┬────────┘
         │ No Match
         ▼
┌─────────────────┐
│   Allow Rules   │ ──▶ Match → Execute
└────────┬────────┘
         │ No Match
         ▼
┌─────────────────┐
│   Ask Rules     │ ──▶ Match → canUseTool Callback
└────────┬────────┘
         │ No Match
         ▼
┌─────────────────┐
│ Permission Mode │
│  Check          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│canUseTool       │ ──▶ Allow/Deny
│Callback         │
└────────┬────────┘
         │ Allow
         ▼
    Execute Tool
         │
         ▼
┌─────────────────┐
│ PostToolUse Hook│
└─────────────────┘
```

### Permission Modes

| Mode | Description | Behavior |
|------|-------------|----------|
| `default` | Standard checks | Normal permission flow |
| `acceptEdits` | Auto-approve edits | File operations approved automatically |
| `bypassPermissions` | Auto-approve all | All tools approved (use with caution!) |
| `plan` | Planning only | Read-only tools only (**Not supported in SDK**) |

```python
from claude_agent_sdk import ClaudeAgentOptions

# Standard behavior
options = ClaudeAgentOptions(permission_mode='default')

# Auto-approve file edits (good for controlled environments)
options = ClaudeAgentOptions(permission_mode='acceptEdits')

# Full automation (dangerous - use only in sandboxed containers)
options = ClaudeAgentOptions(permission_mode='bypassPermissions')
```

### Tool Allow/Disallow Lists

```python
options = ClaudeAgentOptions(
    # Explicit allowlist
    allowed_tools=[
        "Read", "Grep", "Glob",  # Built-in tools
        "mcp__mytools__custom"   # Custom MCP tool
    ],

    # Explicit denylist
    disallowed_tools=[
        "Bash",  # Prevent shell access
        "Write"  # Prevent file creation
    ]
)
```

### Custom Permission Handler (canUseTool)

```python
from claude_agent_sdk import ClaudeAgentOptions

async def custom_permission_handler(tool_name: str, input_data: dict) -> dict:
    """Custom logic for tool permissions."""

    # Block writes to system directories
    if tool_name == "Write":
        file_path = input_data.get("file_path", "")
        if file_path.startswith("/etc/") or file_path.startswith("/system/"):
            return {
                "behavior": "deny",
                "message": "System directory writes are not allowed"
            }

    # Redirect sensitive operations to sandbox
    if tool_name in ["Write", "Edit"]:
        file_path = input_data.get("file_path", "")
        if "config" in file_path or "secrets" in file_path:
            return {
                "behavior": "deny",
                "message": "Cannot modify config or secrets files"
            }

    # Auto-approve everything else
    return {"behavior": "allow", "updatedInput": input_data}


options = ClaudeAgentOptions(
    can_use_tool=custom_permission_handler,
    allowed_tools=["Read", "Write", "Edit", "Bash"]
)
```

### canUseTool Return Format

```python
# Allow the operation
{"behavior": "allow", "updatedInput": input_data}

# Allow with modified input
{"behavior": "allow", "updatedInput": {"file_path": "/safe/path/file.txt"}}

# Deny with explanation
{"behavior": "deny", "message": "Reason for denial"}
```

---

## Hooks System

### Available Hook Events (Python SDK)

| Event | Supported | Trigger | Example Use Case |
|-------|-----------|---------|------------------|
| `PreToolUse` | ✅ | Tool call request (can block/modify) | Block dangerous shell commands |
| `PostToolUse` | ✅ | Tool execution result | Log file changes to audit trail |
| `UserPromptSubmit` | ✅ | User prompt submission | Inject additional context |
| `Stop` | ✅ | Agent execution stop | Save session state |
| `SubagentStop` | ✅ | Subagent completion | Aggregate results |
| `PreCompact` | ✅ | Conversation compaction | Archive full transcript |
| `PostToolUseFailure` | ❌ | Tool execution failure | *(Not available in Python SDK)* |
| `SubagentStart` | ❌ | Subagent initialization | *(Not available in Python SDK)* |
| `PermissionRequest` | ❌ | Permission dialog displayed | *(Not available in Python SDK)* |
| `SessionStart` | ❌ | Session initialization | *(Not available in Python SDK)* |
| `SessionEnd` | ❌ | Session termination | *(Not available in Python SDK)* |
| `Notification` | ❌ | Agent status messages | *(Not available in Python SDK)* |

### Hook Callback Input Fields

**Common fields** (all hooks):
- `hook_event_name`: The hook type (`PreToolUse`, `PostToolUse`, etc.)
- `session_id`: Current session identifier
- `transcript_path`: Path to conversation transcript
- `cwd`: Current working directory

**Hook-specific fields**:

| Field | Type | Hooks |
|-------|------|-------|
| `tool_name` | `str` | PreToolUse, PostToolUse |
| `tool_input` | `dict` | PreToolUse, PostToolUse |
| `tool_response` | `Any` | PostToolUse |
| `prompt` | `str` | UserPromptSubmit |
| `stop_hook_active` | `bool` | Stop, SubagentStop |
| `trigger` | `str` | PreCompact (`manual` or `auto`) |
| `custom_instructions` | `str` | PreCompact |

### Hook Implementation

```python
from claude_agent_sdk import query, ClaudeAgentOptions, HookMatcher, HookContext
from typing import Any
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def log_all_tools(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: HookContext
) -> dict[str, Any]:
    """Log all tool usage."""
    tool_name = input_data.get('tool_name', 'unknown')
    logger.info(f"Tool called: {tool_name}")
    return {}


async def block_dangerous_commands(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: HookContext
) -> dict[str, Any]:
    """Block dangerous bash commands."""
    if input_data.get('tool_name') != 'Bash':
        return {}

    command = input_data.get('tool_input', {}).get('command', '')

    dangerous_patterns = [
        'rm -rf /',
        'rm -rf ~',
        'dd if=',
        ':(){:|:&};:',  # Fork bomb
        'chmod -R 777 /'
    ]

    for pattern in dangerous_patterns:
        if pattern in command:
            return {
                'hookSpecificOutput': {
                    'hookEventName': 'PreToolUse',
                    'permissionDecision': 'deny',
                    'permissionDecisionReason': f'Dangerous command blocked: {pattern}'
                }
            }

    return {}


options = ClaudeAgentOptions(
    hooks={
        'PreToolUse': [
            # Apply to all tools
            HookMatcher(hooks=[log_all_tools]),
            # Only apply to Bash tool
            HookMatcher(matcher='Bash', hooks=[block_dangerous_commands], timeout=120)
        ],
        'PostToolUse': [
            HookMatcher(hooks=[log_all_tools])
        ]
    }
)
```

### Hook Return Format

**Top-level fields** (outside `hookSpecificOutput`):

| Field | Type | Description |
|-------|------|-------------|
| `continue` | `bool` | Whether agent should continue (default: `True`) |
| `stopReason` | `str` | Message shown when `continue=False` |
| `suppressOutput` | `bool` | Hide stdout from transcript (default: `False`) |
| `systemMessage` | `str` | Message injected for Claude to see |

**Fields inside `hookSpecificOutput`**:

| Field | Type | Hooks | Description |
|-------|------|-------|-------------|
| `hookEventName` | `str` | All | Required. Use `input.hook_event_name` |
| `permissionDecision` | `'allow' \| 'deny' \| 'ask'` | PreToolUse | Controls tool execution |
| `permissionDecisionReason` | `str` | PreToolUse | Explanation for decision |
| `updatedInput` | `dict` | PreToolUse | Modified tool input (requires `allow`) |
| `additionalContext` | `str` | PostToolUse, UserPromptSubmit | Context for conversation |

```python
# Continue with default behavior
return {}

# Block the operation
return {
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': 'Reason here'
    }
}

# Allow with modified input
return {
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'allow',
        'updatedInput': {
            **input_data['tool_input'],
            'file_path': '/sandbox' + input_data['tool_input'].get('file_path', '')
        }
    }
}

# Add system message
return {
    'systemMessage': 'Important: This operation was modified'
}

# Auto-approve read-only tools
return {
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'allow',
        'permissionDecisionReason': 'Read-only tool auto-approved'
    }
}
```

### Permission Decision Flow

When multiple hooks or rules apply:
1. **Deny** rules checked first (any match = immediate denial)
2. **Ask** rules checked second
3. **Allow** rules checked third
4. **Default to Ask** if nothing matches

If any hook returns `deny`, the operation is blocked—other hooks returning `allow` won't override it.

---

## Sandbox Configuration

### SandboxSettings Structure

```python
from claude_agent_sdk import ClaudeAgentOptions

sandbox_config = {
    "enabled": True,
    "autoAllowBashIfSandboxed": True,  # Auto-approve bash in sandbox
    "excludedCommands": ["docker", "kubectl"],  # Never run these

    "network": {
        "allowLocalBinding": True,  # Allow localhost binding
        "allowUnixSockets": ["/var/run/docker.sock"]  # Allowed unix sockets
    },

    "ignoreViolations": {
        "fakeRoot": False,  # Whether to ignore root violations
        "network": False,   # Whether to ignore network violations
        "filesystem": []    # List of paths to ignore filesystem violations
    }
}

options = ClaudeAgentOptions(sandbox=sandbox_config)
```

### Sandbox Best Practices

1. **Always sandbox in production** - Never run untrusted code unsandboxed
2. **Restrict network access** - Limit to necessary endpoints only
3. **Use excludedCommands** - Block known dangerous commands
4. **Monitor violations** - Log but don't ignore sandbox violations

---

## Secure Deployment

### Security Principles

1. **Security Boundaries**: Place sensitive resources (credentials) outside the agent's environment
2. **Least Privilege**: Restrict agent to only required capabilities
3. **Defense in Depth**: Layer multiple controls

### Credential Management: The Proxy Pattern

**Never give agents direct access to API keys.** Instead, run a proxy outside the agent's boundary:

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Container                           │
│   ┌─────────────┐                                           │
│   │ Agent sends │ ─────▶ Unix Socket ─────┐                 │
│   │ request     │        (no API key)     │                 │
│   └─────────────┘                         │                 │
└───────────────────────────────────────────┼─────────────────┘
                                            │
┌───────────────────────────────────────────▼─────────────────┐
│                    Host (Trusted Zone)                       │
│   ┌──────────────────────────────────────────────────────┐  │
│   │                     Proxy                             │  │
│   │   1. Validate request (domain allowlist)             │  │
│   │   2. Inject credentials (API keys)                   │  │
│   │   3. Log for audit                                   │  │
│   │   4. Forward to external API                         │  │
│   └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Configuring Proxy for API Calls

```bash
# Option 1: ANTHROPIC_BASE_URL (sampling requests only)
export ANTHROPIC_BASE_URL="http://localhost:8080"

# Option 2: HTTP_PROXY/HTTPS_PROXY (system-wide)
export HTTP_PROXY="http://localhost:8080"
export HTTPS_PROXY="http://localhost:8080"
```

### Isolation Technologies

| Technology | Isolation | Performance | Complexity |
|------------|-----------|-------------|------------|
| **Sandbox Runtime** | Good (secure defaults) | Very low | Low |
| **Containers (Docker)** | Setup dependent | Low | Medium |
| **gVisor** | Excellent | Medium/High | Medium |
| **VMs (Firecracker)** | Excellent | High | High |

### Hardened Docker Configuration

```bash
docker run \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=100m \
  --network none \
  --memory 2g \
  --pids-limit 100 \
  --user 1000:1000 \
  -v /path/to/code:/workspace:ro \
  -v /var/run/proxy.sock:/var/run/proxy.sock:ro \
  agent-image
```

### Files to NEVER Mount

| File | Risk |
|------|------|
| `.env`, `.env.local` | API keys, secrets |
| `~/.git-credentials` | Git tokens |
| `~/.aws/credentials` | AWS access keys |
| `~/.config/gcloud/` | Google Cloud tokens |
| `~/.azure/` | Azure credentials |
| `~/.docker/config.json` | Registry auth |
| `~/.kube/config` | Kubernetes credentials |
| `*.pem`, `*.key` | Private keys |

---

## Production Hosting

### System Requirements

| Resource | Recommendation |
|----------|----------------|
| **Python** | 3.10+ |
| **Node.js** | 18+ (required by CLI) |
| **RAM** | 1 GiB minimum |
| **Disk** | 5 GiB minimum |
| **CPU** | 1 vCPU minimum |
| **Network** | Outbound HTTPS to `api.anthropic.com` |

### Deployment Patterns

#### Pattern 1: Ephemeral Sessions

Create container per task, destroy when complete.

**Best for:** One-off tasks, stateless operations

```python
# Bug fix task - container destroyed after completion
async for message in query(
    prompt="Fix the bug in auth.py",
    options=ClaudeAgentOptions(
        permission_mode='acceptEdits',
        max_turns=20
    )
):
    print(message)
```

**Use cases:**
- Bug investigation & fix
- Invoice/document processing
- Translation tasks
- Code reviews

#### Pattern 2: Long-Running Sessions

Maintain persistent containers for continuous tasks.

**Best for:** Proactive agents, high-frequency interactions

```python
# Email agent - runs continuously
async def email_agent():
    while True:
        emails = await fetch_new_emails()
        for email in emails:
            async for message in query(
                prompt=f"Process this email: {email.body}",
                options=ClaudeAgentOptions(...)
            ):
                await handle_response(message)
        await asyncio.sleep(60)  # Check every minute
```

**Use cases:**
- Email triage agents
- Slack bots
- Monitoring agents
- Site builders

#### Pattern 3: Hybrid Sessions

Ephemeral containers with session resumption.

**Best for:** Intermittent interaction, cost optimization

```python
# Resume from last session
session_id = await load_session_from_db(user_id)

async for message in query(
    prompt=user_input,
    options=ClaudeAgentOptions(
        resume=session_id,  # Continue previous work
        max_turns=10
    )
):
    if isinstance(message, ResultMessage):
        await save_session_to_db(user_id, message.session_id)
```

**Use cases:**
- Project managers
- Research assistants
- Customer support

### Docker Example

```dockerfile
FROM python:3.11-slim

# Install Node.js for Claude Code CLI
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Install Python SDK
RUN pip install claude-agent-sdk aiohttp

# Create non-root user
RUN useradd -m -u 1000 agent
USER agent

WORKDIR /app
COPY . .

CMD ["python", "agent.py"]
```

### Kubernetes Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: claude-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: claude-agent
  template:
    metadata:
      labels:
        app: claude-agent
    spec:
      containers:
      - name: agent
        image: your-registry/claude-agent:latest
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1"
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: anthropic-secrets
              key: api-key
        securityContext:
          runAsNonRoot: true
          readOnlyRootFilesystem: true
          allowPrivilegeEscalation: false
```

### Sandbox Providers

| Provider | Type | Best For |
|----------|------|----------|
| [Cloudflare Sandboxes](https://github.com/cloudflare/sandbox-sdk) | Edge | Low latency, global |
| [Modal Sandboxes](https://modal.com/docs/guide/sandbox) | Serverless | Python workloads |
| [Daytona](https://www.daytona.io/) | Dev environments | Full IDE |
| [E2B](https://e2b.dev/) | Cloud | Code execution |
| [Fly Machines](https://fly.io/docs/machines/) | Containers | Long-running |
| [Vercel Sandbox](https://vercel.com/docs/functions/sandbox) | Serverless | Next.js/Vercel integration |

For self-hosted options (Docker, gVisor, Firecracker) and detailed isolation configuration, see [Isolation Technologies](https://docs.anthropic.com/en/docs/agent-sdk/secure-deployment#isolation-technologies).

### Security Checklist

- [ ] Never expose API keys in containers
- [ ] Use non-root users in containers
- [ ] Enable sandbox mode for untrusted code
- [ ] Restrict network egress to necessary endpoints
- [ ] Use `max_turns` to prevent infinite loops
- [ ] Implement rate limiting
- [ ] Log all tool usage for auditing
- [ ] Use `excludedCommands` to block dangerous operations
- [ ] Regularly update the Claude Code CLI

### Cost Optimization

```python
options = ClaudeAgentOptions(
    # Use cheaper model for simple tasks
    model="haiku",

    # Limit turns to control costs
    max_turns=10,

    # Use session resumption instead of recreating context
    resume=previous_session_id
)
```

---

## Production FAQ

### How do I communicate with my sandboxes?
When hosting in containers, expose ports to communicate with your SDK instances. Your application can expose HTTP/WebSocket endpoints for external clients while the SDK runs internally within the container.

### What is the cost of hosting a container?
The dominant cost of serving agents is the tokens. Container costs vary based on provisioning, but a minimum cost is roughly 5 cents per hour running.

### When should I shut down idle containers vs. keeping them warm?
This is provider-dependent. Different sandbox providers allow different criteria for idle timeouts. Tune this timeout based on how frequent user responses might be.

### How often should I update the Claude Code CLI?
The Claude Code CLI uses semver. Breaking changes will be versioned. Check for updates regularly but breaking changes are documented.

### How do I monitor container health and agent performance?
Since containers are just servers, the same logging infrastructure you use for the backend will work for containers. Log all tool usage for auditing.

### How long can an agent session run before timing out?
An agent session will not timeout, but set a `max_turns` property to prevent Claude from getting stuck in a loop.

---

*See also: [04_API_REFERENCE.md](./04_API_REFERENCE.md) for complete type definitions*
