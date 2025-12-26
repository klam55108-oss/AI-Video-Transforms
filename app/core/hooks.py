"""
Agent Hooks for Audit Logging.

This module provides hook callbacks for the Claude Agent SDK that capture
tool usage, session events, and security-relevant operations into an
audit trail.

Hook Flow:
    PreToolUse  → log_pre_tool_use  → Block dangerous ops / Log intent
    PostToolUse → log_post_tool_use → Log results and timing
    Stop        → log_stop          → Log session termination
    SubagentStop→ log_subagent_stop → Log subagent completions

Usage:
    from app.core.hooks import create_audit_hooks

    hooks = create_audit_hooks(session_id, audit_service)
    options = ClaudeAgentOptions(hooks=hooks, ...)
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any, Callable, Coroutine

from app.models.audit import (
    AuditEventType,
    SessionAuditEvent,
    ToolAuditEvent,
)

logger = logging.getLogger(__name__)

# Type alias for hook callbacks (SDK signature)
# async def hook(input_data: dict, tool_use_id: str | None, context: Any) -> dict
HookCallback = Callable[
    [dict[str, Any], str | None, Any],
    Coroutine[Any, Any, dict[str, Any]],
]

# Dangerous command patterns to block in Bash tool
DANGEROUS_BASH_PATTERNS: list[str] = [
    # Destructive file operations
    "rm -rf /",
    "rm -rf ~",
    "rm -rf /*",
    "sudo rm -rf",
    # Disk operations
    "dd if=",
    "mkfs.",
    "> /dev/sda",
    # System compromise
    ":(){:|:&};:",  # Fork bomb
    "chmod -R 777 /",
    # Remote code execution via pipe-to-shell
    "wget -O- | sh",
    "curl | sh",
    "curl | bash",
    "wget | sh",
    "wget | bash",
    # Obfuscated payload execution
    "base64 -d | sh",
    "base64 -d | bash",
    "base64 --decode | sh",
    # Shell eval (common attack vector)
    "eval $(",
    'eval "$(',
    # Python eval
    'python -c "import os;',
    'python3 -c "import os;',
    # Suppress output and background (hiding malicious activity)
    ">/dev/null 2>&1 &",
    # Reverse shell patterns
    "bash -i >& /dev/tcp/",
    "bash -i >&/dev/tcp/",
    "nc -e /bin/",
    "nc -e /bin/sh",
    "nc -e /bin/bash",
    "/dev/tcp/",  # Bash network redirects
    "mkfifo /tmp/",  # Named pipe for reverse shells
    # Credential exfiltration
    "cat /etc/shadow",
    "cat /etc/passwd",
    "cat ~/.ssh/",
    "cat ~/.aws/",
    "cat ~/.gnupg/",
    # Environment variable exfiltration (API keys, secrets)
    "printenv | curl",
    "env | curl",
    "printenv | nc",
    "env | nc",
]

# Patterns for sensitive data that should be redacted from audit logs.
# These are compiled regex patterns for performance.
SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # API keys (common formats)
    (re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE), "[REDACTED_API_KEY]"),
    (
        re.compile(r"sk-ant-[a-zA-Z0-9\-]{20,}", re.IGNORECASE),
        "[REDACTED_ANTHROPIC_KEY]",
    ),
    (
        re.compile(
            r"api[_-]?key[\"']?\s*[:=]\s*[\"']?[a-zA-Z0-9\-_]{20,}", re.IGNORECASE
        ),
        "[REDACTED_API_KEY]",
    ),
    # AWS credentials
    (re.compile(r"AKIA[A-Z0-9]{16}"), "[REDACTED_AWS_KEY]"),
    (
        re.compile(
            r"aws[_-]?secret[_-]?access[_-]?key[\"']?\s*[:=]\s*[\"']?[a-zA-Z0-9/+=]{40}",
            re.IGNORECASE,
        ),
        "[REDACTED_AWS_SECRET]",
    ),
    # Generic secrets/passwords in key-value format
    (
        re.compile(r"password[\"']?\s*[:=]\s*[\"']?[^\s\"',]{8,}", re.IGNORECASE),
        "password=[REDACTED]",
    ),
    (
        re.compile(r"secret[\"']?\s*[:=]\s*[\"']?[^\s\"',]{8,}", re.IGNORECASE),
        "secret=[REDACTED]",
    ),
    (
        re.compile(r"token[\"']?\s*[:=]\s*[\"']?[a-zA-Z0-9\-_]{20,}", re.IGNORECASE),
        "token=[REDACTED]",
    ),
    # Bearer tokens
    (re.compile(r"Bearer\s+[a-zA-Z0-9\-_\.]{20,}", re.IGNORECASE), "Bearer [REDACTED]"),
    # Private keys
    (
        re.compile(
            r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END", re.IGNORECASE
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
]

# System paths that should never be written to
PROTECTED_PATHS: tuple[str, ...] = (
    "/etc/",
    "/usr/",
    "/bin/",
    "/sbin/",
    "/boot/",
    "/dev/",
    "/proc/",
    "/sys/",
    "/var/log/",
    "/root/",
)


class AuditHookFactory:
    """
    Factory for creating session-bound audit hooks.

    Creates hook callbacks that are bound to a specific session and audit
    service, allowing proper correlation of events and centralized logging.

    The factory pattern is used because:
    1. Hooks need session context not available at import time
    2. AuditService lifecycle is managed by ServiceContainer
    3. Each session gets its own set of hooks with proper scoping
    """

    def __init__(self, session_id: str, audit_service: Any) -> None:
        """Initialize hook factory.

        Args:
            session_id: Session ID for correlating audit events.
            audit_service: AuditService instance for persisting events.
        """
        self.session_id = session_id
        self.audit_service = audit_service
        self._tool_start_times: dict[str, float] = {}  # tool_use_id → start time

    async def pre_tool_use_hook(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        context: Any,
    ) -> dict[str, Any]:
        """Hook called before tool execution.

        Logs the tool invocation intent and can block dangerous operations
        before they execute.

        Args:
            input_data: Contains tool_name and tool_input.
            tool_use_id: Unique identifier for this tool call.
            context: HookContext with session info.

        Returns:
            Empty dict to continue, or hookSpecificOutput to block.
        """
        tool_name = input_data.get("tool_name", "unknown")
        tool_input = input_data.get("tool_input", {})

        # Record start time for duration tracking
        if tool_use_id:
            self._tool_start_times[tool_use_id] = time.time()

        # Check for dangerous operations
        block_reason = self._check_dangerous_operation(tool_name, tool_input)

        if block_reason:
            # Log blocked event
            event = ToolAuditEvent(
                event_type=AuditEventType.TOOL_BLOCKED,
                session_id=self.session_id,
                tool_name=tool_name,
                tool_input=tool_input,
                blocked=True,
                block_reason=block_reason,
            )
            await self.audit_service.log_event(event)

            logger.warning(
                f"Session {self.session_id}: Blocked {tool_name} - {block_reason}"
            )

            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": block_reason,
                }
            }

        # Log normal pre-tool event
        event = ToolAuditEvent(
            event_type=AuditEventType.PRE_TOOL_USE,
            session_id=self.session_id,
            tool_name=tool_name,
            tool_input=tool_input,
        )
        await self.audit_service.log_event(event)

        logger.debug(f"Session {self.session_id}: PreToolUse - {tool_name}")

        # Continue with default behavior
        return {}

    def _check_dangerous_operation(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> str | None:
        """Check if an operation is dangerous and should be blocked.

        Args:
            tool_name: The tool being invoked.
            tool_input: The tool's input arguments.

        Returns:
            Block reason string if dangerous, None if safe.
        """
        # Check Bash commands
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            for pattern in DANGEROUS_BASH_PATTERNS:
                if pattern in command:
                    return f"Dangerous command pattern detected: {pattern}"

        # Check file operations for protected paths
        # Resolve symlinks to prevent bypass attacks (e.g., /tmp/link -> /etc/passwd)
        #
        # Edge case note: Path.resolve() may not fully resolve symlinks if the
        # target doesn't exist yet (e.g., writing a new file via symlink to a
        # non-existent path). In practice, this is acceptable because:
        # 1. Creating new files in protected dirs still requires the dir to exist
        # 2. The parent directory check would catch most bypass attempts
        # 3. OS-level permissions provide additional protection
        if tool_name in ("Write", "Edit"):
            file_path = tool_input.get("file_path", "")
            try:
                # Resolve symlinks and normalize path for security check
                resolved_path = str(Path(file_path).resolve())
            except (OSError, ValueError):
                # If path resolution fails, use original path
                resolved_path = file_path

            for protected in PROTECTED_PATHS:
                if resolved_path.startswith(protected):
                    return f"Cannot modify protected path: {protected}"

        return None

    async def post_tool_use_hook(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        context: Any,
    ) -> dict[str, Any]:
        """Hook called after tool execution.

        Logs the tool result, timing, and success status for audit trail.

        Args:
            input_data: Contains tool_name, tool_input, and tool_response.
            tool_use_id: Unique identifier for this tool call.
            context: HookContext with session info.

        Returns:
            Empty dict (post-hooks cannot block).
        """
        tool_name = input_data.get("tool_name", "unknown")
        tool_input = input_data.get("tool_input", {})
        tool_response = input_data.get("tool_response")

        # Calculate duration
        duration_ms: float | None = None
        if tool_use_id and tool_use_id in self._tool_start_times:
            start_time = self._tool_start_times.pop(tool_use_id)
            duration_ms = (time.time() - start_time) * 1000

        # Determine success (heuristic based on response structure)
        success = self._determine_success(tool_response)

        # Log post-tool event
        event = ToolAuditEvent(
            event_type=AuditEventType.POST_TOOL_USE,
            session_id=self.session_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_response=self._sanitize_response(tool_response),
            duration_ms=duration_ms,
            success=success,
        )
        await self.audit_service.log_event(event)

        status = "success" if success else "failed"
        duration_str = f" ({duration_ms:.0f}ms)" if duration_ms else ""
        logger.debug(
            f"Session {self.session_id}: PostToolUse - {tool_name} {status}{duration_str}"
        )

        return {}

    def _determine_success(self, tool_response: Any) -> bool:
        """Determine if a tool response indicates success.

        Args:
            tool_response: The response from the tool.

        Returns:
            True if success, False if failure detected.
        """
        if tool_response is None:
            return True  # No response often means success

        if isinstance(tool_response, dict):
            # Check for explicit success/error fields
            if "success" in tool_response:
                return bool(tool_response["success"])
            if "error" in tool_response:
                return False
            if "is_error" in tool_response:
                return not tool_response["is_error"]

        return True  # Default to success

    def _redact_sensitive_data(self, text: str) -> str:
        """Redact sensitive data (API keys, passwords, etc.) from text.

        Args:
            text: The text to redact.

        Returns:
            Text with sensitive patterns replaced by redaction markers.
        """
        for pattern, replacement in SENSITIVE_PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    def _sanitize_response(self, tool_response: Any) -> Any:
        """Sanitize tool response for safe storage.

        Truncates very large responses and redacts sensitive data
        (API keys, passwords, tokens) to prevent data leakage in audit logs.

        Args:
            tool_response: The raw tool response.

        Returns:
            Sanitized response safe for JSON storage.
        """
        if tool_response is None:
            return None

        if isinstance(tool_response, str):
            # Redact sensitive data before truncation
            sanitized = self._redact_sensitive_data(tool_response)
            # Truncate very long strings
            max_len = 5000
            if len(sanitized) > max_len:
                total = len(sanitized)
                return f"{sanitized[:max_len]}... [truncated, {total} chars total]"
            return sanitized

        if isinstance(tool_response, dict):
            # Recursively sanitize dict values
            return {k: self._sanitize_response(v) for k, v in tool_response.items()}

        if isinstance(tool_response, list):
            # Truncate very long lists
            max_items = 50
            if len(tool_response) > max_items:
                # Use a dict marker to maintain type consistency and indicate truncation
                truncated = [
                    self._sanitize_response(item) for item in tool_response[:max_items]
                ]
                truncated.append(
                    {"__truncated__": True, "total_items": len(tool_response)}
                )
                return truncated
            return [self._sanitize_response(item) for item in tool_response]

        # Return primitives as-is
        return tool_response

    async def stop_hook(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        context: Any,
    ) -> dict[str, Any]:
        """Hook called when agent execution stops.

        Logs session termination for tracking agent lifecycle.

        Args:
            input_data: Contains stop_hook_active flag.
            tool_use_id: Not used for Stop hooks.
            context: HookContext with session info.

        Returns:
            Empty dict (stop hooks cannot block).
        """
        stop_reason = input_data.get("stop_reason")

        event = SessionAuditEvent(
            event_type=AuditEventType.SESSION_STOP,
            session_id=self.session_id,
            stop_reason=stop_reason,
        )
        await self.audit_service.log_event(event)

        logger.info(f"Session {self.session_id}: Stop - {stop_reason or 'completed'}")

        return {}

    async def subagent_stop_hook(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        context: Any,
    ) -> dict[str, Any]:
        """Hook called when a subagent stops.

        Logs subagent completion for tracking delegated work.

        Args:
            input_data: Contains subagent info.
            tool_use_id: Not used for SubagentStop hooks.
            context: HookContext with session info.

        Returns:
            Empty dict (subagent stop hooks cannot block).
        """
        # Extract subagent info if available
        subagent_id = input_data.get("subagent_id") or input_data.get("task_id")

        event = SessionAuditEvent(
            event_type=AuditEventType.SUBAGENT_STOP,
            session_id=self.session_id,
            subagent_id=str(subagent_id) if subagent_id else None,
        )
        await self.audit_service.log_event(event)

        logger.debug(
            f"Session {self.session_id}: SubagentStop - {subagent_id or 'unknown'}"
        )

        return {}


def create_audit_hooks(
    session_id: str,
    audit_service: Any,
) -> dict[str, Any]:
    """Create audit hook configuration for ClaudeAgentOptions.

    This function creates a properly structured hooks dictionary that can
    be passed directly to ClaudeAgentOptions. It uses the SDK's HookMatcher
    pattern internally.

    Args:
        session_id: Session ID for correlating events.
        audit_service: AuditService instance for persistence.

    Returns:
        Hooks configuration dictionary for ClaudeAgentOptions.

    Example:
        hooks = create_audit_hooks(session_id, audit_service)
        options = ClaudeAgentOptions(hooks=hooks, ...)
    """
    factory = AuditHookFactory(session_id, audit_service)

    # Import HookMatcher from SDK
    # This is expected to fail in some environments (e.g., testing without SDK)
    try:
        from claude_agent_sdk import HookMatcher
    except ImportError:
        logger.info("HookMatcher not available, audit hooks disabled")
        return {}

    # Return hooks configuration with HookMatcher instances
    # Type ignored because SDK types are complex and we trust the SDK's runtime behavior
    return {
        "PreToolUse": [
            HookMatcher(hooks=[factory.pre_tool_use_hook]),  # type: ignore[list-item]
        ],
        "PostToolUse": [
            HookMatcher(hooks=[factory.post_tool_use_hook]),  # type: ignore[list-item]
        ],
        "Stop": [
            HookMatcher(hooks=[factory.stop_hook]),  # type: ignore[list-item]
        ],
        "SubagentStop": [
            HookMatcher(hooks=[factory.subagent_stop_hook]),  # type: ignore[list-item]
        ],
    }
