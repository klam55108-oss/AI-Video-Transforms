# Claude Agent SDK - File Checkpointing

> **Reference:** Python SDK v0.1.0+ (Docs v0.5.0)
> **Focus:** File versioning, automatic restoration, reversible experimentation
> **New in:** v0.1.0

---

## Table of Contents

1. [Overview](#overview)
2. [Enabling File Checkpointing](#enabling-file-checkpointing)
3. [Rewinding Files](#rewinding-files)
4. [Use Cases](#use-cases)
5. [Best Practices](#best-practices)

---

## Overview

File Checkpointing enables automatic versioning of file changes made by Claude. This allows you to:

- **Track all file modifications** during agent execution
- **Restore files** to their original state after experimentation
- **Implement rollback workflows** for production deployments
- **Enable safe exploration** of code changes

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Session                             │
│                                                             │
│   ┌─────────┐     ┌─────────┐     ┌─────────┐              │
│   │ File A  │ ──▶ │ Edit A  │ ──▶ │ File A' │              │
│   │(original)│     │         │     │(modified)│              │
│   └─────────┘     └─────────┘     └─────────┘              │
│        │                               │                    │
│        └───────────┬───────────────────┘                    │
│                    ▼                                        │
│            ┌─────────────┐                                  │
│            │ Checkpoint  │ ← Stores original state          │
│            │   Storage   │                                  │
│            └─────────────┘                                  │
│                    │                                        │
│                    ▼                                        │
│            ┌─────────────┐                                  │
│            │rewind_files()│ ← Restores original state       │
│            └─────────────┘                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Enabling File Checkpointing

### Basic Usage with query()

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def experiment_with_code():
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="acceptEdits",
        enable_file_checkpointing=True  # Enable checkpointing!
    )

    async for message in query(
        prompt="Refactor the authentication module to use async/await",
        options=options
    ):
        print(message)

asyncio.run(experiment_with_code())
```

### Usage with ClaudeSDKClient

```python
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async def interactive_refactoring():
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit"],
        permission_mode="acceptEdits",
        enable_file_checkpointing=True
    )

    async with ClaudeSDKClient(options) as client:
        # First attempt - make changes
        await client.query("Add comprehensive error handling to api.py")
        async for message in client.receive_response():
            print(message)

        # Review changes, decide to undo
        print("\n--- Reverting changes ---\n")
        await client.rewind_files()  # Restore all files!

        # Try a different approach
        await client.query("Add simple try/except blocks to api.py instead")
        async for message in client.receive_response():
            print(message)

asyncio.run(interactive_refactoring())
```

---

## Rewinding Files

### The rewind_files() Method

The `rewind_files()` method restores all modified files to their state at the start of the session.

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async def safe_experimentation():
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "Bash"],
        enable_file_checkpointing=True
    )

    async with ClaudeSDKClient(options) as client:
        # Store initial state
        await client.query("Show me the current state of config.py")
        async for message in client.receive_response():
            print(message)

        # Make experimental changes
        await client.query("Add a new logging configuration section")
        async for message in client.receive_response():
            print(message)

        # Test the changes
        await client.query("Run the tests to verify the changes")
        async for message in client.receive_response():
            if "FAILED" in str(message):
                # Revert if tests fail!
                print("Tests failed, reverting...")
                await client.rewind_files()
                print("Files restored to original state")

asyncio.run(safe_experimentation())
```

### What Gets Restored

| File Operation | Restored on Rewind |
|----------------|-------------------|
| **Edit** existing file | ✅ Original content restored |
| **Write** new file | ✅ File deleted |
| **Delete** file (via Bash) | ⚠️ Not automatically restored |
| **External changes** | ❌ Not tracked |

**Note:** Only changes made through Claude's tools (Write, Edit) are tracked. External modifications or deletions via Bash are not automatically restored.

---

## Use Cases

### 1. A/B Testing Code Approaches

```python
async def ab_test_implementations():
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "Bash"],
        enable_file_checkpointing=True
    )

    async with ClaudeSDKClient(options) as client:
        # Approach A: ORM-based
        await client.query("Implement the user repository using SQLAlchemy ORM")
        async for message in client.receive_response():
            pass

        # Run benchmarks
        await client.query("Run performance benchmarks on the repository")
        async for message in client.receive_response():
            orm_performance = extract_performance(message)

        # Revert to try Approach B
        await client.rewind_files()

        # Approach B: Raw SQL
        await client.query("Implement the user repository using raw SQL queries")
        async for message in client.receive_response():
            pass

        # Compare performance
        await client.query("Run the same performance benchmarks")
        async for message in client.receive_response():
            sql_performance = extract_performance(message)

        # Choose the better approach
        if orm_performance > sql_performance:
            await client.rewind_files()
            await client.query("Re-implement using SQLAlchemy ORM (better performance)")
```

### 2. Safe Deployment Preparation

```python
async def prepare_deployment():
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob"],
        enable_file_checkpointing=True,
        permission_mode="acceptEdits"
    )

    async with ClaudeSDKClient(options) as client:
        # Make deployment changes
        await client.query("""
            Prepare for production deployment:
            1. Update version numbers
            2. Generate changelog
            3. Update deployment configs
        """)
        async for message in client.receive_response():
            print(message)

        # Verify changes
        await client.query("Run all validation checks")
        async for message in client.receive_response():
            if "ERROR" in str(message):
                print("Validation failed - reverting all changes")
                await client.rewind_files()
                return False

        print("Deployment preparation complete!")
        return True
```

### 3. Interactive Code Review with Rollback

```python
async def interactive_review():
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
        enable_file_checkpointing=True
    )

    async with ClaudeSDKClient(options) as client:
        # Get suggestions
        await client.query("Review the codebase and suggest improvements")
        async for message in client.receive_response():
            print(message)

        # Apply suggestions incrementally
        while True:
            user_input = input("\nApply suggestion? (y/n/revert/done): ")

            if user_input == "revert":
                await client.rewind_files()
                print("All changes reverted")
            elif user_input == "done":
                break
            elif user_input == "y":
                await client.query("Apply the next suggested improvement")
                async for message in client.receive_response():
                    print(message)
```

### 4. Training Data Generation

```python
async def generate_training_variations():
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit"],
        enable_file_checkpointing=True
    )

    variations = []

    async with ClaudeSDKClient(options) as client:
        for style in ["minimal", "verbose", "enterprise"]:
            # Generate variation
            await client.query(f"Rewrite the API using {style} coding style")
            async for message in client.receive_response():
                pass

            # Save the variation
            with open(f"api_{style}.py", "r") as f:
                variations.append(f.read())

            # Reset for next variation
            await client.rewind_files()

    return variations
```

---

## Best Practices

### 1. Always Enable for Experimental Work

```python
# ✅ Enable checkpointing for any experimental or risky changes
options = ClaudeAgentOptions(
    enable_file_checkpointing=True,
    permission_mode="acceptEdits"
)

# ❌ Avoid for read-only operations (unnecessary overhead)
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Grep", "Glob"],  # Read-only
    enable_file_checkpointing=False  # Not needed
)
```

### 2. Combine with Permission Modes

```python
# Safe automation with rollback capability
options = ClaudeAgentOptions(
    enable_file_checkpointing=True,
    permission_mode="acceptEdits",  # Auto-approve file changes
    max_turns=20  # Limit iterations
)
```

### 3. Use with Session Resumption

```python
# Checkpoints persist across session resumption
async for message in query(
    prompt="Continue the refactoring",
    options=ClaudeAgentOptions(
        resume="session-abc123",
        enable_file_checkpointing=True  # Checkpoints still available!
    )
):
    print(message)
```

### 4. Handle Partial Rollbacks Manually

File checkpointing is all-or-nothing. For partial rollbacks:

```python
async def partial_rollback():
    async with ClaudeSDKClient(options) as client:
        # Read specific files before changes
        await client.query("Show me the contents of config.py")
        original_config = extract_file_content(...)

        # Make changes to multiple files
        await client.query("Update config.py and api.py")

        # Rewind everything
        await client.rewind_files()

        # Re-apply only desired changes
        await client.query("Only update api.py, leave config.py unchanged")
```

---

## Limitations

| Limitation | Description | Workaround |
|------------|-------------|------------|
| **Bash deletions** | Files deleted via Bash aren't auto-restored | Use Write tool to recreate |
| **External changes** | Changes outside agent aren't tracked | Use version control (git) |
| **All-or-nothing** | Can't selectively restore files | Manual partial rollback |
| **Session-scoped** | Checkpoints lost when session ends | Use git for persistence |

---

## Integration with Version Control

For production workflows, combine file checkpointing with git:

```python
async def git_integrated_workflow():
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob"],
        enable_file_checkpointing=True,
        permission_mode="acceptEdits"
    )

    async with ClaudeSDKClient(options) as client:
        # Create git branch for safety
        await client.query("Create a new git branch 'experiment/refactor'")

        # Make changes with checkpointing
        await client.query("Refactor the authentication system")
        async for message in client.receive_response():
            print(message)

        # If changes are good, commit them
        user_approval = input("Commit changes? (y/n): ")
        if user_approval == "y":
            await client.query("Commit all changes with a descriptive message")
        else:
            # Use checkpointing for quick revert
            await client.rewind_files()
            # Or use git for full history
            await client.query("git checkout main && git branch -D experiment/refactor")
```

---

## API Reference

### ClaudeAgentOptions

```python
@dataclass
class ClaudeAgentOptions:
    enable_file_checkpointing: bool = False
    """Enable automatic file versioning.

    When True:
    - All file changes via Write/Edit are tracked
    - rewind_files() can restore original state
    - Adds slight overhead for file tracking

    When False (default):
    - No file tracking occurs
    - rewind_files() has no effect
    - Slightly better performance
    """
```

### ClaudeSDKClient.rewind_files()

```python
async def rewind_files(self) -> None:
    """Restore all files modified during this session to their original state.

    Requires enable_file_checkpointing=True in options.

    Behavior:
    - Edited files: Restored to original content
    - New files: Deleted
    - Deleted files via Bash: NOT restored (use git for this)

    Raises:
        RuntimeError: If checkpointing was not enabled
    """
```

---

*Documentation based on Claude Agent SDK v0.1.0+ (Docs v0.5.0, December 2025)*
*Official Docs: https://docs.anthropic.com/en/docs/agent-sdk/file-checkpointing*
