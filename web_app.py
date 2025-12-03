import asyncio
import logging
import os
import re
import time
import uuid
from pathlib import Path
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# UUID v4 validation pattern
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def validate_uuid(value: str, field_name: str = "ID") -> None:
    """
    Validate that a string is a valid UUID v4 format.

    Args:
        value: The string to validate
        field_name: Name of the field for error messages

    Raises:
        HTTPException: If the value is not a valid UUID v4
    """
    if not UUID_PATTERN.match(value):
        raise HTTPException(
            status_code=400, detail=f"Invalid {field_name} format (must be UUID v4)"
        )

from claude_agent_sdk import (  # noqa: E402
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
)
from agent_video import video_tools_server  # noqa: E402
from agent_video.prompts import SYSTEM_PROMPT  # noqa: E402
from storage import storage  # noqa: E402
from web_app_models import (  # noqa: E402
    StatusResponse,
    AgentStatus,
    HistoryListResponse,
    SessionDetail,
    SessionSummary,
    TranscriptListResponse,
    TranscriptMetadata,
    UploadResponse,
)

# Configuration constants
RESPONSE_TIMEOUT_SECONDS: float = 300.0  # 5 minutes for transcription
GREETING_TIMEOUT_SECONDS: float = 30.0  # 30 seconds for initial greeting
SESSION_TTL_SECONDS: float = 3600.0  # 1 hour session lifetime
CLEANUP_INTERVAL_SECONDS: float = 300.0  # 5 minutes between cleanup runs
QUEUE_MAX_SIZE: int = 10  # Maximum pending messages per queue
GRACEFUL_SHUTDOWN_TIMEOUT: float = 2.0  # Seconds to wait before force-cancel

# Upload configuration
UPLOAD_DIR = Path("uploads")
ALLOWED_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

# --------------------------------------------------------------------------
# Exception Handling
# --------------------------------------------------------------------------


async def validation_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Return 422 with structured validation error details."""
    if not isinstance(exc, RequestValidationError):
        raise exc
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({"field": field, "message": error["msg"]})

    return JSONResponse(
        status_code=422, content={"detail": "Validation error", "errors": errors}
    )


def handle_endpoint_error(e: Exception, context: str) -> HTTPException:
    """
    Convert exceptions to safe HTTP responses.

    Logs full error details server-side but returns
    generic messages to clients to prevent information leakage.

    Args:
        e: The exception that occurred
        context: Description of the endpoint context for logging

    Returns:
        HTTPException with appropriate status code and safe message
    """
    if isinstance(e, HTTPException):
        return e

    if isinstance(e, TimeoutError):
        logger.warning(f"{context}: Timeout - {e}")
        return HTTPException(
            status_code=504, detail="Request timed out. Please try again."
        )

    if isinstance(e, RuntimeError):
        error_msg = str(e).lower()
        if "closed" in error_msg:
            logger.warning(f"{context}: Session closed - {e}")
            return HTTPException(status_code=410, detail="Session is closed")

    # Log full error details but don't expose to client
    logger.error(f"{context}: {type(e).__name__}: {e}", exc_info=True)
    return HTTPException(
        status_code=500, detail="An internal error occurred. Please try again."
    )


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
        self.response_queue: asyncio.Queue[str | Exception] = asyncio.Queue(
            maxsize=QUEUE_MAX_SIZE
        )
        self.greeting_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        self.active_task: asyncio.Task[None] | None = None
        self._running_event = asyncio.Event()
        self.last_activity: float = time.time()
        self._is_processing: bool = False

    @property
    def is_running(self) -> bool:
        """Thread-safe check if session is running."""
        return self._running_event.is_set()

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

    async def get_greeting(self) -> str:
        """Waits for and returns the initial greeting message."""
        if not self._running_event.is_set():
            raise RuntimeError("Session is closed")

        self.touch()

        try:
            greeting = await asyncio.wait_for(
                self.greeting_queue.get(), timeout=GREETING_TIMEOUT_SECONDS
            )
            return greeting
        except asyncio.TimeoutError:
            logger.warning(f"Session {self.session_id}: Greeting timed out")
            return "Hello! I'm ready to help you transcribe videos. (Note: Initialization was slow)"

    async def process_message(self, message: str) -> str:
        """Sends a message to the agent and awaits the full text response."""
        if not self._running_event.is_set() or not self.active_task:
            raise RuntimeError("Session is closed")

        self.touch()
        self._is_processing = True

        try:
            await self.input_queue.put(message)

            get_response = asyncio.create_task(self.response_queue.get())

            done, pending = await asyncio.wait(
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

    async def _worker_loop(self) -> None:
        """The main loop that holds the ClaudeSDKClient context."""
        logger.info(f"Session {self.session_id}: Worker started")

        try:
            options = ClaudeAgentOptions(
                system_prompt=SYSTEM_PROMPT,
                mcp_servers={"video-tools": video_tools_server},
                allowed_tools=[
                    "mcp__video-tools__transcribe_video",
                    "mcp__video-tools__write_file",
                ],
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
                        if isinstance(message, AssistantMessage):
                            for block in message.content:
                                if isinstance(block, TextBlock):
                                    greeting_text.append(block.text)

                    await self.greeting_queue.put("\n".join(greeting_text))
                except Exception as e:
                    logger.error(f"Session {self.session_id}: Greeting failed: {e}")
                    await self.greeting_queue.put(
                        "Hello! I encountered an issue during startup but I'm ready to help."
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
                            if isinstance(message, AssistantMessage):
                                for block in message.content:
                                    if isinstance(block, TextBlock):
                                        full_text.append(block.text)

                        await self.response_queue.put("\n".join(full_text))

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


# Background task reference for cleanup
_cleanup_task: asyncio.Task[None] | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle with startup and shutdown events."""
    global _cleanup_task
    # Startup: begin background cleanup task
    _cleanup_task = asyncio.create_task(cleanup_expired_sessions())
    logger.info("Started session cleanup background task")

    yield

    # Shutdown: cancel cleanup and stop all sessions
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass

    # Gracefully stop all active sessions
    async with sessions_lock:
        actors = list(active_sessions.values())
        active_sessions.clear()

    for actor in actors:
        await actor.stop()
    logger.info("Shutdown complete: all sessions closed")


# Initialize FastAPI app with lifespan context manager
app = FastAPI(title="Agent Video to Data", lifespan=lifespan)

# Register exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")


class ChatRequest(BaseModel):
    """Request model for chat messages."""

    session_id: str = Field(
        ..., min_length=36, max_length=36, description="UUID v4 session identifier"
    )
    message: str = Field(
        ..., min_length=1, max_length=50000, description="User message content"
    )

    @field_validator("session_id")
    @classmethod
    def validate_session_id_format(cls, v: str) -> str:
        """Validate session_id is a valid UUID v4."""
        if not UUID_PATTERN.match(v):
            raise ValueError("session_id must be a valid UUID v4 format")
        return v

    @field_validator("message")
    @classmethod
    def validate_message_not_empty(cls, v: str) -> str:
        """Validate message is not just whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("message cannot be empty or whitespace only")
        return stripped


class ChatResponse(BaseModel):
    """Response model for chat messages."""

    response: str
    session_id: str


class InitRequest(BaseModel):
    """Request model for session initialization."""

    session_id: str = Field(
        ..., min_length=36, max_length=36, description="UUID v4 session identifier"
    )

    @field_validator("session_id")
    @classmethod
    def validate_session_id_format(cls, v: str) -> str:
        """Validate session_id is a valid UUID v4."""
        if not UUID_PATTERN.match(v):
            raise ValueError("session_id must be a valid UUID v4 format")
        return v


async def get_or_create_session(session_id: str) -> SessionActor:
    """Retrieves an existing session or spawns a new actor."""
    async with sessions_lock:
        if session_id in active_sessions:
            actor = active_sessions[session_id]
            if actor.is_running:
                return actor
            else:
                del active_sessions[session_id]
                logger.warning(f"Cleaned up dead session: {session_id}")

        logger.info(f"Initializing new session actor: {session_id}")

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(
                status_code=503, detail="Service unavailable: API not configured"
            )

        actor = SessionActor(session_id)
        await actor.start()
        active_sessions[session_id] = actor
        return actor


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/chat/init", response_model=ChatResponse)
async def chat_init(request: InitRequest):
    """Initialize a chat session and return the greeting message."""
    try:
        actor = await get_or_create_session(request.session_id)
        greeting = await actor.get_greeting()

        # Save greeting to storage
        storage.save_message(request.session_id, "agent", greeting)

        return ChatResponse(response=greeting, session_id=request.session_id)
    except HTTPException:
        raise
    except Exception as e:
        raise handle_endpoint_error(e, f"chat_init session={request.session_id[:8]}...")


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Process a chat message and return the response."""
    try:
        actor = await get_or_create_session(request.session_id)

        # Save user message to storage
        storage.save_message(request.session_id, "user", request.message)

        # Send message to actor and await response
        response_text = await actor.process_message(request.message)

        # Save agent response to storage
        storage.save_message(request.session_id, "agent", response_text)

        return ChatResponse(response=response_text, session_id=request.session_id)
    except HTTPException:
        raise
    except Exception as e:
        raise handle_endpoint_error(e, f"chat session={request.session_id[:8]}...")


@app.delete("/chat/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session."""
    # Validate session ID format
    if not UUID_PATTERN.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    async with sessions_lock:
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        actor = active_sessions.pop(session_id)

    await actor.stop()
    logger.info(f"Session deleted: {session_id[:8]}...")

    return {"status": "success", "message": f"Session {session_id} closed"}


@app.get("/status/{session_id}", response_model=StatusResponse)
async def get_status(session_id: str):
    """Get current status of a session's agent."""
    validate_uuid(session_id, "session ID")

    async with sessions_lock:
        if session_id not in active_sessions:
            return StatusResponse(
                status=AgentStatus.INITIALIZING,
                session_id=session_id,
                message="Session not yet initialized",
            )

        actor = active_sessions[session_id]

    if not actor.is_running:
        return StatusResponse(
            status=AgentStatus.ERROR,
            session_id=session_id,
            message="Session worker stopped",
        )

    if actor._is_processing:
        return StatusResponse(status=AgentStatus.PROCESSING, session_id=session_id)

    return StatusResponse(status=AgentStatus.READY, session_id=session_id)


@app.get("/history", response_model=HistoryListResponse)
async def list_history(limit: int = 50):
    """List all chat sessions with previews."""
    sessions = storage.list_sessions(limit=limit)
    return HistoryListResponse(
        sessions=[SessionSummary(**s) for s in sessions], total=len(sessions)
    )


@app.get("/history/{session_id}", response_model=SessionDetail)
async def get_history(session_id: str):
    """Get full chat history for a session."""
    validate_uuid(session_id, "session ID")

    session = storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session history not found")
    return SessionDetail(**session)


@app.delete("/history/{session_id}")
async def delete_history(session_id: str):
    """Delete a session's history."""
    validate_uuid(session_id, "session ID")

    success = storage.delete_session(session_id)
    return {"success": success}


@app.get("/transcripts", response_model=TranscriptListResponse)
async def list_transcripts():
    """List all saved transcript files."""
    transcripts = storage.list_transcripts()
    return TranscriptListResponse(
        transcripts=[TranscriptMetadata(**t) for t in transcripts],
        total=len(transcripts),
    )


@app.get("/transcripts/{transcript_id}/download")
async def download_transcript(transcript_id: str):
    """Download a transcript file."""
    metadata = storage.get_transcript(transcript_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Transcript not found")

    file_path = Path(metadata["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(file_path), filename=metadata["filename"], media_type="text/plain"
    )


@app.delete("/transcripts/{transcript_id}")
async def delete_transcript(transcript_id: str):
    """Delete a transcript file."""
    success = storage.delete_transcript(transcript_id)
    return {"success": success}


@app.post("/upload", response_model=UploadResponse)
async def upload_video(file: UploadFile = File(...), session_id: str = Form(...)):
    """Upload a video file for transcription."""
    # Validate session_id is a valid UUID v4
    if not UUID_PATTERN.match(session_id):
        return UploadResponse(success=False, error="Invalid session ID format")

    # Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return UploadResponse(
            success=False,
            error=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Sanitize filename - extract only the base name to prevent path traversal
    original_filename = Path(file.filename or "upload").name
    if not original_filename or original_filename.startswith("."):
        original_filename = "upload" + ext

    # Create session upload directory
    session_upload_dir = UPLOAD_DIR / session_id
    session_upload_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename with sanitized original name
    file_id = str(uuid.uuid4())[:8]
    safe_filename = f"{file_id}_{original_filename}"
    file_path = session_upload_dir / safe_filename

    # Stream file to disk with size validation
    try:
        total_size = 0
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(8192):
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    buffer.close()
                    file_path.unlink(missing_ok=True)
                    return UploadResponse(
                        success=False,
                        error=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
                    )
                buffer.write(chunk)

        # Return relative path to avoid exposing server filesystem structure
        # The agent can access files from the project root
        try:
            relative_path = file_path.relative_to(Path.cwd())
            path_to_return = str(relative_path)
        except ValueError:
            # If file_path is not under cwd (e.g., in tests), return path from UPLOAD_DIR
            path_to_return = str(UPLOAD_DIR / session_id / safe_filename)

        return UploadResponse(
            success=True, file_id=file_id, file_path=path_to_return
        )
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        # Clean up partial file on error
        file_path.unlink(missing_ok=True)
        return UploadResponse(success=False, error="Upload failed")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web_app:app", host="127.0.0.1", port=8000, reload=True)
