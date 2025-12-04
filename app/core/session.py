"""
Session Management (Actor Pattern) for the Video Agent Web App.

This module implements the SessionActor pattern to serialize access to the
Claude Agent SDK for each user session, preventing race conditions and
managing session lifecycle.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass

from fastapi import HTTPException

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)

from app.agent import video_tools_server
from app.agent.prompts import SYSTEM_PROMPT
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

# Configuration constants
RESPONSE_TIMEOUT_SECONDS: float = 300.0  # 5 minutes for transcription
GREETING_TIMEOUT_SECONDS: float = 30.0  # 30 seconds for initial greeting
SESSION_TTL_SECONDS: float = 3600.0  # 1 hour session lifetime
CLEANUP_INTERVAL_SECONDS: float = 300.0  # 5 minutes between cleanup runs
QUEUE_MAX_SIZE: int = 10  # Maximum pending messages per queue
GRACEFUL_SHUTDOWN_TIMEOUT: float = 5.0  # Seconds to wait before force-cancel


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
# Session Management (Actor Pattern)
# --------------------------------------------------------------------------


class SessionActor:
    """
    A dedicated actor that runs the ClaudeSDKClient in its own asyncio task.
    This prevents 'cancel scope' errors by ensuring the client is always
    accessed from the same task context.
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
                return [parsed.message]
            except Exception:
                pass  # Fall through to text extraction

        # Fallback to TextBlock content
        return [block.text for block in message.content if isinstance(block, TextBlock)]

    async def _worker_loop(self) -> None:
        """The main loop that holds the ClaudeSDKClient context."""
        logger.info(f"Session {self.session_id}: Worker started")

        try:
            # Create permission handler
            permission_handler = create_permission_handler(
                get_default_permission_config()
            )

            options = ClaudeAgentOptions(
                model="claude-opus-4-5",
                system_prompt=SYSTEM_PROMPT,
                mcp_servers={"video-tools": video_tools_server},
                allowed_tools=[
                    "mcp__video-tools__transcribe_video",
                    "mcp__video-tools__write_file",
                    "mcp__video-tools__save_transcript",
                    "mcp__video-tools__get_transcript",
                    "mcp__video-tools__list_transcripts",
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
                        "Start the conversation by greeting me and asking for a video "
                        "to transcribe. Follow your workflow."
                    )
                    await client.query(initial_prompt)

                    greeting_text = []
                    async for message in client.receive_response():
                        # Capture cost from ResultMessage (SDK's authoritative source)
                        if isinstance(message, ResultMessage):
                            if message.total_cost_usd is not None:
                                self.session_cost.set_reported_cost(
                                    message.total_cost_usd
                                )

                        if isinstance(message, AssistantMessage):
                            greeting_text.extend(self._extract_message_text(message))

                    # Return cumulative session usage (aggregated across all messages)
                    await self.greeting_queue.put(
                        MessageResponse(
                            text="\n".join(greeting_text),
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
                        async for message in client.receive_response():
                            # Capture cost from ResultMessage (SDK's authoritative source)
                            if isinstance(message, ResultMessage):
                                if message.total_cost_usd is not None:
                                    self.session_cost.set_reported_cost(
                                        message.total_cost_usd
                                    )

                            if isinstance(message, AssistantMessage):
                                full_text.extend(self._extract_message_text(message))

                        # Return cumulative session usage (aggregated across all messages)
                        await self.response_queue.put(
                            MessageResponse(
                                text="\n".join(full_text),
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


# In-memory storage for active sessions
active_sessions: dict[str, SessionActor] = {}
sessions_lock = asyncio.Lock()  # Protects active_sessions access


async def cleanup_expired_sessions() -> None:
    """Periodically remove expired sessions."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

        # Collect and remove expired sessions while holding the lock
        # to prevent race conditions with session creation
        actors_to_stop: list[SessionActor] = []
        async with sessions_lock:
            expired_ids = [
                sid
                for sid, actor in active_sessions.items()
                if actor.is_expired() or not actor.is_running
            ]
            for sid in expired_ids:
                logger.info(f"Cleaning up expired session: {sid}")
                actors_to_stop.append(active_sessions.pop(sid))

        # Stop actors outside the lock to avoid blocking other operations
        for actor in actors_to_stop:
            await actor.stop()


async def get_or_create_session(session_id: str) -> SessionActor:
    """
    Retrieves an existing session or spawns a new actor.

    Uses double-checked locking pattern to minimize lock contention:
    1. First check with lock to see if session exists
    2. If not, create and start actor outside lock (slow operation)
    3. Re-acquire lock to add to dict, handling race if another created it
    """
    # First check: see if session already exists
    async with sessions_lock:
        if session_id in active_sessions:
            actor = active_sessions[session_id]
            if actor.is_running:
                return actor
            else:
                del active_sessions[session_id]
                logger.warning(f"Cleaned up dead session: {session_id}")

    # Create and start new actor outside the lock (slow operation)
    logger.info(f"Initializing new session actor: {session_id}")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(
            status_code=503, detail="Service unavailable: API not configured"
        )

    new_actor = SessionActor(session_id)
    await new_actor.start()

    # Second check: add to dict, handling race condition
    async with sessions_lock:
        if session_id in active_sessions:
            # Another request created the session while we were starting
            # Stop our actor and use theirs
            existing = active_sessions[session_id]
            if existing.is_running:
                await new_actor.stop()
                logger.info(
                    f"Session {session_id[:8]} created by another request, reusing"
                )
                return existing
            else:
                # Existing one died, use ours
                del active_sessions[session_id]

        active_sessions[session_id] = new_actor
        return new_actor
