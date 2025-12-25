"""
Session Management (Actor Pattern) for the Video Agent Web App.

This module implements the SessionActor pattern to serialize access to the
Claude Agent SDK for each user session, preventing race conditions and
managing session lifecycle.

Includes real-time activity streaming for transparent agent processing UX.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)

from app.core.cost_tracking import UsageData

from app.agent import video_tools_server
from app.agent.prompts import SYSTEM_PROMPT
from app.core.config import get_settings
from app.core.cost_tracking import SessionCost
from app.core.permissions import (
    create_permission_handler,
    get_default_permission_config,
)
from app.core.storage import storage
from app.models.structured import (
    AgentResponse as StructuredAgentResponse,
    get_output_schema,
)

# Logging configuration
logger = logging.getLogger(__name__)

# Agent resources directory for SDK setting_sources
AGENT_RESOURCES_DIR = Path(__file__).parent.parent / "agent" / "resources"

# Configuration constants (backward compatibility)
# NOTE: These are now loaded from Settings but kept as module-level
# accessors for backward compatibility with existing code
RESPONSE_TIMEOUT_SECONDS: float = get_settings().response_timeout
GREETING_TIMEOUT_SECONDS: float = get_settings().greeting_timeout
SESSION_TTL_SECONDS: float = get_settings().session_ttl
CLEANUP_INTERVAL_SECONDS: float = get_settings().cleanup_interval
QUEUE_MAX_SIZE: int = get_settings().queue_max_size
GRACEFUL_SHUTDOWN_TIMEOUT: float = get_settings().graceful_shutdown_timeout


# --------------------------------------------------------------------------
# Message Response Data Class
# --------------------------------------------------------------------------


@dataclass
class MessageUsage:
    """Per-message token usage and cost data."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class MessageResponse:
    """Response data from a single agent interaction."""

    text: str
    usage: MessageUsage


# --------------------------------------------------------------------------
# Activity Tracking for Real-Time UX
# --------------------------------------------------------------------------


class ActivityType(Enum):
    """Types of agent activity for real-time display."""

    THINKING = "thinking"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    SUBAGENT = "subagent"
    FILE_SAVE = "file_save"  # Atomic file writing operations
    COMPLETED = "completed"


@dataclass
class ActivityEvent:
    """An activity event emitted during agent processing.

    These events are streamed to the frontend to provide real-time
    visibility into what the agent is doing (instead of just "3 dots").
    """

    activity_type: ActivityType
    message: str
    tool_name: str | None = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for SSE transmission."""
        return {
            "type": self.activity_type.value,
            "message": self.message,
            "tool_name": self.tool_name,
            "timestamp": self.timestamp,
        }


# Activity streaming configuration
ACTIVITY_QUEUE_MAX_SIZE: int = 100  # Max events per subscriber queue
ACTIVITY_MAX_CONSECUTIVE_DROPS: int = 10  # Auto-unsubscribe after N drops


@dataclass
class ActivitySubscriber:
    """Tracks a subscriber's queue and health for auto-cleanup.

    When a subscriber stops consuming events (e.g., network issues),
    consecutive_drops increases. After ACTIVITY_MAX_CONSECUTIVE_DROPS,
    the subscriber is automatically removed to prevent memory leaks.
    """

    queue: asyncio.Queue[ActivityEvent]
    consecutive_drops: int = 0


# Tool name to human-friendly description mapping
TOOL_DESCRIPTIONS: dict[str, str] = {
    # Transcription tools
    "mcp__video-tools__transcribe_video": "Transcribing video",
    "mcp__video-tools__write_file": "Writing file",
    "mcp__video-tools__save_transcript": "Saving transcript",
    "mcp__video-tools__get_transcript": "Loading transcript",
    "mcp__video-tools__list_transcripts": "Listing transcripts",
    # Knowledge Graph tools
    "mcp__video-tools__extract_to_kg": "Extracting knowledge",
    "mcp__video-tools__list_kg_projects": "Listing KG projects",
    "mcp__video-tools__create_kg_project": "Creating KG project",
    "mcp__video-tools__bootstrap_kg_project": "Bootstrapping KG schema",
    "mcp__video-tools__get_kg_stats": "Getting KG statistics",
    # SDK built-in tools
    "Skill": "Using skill",
    "Read": "Reading file",
    "Write": "Writing file",
    "Edit": "Editing file",
    "Bash": "Running command",
    "Glob": "Finding files",
    "Grep": "Searching files",
    "WebSearch": "Searching web",
    "WebFetch": "Fetching URL",
    "Task": "Delegating to subagent",
    "TodoWrite": "Updating task list",
}

# Tools that perform atomic file saving operations (get FILE_SAVE activity type)
FILE_SAVE_TOOLS: frozenset[str] = frozenset(
    {
        "mcp__video-tools__write_file",
        "mcp__video-tools__save_transcript",
        "Write",
        "Edit",
    }
)


def get_activity_text(msg: Any) -> ActivityEvent | None:
    """
    Extract activity information from a Claude SDK message.

    This function inspects SDK messages to determine what the agent is doing,
    providing real-time feedback for the frontend loading indicator.

    Follows the pattern from Anthropic's Chief of Staff Agent cookbook.

    Args:
        msg: A message from the Claude Agent SDK stream

    Returns:
        ActivityEvent if activity detected, None otherwise
    """
    try:
        class_name = msg.__class__.__name__

        if "Assistant" in class_name:
            if hasattr(msg, "content") and msg.content:
                # Check first content block for tool use
                first_content = (
                    msg.content[0] if isinstance(msg.content, list) else msg.content
                )

                if isinstance(first_content, ToolUseBlock):
                    tool_name = first_content.name
                    description = TOOL_DESCRIPTIONS.get(tool_name, tool_name)

                    # Use FILE_SAVE activity type for file-saving tools
                    if tool_name in FILE_SAVE_TOOLS:
                        return ActivityEvent(
                            activity_type=ActivityType.FILE_SAVE,
                            message=f"💾 {description}",
                            tool_name=tool_name,
                        )

                    return ActivityEvent(
                        activity_type=ActivityType.TOOL_USE,
                        message=f"🔧 {description}",
                        tool_name=tool_name,
                    )

                if isinstance(first_content, TextBlock):
                    return ActivityEvent(
                        activity_type=ActivityType.THINKING,
                        message="🤔 Thinking...",
                    )

            # Default for assistant messages
            return ActivityEvent(
                activity_type=ActivityType.THINKING,
                message="🤔 Thinking...",
            )

        elif "User" in class_name:
            # User messages contain tool results
            if hasattr(msg, "content") and msg.content:
                for block in (
                    msg.content if isinstance(msg.content, list) else [msg.content]
                ):
                    if isinstance(block, ToolResultBlock):
                        return ActivityEvent(
                            activity_type=ActivityType.TOOL_RESULT,
                            message="✅ Tool completed",
                        )

        elif "Result" in class_name:
            return ActivityEvent(
                activity_type=ActivityType.COMPLETED,
                message="✨ Processing complete",
            )

    except (AttributeError, IndexError, TypeError):
        pass

    return None


# --------------------------------------------------------------------------
# Session Management (Actor Pattern)
# --------------------------------------------------------------------------


class SessionActor:
    """
    A dedicated actor that runs the ClaudeSDKClient in its own asyncio task.
    This prevents 'cancel scope' errors by ensuring the client is always
    accessed from the same task context.

    Now includes activity streaming for real-time UX feedback during processing.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.input_queue: asyncio.Queue[str | None] = asyncio.Queue(
            maxsize=QUEUE_MAX_SIZE
        )
        self.response_queue: asyncio.Queue[MessageResponse | Exception] = asyncio.Queue(
            maxsize=QUEUE_MAX_SIZE
        )
        self.greeting_queue: asyncio.Queue[MessageResponse] = asyncio.Queue(maxsize=1)

        # Activity streaming for real-time UX updates
        # Subscribers are wrapped in ActivitySubscriber for health tracking
        self._activity_subscribers: dict[
            asyncio.Queue[ActivityEvent], ActivitySubscriber
        ] = {}
        self._current_activity: ActivityEvent | None = (
            None  # Track actual current activity
        )

        self.active_task: asyncio.Task[None] | None = None
        self._running_event = asyncio.Event()
        self.last_activity: float = time.time()
        self._is_processing: bool = False
        self.session_cost: SessionCost = SessionCost(session_id=session_id)

    @property
    def is_running(self) -> bool:
        """Thread-safe check if session is running."""
        return self._running_event.is_set()

    @property
    def is_processing(self) -> bool:
        """Check if session is currently processing a message."""
        return self._is_processing

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()

    def is_expired(self, ttl: float = SESSION_TTL_SECONDS) -> bool:
        """Check if session has been inactive for longer than TTL."""
        return time.time() - self.last_activity > ttl

    async def start(self) -> None:
        """Starts the background worker task."""
        self._running_event.set()
        self.active_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        """Signals the worker to stop and waits for it to finish."""
        if not self._running_event.is_set():
            return

        self._running_event.clear()

        # Send sentinel to unblock queue waiter
        try:
            self.input_queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

        if self.active_task:
            # Give worker time to exit gracefully
            try:
                await asyncio.wait_for(
                    self.active_task, timeout=GRACEFUL_SHUTDOWN_TIMEOUT
                )
            except asyncio.TimeoutError:
                # Force cancellation
                self.active_task.cancel()
                try:
                    await self.active_task
                except asyncio.CancelledError:
                    logger.debug(f"Session {self.session_id}: Worker force-cancelled")
            except asyncio.CancelledError:
                pass
            finally:
                self.active_task = None

    async def get_greeting(self) -> MessageResponse:
        """Waits for and returns the initial greeting message with usage data."""
        if not self._running_event.is_set():
            raise RuntimeError("Session is closed")

        self.touch()

        try:
            response = await asyncio.wait_for(
                self.greeting_queue.get(), timeout=GREETING_TIMEOUT_SECONDS
            )
            return response
        except asyncio.TimeoutError:
            logger.warning(f"Session {self.session_id}: Greeting timed out")
            return MessageResponse(
                text="Hello! I'm ready to help you transcribe videos. (Note: Initialization was slow)",
                usage=MessageUsage(),
            )

    async def process_message(self, message: str) -> MessageResponse:
        """Sends a message to the agent and awaits the response with usage data."""
        if not self._running_event.is_set() or not self.active_task:
            raise RuntimeError("Session is closed")

        self.touch()
        self._is_processing = True

        try:
            await self.input_queue.put(message)

            get_response = asyncio.create_task(self.response_queue.get())

            done, _ = await asyncio.wait(
                [get_response, self.active_task],
                timeout=RESPONSE_TIMEOUT_SECONDS,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if not done:
                # Timeout occurred
                get_response.cancel()
                try:
                    await get_response
                except asyncio.CancelledError:
                    pass
                raise TimeoutError(
                    f"Response timed out after {RESPONSE_TIMEOUT_SECONDS} seconds"
                )

            if get_response in done:
                result = get_response.result()
                if isinstance(result, Exception):
                    raise result
                return result
            else:
                # Worker task finished before response
                get_response.cancel()
                try:
                    await get_response
                except asyncio.CancelledError:
                    pass

                try:
                    await self.active_task
                except Exception as e:
                    raise RuntimeError(f"Session worker crashed: {e}")

                raise RuntimeError("Session worker stopped unexpectedly")
        finally:
            self._is_processing = False
            self._current_activity = None  # Clear activity tracking
            self.touch()

    def get_cumulative_usage(self) -> MessageUsage:
        """
        Get cumulative session usage data.

        Returns the total cost and token counts accumulated across
        all messages in this session. Since the SDK only provides
        total_cost_usd (not per-message tokens), token counts remain 0.

        Returns:
            MessageUsage with cumulative session cost
        """
        return MessageUsage(
            input_tokens=self.session_cost.total_input_tokens,
            output_tokens=self.session_cost.total_output_tokens,
            cache_creation_tokens=self.session_cost.total_cache_creation_tokens,
            cache_read_tokens=self.session_cost.total_cache_read_tokens,
            cost_usd=self.session_cost.reported_cost_usd,
        )

    # --------------------------------------------------------------------------
    # Activity Streaming Methods
    # --------------------------------------------------------------------------

    def subscribe_to_activity(self) -> asyncio.Queue[ActivityEvent]:
        """
        Subscribe to activity events for real-time streaming.

        Returns a bounded queue (max ACTIVITY_QUEUE_MAX_SIZE events) that will
        receive ActivityEvent objects as the agent processes messages.
        Used by SSE endpoints for frontend streaming.

        Subscribers are automatically removed if they consistently fail to
        consume events (after ACTIVITY_MAX_CONSECUTIVE_DROPS drops).

        Returns:
            Queue for receiving activity events
        """
        subscriber_queue: asyncio.Queue[ActivityEvent] = asyncio.Queue(
            maxsize=ACTIVITY_QUEUE_MAX_SIZE
        )
        self._activity_subscribers[subscriber_queue] = ActivitySubscriber(
            queue=subscriber_queue,
            consecutive_drops=0,
        )
        logger.debug(
            f"Session {self.session_id}: Activity subscriber added "
            f"(total: {len(self._activity_subscribers)})"
        )
        return subscriber_queue

    def unsubscribe_from_activity(self, queue: asyncio.Queue[ActivityEvent]) -> None:
        """
        Unsubscribe from activity events.

        Args:
            queue: The subscriber queue to remove
        """
        self._activity_subscribers.pop(queue, None)
        logger.debug(
            f"Session {self.session_id}: Activity subscriber removed "
            f"(remaining: {len(self._activity_subscribers)})"
        )

    def _emit_activity(self, event: ActivityEvent) -> None:
        """
        Emit an activity event to all subscribers (non-blocking).

        Updates internal current activity tracking and broadcasts to all
        subscribers. Subscribers that consistently fail to consume events
        (queue full) are automatically unsubscribed after
        ACTIVITY_MAX_CONSECUTIVE_DROPS consecutive failures.

        Args:
            event: The activity event to broadcast
        """
        # Track current activity for polling fallback
        self._current_activity = event

        # Collect subscribers to remove (can't modify dict during iteration)
        to_remove: list[asyncio.Queue[ActivityEvent]] = []

        for queue, subscriber in self._activity_subscribers.items():
            try:
                queue.put_nowait(event)
                # Reset drop counter on successful delivery
                subscriber.consecutive_drops = 0
            except asyncio.QueueFull:
                subscriber.consecutive_drops += 1
                if subscriber.consecutive_drops >= ACTIVITY_MAX_CONSECUTIVE_DROPS:
                    logger.warning(
                        f"Session {self.session_id}: Auto-unsubscribing slow subscriber "
                        f"after {subscriber.consecutive_drops} consecutive drops"
                    )
                    to_remove.append(queue)
                else:
                    logger.debug(
                        f"Session {self.session_id}: Activity queue full, "
                        f"drop {subscriber.consecutive_drops}/{ACTIVITY_MAX_CONSECUTIVE_DROPS}"
                    )

        # Remove dead subscribers
        for queue in to_remove:
            self._activity_subscribers.pop(queue, None)

    def get_current_activity(self) -> ActivityEvent | None:
        """
        Get the current activity event (for polling fallback).

        Returns the actual current activity being performed by the agent,
        tracked via _emit_activity calls. This provides accurate status
        for polling clients when SSE is unavailable.

        Note: Activity is cleared when processing completes. If the agent
        is processing but no specific activity has been emitted yet,
        returns a generic "Processing" event.

        Returns:
            Current activity event or None if not processing
        """
        if not self._is_processing:
            return None

        # Return tracked activity if available, otherwise generic processing
        if self._current_activity:
            return self._current_activity

        return ActivityEvent(
            activity_type=ActivityType.THINKING,
            message="🤔 Processing...",
        )

    def _extract_message_text(self, message: AssistantMessage) -> list[str]:
        """
        Extract text content from an AssistantMessage.

        Handles both structured output (Pydantic model) and fallback to
        raw TextBlock content extraction.

        Args:
            message: The AssistantMessage from SDK

        Returns:
            List of text strings extracted from the message
        """
        # Try structured output first
        if hasattr(message, "structured_output") and message.structured_output:
            try:
                parsed = StructuredAgentResponse.model_validate(
                    message.structured_output
                )
                if parsed.message:  # Only return if message is non-empty
                    return [parsed.message]
                else:
                    logger.warning(
                        f"Session {self.session_id}: Structured output has empty message"
                    )
            except Exception as e:
                logger.warning(
                    f"Session {self.session_id}: Failed to parse structured output: {e}"
                )
                # Fall through to text extraction

        # Fallback to TextBlock content
        text_blocks = [
            block.text for block in message.content if isinstance(block, TextBlock)
        ]

        if text_blocks:
            return text_blocks

        # Last resort: try to extract any text from the raw output
        if hasattr(message, "structured_output") and message.structured_output:
            raw_output = message.structured_output
            if isinstance(raw_output, dict) and "message" in raw_output:
                msg = raw_output.get("message")
                if msg:
                    logger.info(
                        f"Session {self.session_id}: Using raw message from structured output"
                    )
                    return [str(msg)]

        return []

    def _extract_usage_from_message(
        self, message: AssistantMessage
    ) -> UsageData | None:
        """
        Extract token usage data from an AssistantMessage.

        The SDK provides per-message usage in AssistantMessage.usage dict.
        This extracts it into our UsageData format for tracking.

        Args:
            message: The AssistantMessage from SDK

        Returns:
            UsageData if usage info available, None otherwise
        """
        if not hasattr(message, "usage") or not message.usage:
            return None

        usage = message.usage
        message_id = getattr(message, "id", "") or ""

        if not message_id:
            return None

        return UsageData(
            message_id=message_id,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
        )

    def _handle_result_message(self, message: ResultMessage) -> str | None:
        """
        Handle ResultMessage including subtype-specific error handling.

        The SDK provides specific subtypes for different outcomes:
        - success: Completed successfully
        - error: General error occurred
        - interrupted: User interrupted execution
        - error_during_execution: Error during tool execution
        - error_max_structured_output_retries: Failed to produce valid JSON

        Args:
            message: The ResultMessage from SDK

        Returns:
            Error message string if error occurred, None if success
        """
        # Update cost tracking (SDK's authoritative source)
        if message.total_cost_usd is not None:
            self.session_cost.set_reported_cost(message.total_cost_usd)

        # Handle subtypes per Claude Agent SDK documentation.
        # The SDK may send ResultMessage with subtype field indicating the outcome:
        # - "success": Explicit success
        # - "error_max_structured_output_retries": Output validation failures
        # - "interrupted": User or system interruption
        # - "error_during_execution": Tool execution error
        #
        # Fallback for subtype=None: Older SDK versions or simple responses may not
        # set subtype. We treat (is_error=False AND subtype=None) as success for
        # backwards compatibility and robustness.
        subtype = getattr(message, "subtype", None)

        if subtype == "success" or (not message.is_error and subtype is None):
            # Explicit success OR implicit success (no error flag, no subtype)
            return None

        # Handle specific error subtypes with user-friendly messages
        if subtype == "error_max_structured_output_retries":
            logger.warning(
                f"Session {self.session_id}: Structured output validation failed repeatedly"
            )
            return (
                "I had trouble formatting my response correctly. "
                "This usually resolves on retry. Please try your request again."
            )

        if subtype == "interrupted":
            logger.info(f"Session {self.session_id}: Request was interrupted")
            return "The request was interrupted."

        if subtype == "error_during_execution":
            logger.error(f"Session {self.session_id}: Error during tool execution")
            return (
                "An error occurred while executing a tool. "
                "Please check the tool inputs and try again."
            )

        # General error
        if message.is_error:
            logger.error(
                f"Session {self.session_id}: General error (subtype={subtype})"
            )
            return "An error occurred processing your request."

        return None

    async def _worker_loop(self) -> None:
        """The main loop that holds the ClaudeSDKClient context."""
        logger.info(f"Session {self.session_id}: Worker started")

        try:
            # Create permission handler
            permission_handler = create_permission_handler(
                get_default_permission_config()
            )

            # Debug: Log system prompt info
            logger.info(
                f"Session {self.session_id}: System prompt length={len(SYSTEM_PROMPT)}, "
                f"starts with: {SYSTEM_PROMPT[:100]!r}..."
            )

            options = ClaudeAgentOptions(
                model=get_settings().claude_model,
                system_prompt={
                    "type": "preset",
                    "preset": "claude_code",
                    "append": SYSTEM_PROMPT,
                },
                cwd=str(AGENT_RESOURCES_DIR),
                setting_sources=["project"],
                mcp_servers={"video-tools": video_tools_server},
                allowed_tools=[
                    # Transcription tools
                    "mcp__video-tools__transcribe_video",
                    "mcp__video-tools__write_file",
                    "mcp__video-tools__save_transcript",
                    "mcp__video-tools__get_transcript",
                    "mcp__video-tools__list_transcripts",
                    # Knowledge Graph tools
                    "mcp__video-tools__extract_to_kg",
                    "mcp__video-tools__list_kg_projects",
                    "mcp__video-tools__create_kg_project",
                    "mcp__video-tools__bootstrap_kg_project",
                    "mcp__video-tools__get_kg_stats",
                    # SDK resources
                    "Skill",
                ],
                can_use_tool=permission_handler,
                output_format={
                    "type": "json_schema",
                    "schema": get_output_schema(),
                },
                max_turns=50,
            )

            async with ClaudeSDKClient(options) as client:
                # Handle Initial Greeting
                try:
                    initial_prompt = (
                        'Start by greeting me following your <phase name="gathering_input"> workflow. '
                        "Your greeting MUST include: "
                        "(1) mention you use gpt-4o-transcribe model, "
                        "(2) list accepted formats (local files AND YouTube URLs), "
                        "(3) ask about language with ISO code examples, "
                        "(4) ask about quality preferences (domain terms, filler words, formatting). "
                        "Be thorough - include ALL four points."
                    )
                    await client.query(initial_prompt)

                    greeting_text = []
                    error_message: str | None = None

                    async for message in client.receive_response():
                        # Handle ResultMessage with subtype-aware error handling
                        if isinstance(message, ResultMessage):
                            error_message = self._handle_result_message(message)

                        if isinstance(message, AssistantMessage):
                            # Extract token usage for granular tracking
                            usage_data = self._extract_usage_from_message(message)
                            if usage_data:
                                self.session_cost.add_usage(usage_data)

                            greeting_text.extend(self._extract_message_text(message))

                    # Use error message if there was an error, otherwise use greeting
                    final_text = error_message or "\n".join(greeting_text)

                    # Return cumulative session usage (aggregated across all messages)
                    await self.greeting_queue.put(
                        MessageResponse(
                            text=final_text,
                            usage=self.get_cumulative_usage(),
                        )
                    )
                except Exception as e:
                    logger.error(f"Session {self.session_id}: Greeting failed: {e}")
                    await self.greeting_queue.put(
                        MessageResponse(
                            text="Hello! I encountered an issue during startup but I'm ready to help.",
                            usage=MessageUsage(),
                        )
                    )

                logger.info(f"Session {self.session_id}: Ready for input")

                # Main Event Loop with timeout on queue wait
                while self._running_event.is_set():
                    try:
                        user_message = await asyncio.wait_for(
                            self.input_queue.get(), timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        continue  # Re-check is_running

                    if user_message is None:
                        break

                    try:
                        await client.query(user_message)

                        full_text = []
                        response_error: str | None = None

                        async for message in client.receive_response():
                            # Emit activity event for real-time UX feedback
                            activity_event = get_activity_text(message)
                            if activity_event:
                                self._emit_activity(activity_event)

                            # Handle ResultMessage with subtype-aware error handling
                            if isinstance(message, ResultMessage):
                                response_error = self._handle_result_message(message)

                            if isinstance(message, AssistantMessage):
                                # Extract token usage for granular tracking
                                usage_data = self._extract_usage_from_message(message)
                                if usage_data:
                                    self.session_cost.add_usage(usage_data)

                                full_text.extend(self._extract_message_text(message))

                        # Emit completion event
                        self._emit_activity(
                            ActivityEvent(
                                activity_type=ActivityType.COMPLETED,
                                message="✨ Response ready",
                            )
                        )

                        # Use error message if there was an error, otherwise use response
                        final_text = response_error or "\n".join(full_text)

                        # Ensure we always have some response text
                        if not final_text.strip():
                            logger.warning(
                                f"Session {self.session_id}: Empty response text, using fallback"
                            )
                            final_text = (
                                "I've processed your request. "
                                "Please check the Jobs panel for any background tasks."
                            )

                        # Return cumulative session usage (aggregated across all messages)
                        await self.response_queue.put(
                            MessageResponse(
                                text=final_text,
                                usage=self.get_cumulative_usage(),
                            )
                        )

                    except Exception as e:
                        logger.error(
                            f"Session {self.session_id}: Error processing message: {e}"
                        )
                        await self.response_queue.put(e)

        except asyncio.CancelledError:
            logger.info(f"Session {self.session_id}: Worker cancelled")
            raise
        except Exception as e:
            logger.error(
                f"Session {self.session_id}: Worker crashed: {e}", exc_info=True
            )
        finally:
            # Save cost data before shutdown
            try:
                cost_data = self.session_cost.to_dict()
                storage.save_session_cost(self.session_id, cost_data)
                storage.update_global_cost(cost_data)
                logger.info(
                    f"Session {self.session_id}: Saved cost data - "
                    f"${cost_data['total_cost_usd']:.4f}"
                )
            except Exception as e:
                logger.error(
                    f"Session {self.session_id}: Failed to save cost data: {e}"
                )

            self._running_event.clear()
            logger.info(f"Session {self.session_id}: Worker shutdown")
