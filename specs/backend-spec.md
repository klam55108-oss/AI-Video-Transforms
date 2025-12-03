# Backend Implementation Spec

## Overview

This spec covers all backend changes for the VideoAgent web application, including concurrency fixes, async improvements, new API endpoints, and storage infrastructure.

---

## Target Files

| File | Action | Description |
|------|--------|-------------|
| `web_app.py` | MODIFY | Concurrency fixes, logging, new endpoints |
| `agent_video/transcribe_tool.py` | MODIFY | Async wrapper for blocking operations |
| `agent_video/file_tool.py` | MODIFY | Async wrapper for file I/O |
| `storage.py` | CREATE | File-based storage manager |
| `web_app_models.py` | CREATE | Pydantic models for new features |
| `.gitignore` | MODIFY | Add data/ and uploads/ directories |

---

## Part 1: Foundation & Logging

### 1.1 Add Logging Infrastructure

**File:** `web_app.py`

Add after imports:
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
```

Replace print() statements at these lines with logger calls:
- Line 127: `logger.info(f"Session {self.session_id}: Worker started")`
- Line 158: `logger.info(f"Session {self.session_id}: Ready for input")`
- Line 184: `logger.error(f"Session {self.session_id}: Error processing message: {e}")`
- Line 188: `logger.error(f"Session {self.session_id}: Worker crashed: {e}")`
- Line 190: `logger.info(f"Session {self.session_id}: Worker shutdown")`
- Line 218: `logger.info(f"Initializing new session actor: {session_id}")`

### 1.2 Add Configuration Constants

**File:** `web_app.py` (after imports, before class definitions)

```python
import time

# Configuration constants
RESPONSE_TIMEOUT_SECONDS: float = 300.0    # 5 minutes for transcription
GREETING_TIMEOUT_SECONDS: float = 30.0     # 30 seconds for initial greeting
SESSION_TTL_SECONDS: float = 3600.0        # 1 hour session lifetime
CLEANUP_INTERVAL_SECONDS: float = 300.0    # 5 minutes between cleanup runs
QUEUE_MAX_SIZE: int = 10                   # Maximum pending messages per queue
GRACEFUL_SHUTDOWN_TIMEOUT: float = 2.0     # Seconds to wait before force-cancel
```

---

## Part 2: Concurrency & Stability Fixes

### 2.1 Add Session Lock for Thread Safety

**File:** `web_app.py:194` (after active_sessions definition)

```python
active_sessions: Dict[str, SessionActor] = {}
sessions_lock = asyncio.Lock()  # Protects active_sessions access
```

### 2.2 Replace is_running Boolean with asyncio.Event

**File:** `web_app.py:44-50` (SessionActor.__init__)

```python
def __init__(self, session_id: str):
    self.session_id = session_id
    self.input_queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
    self.response_queue: asyncio.Queue[str | Exception] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
    self.greeting_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
    self.active_task: Optional[asyncio.Task[None]] = None
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
```

### 2.3 Update start() Method

**File:** `web_app.py:52-55`

```python
async def start(self) -> None:
    """Starts the background worker task."""
    self._running_event.set()
    self.active_task = asyncio.create_task(self._worker_loop())
```

### 2.4 Update stop() Method with Proper Cancellation

**File:** `web_app.py:57-71`

```python
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
            await asyncio.wait_for(self.active_task, timeout=GRACEFUL_SHUTDOWN_TIMEOUT)
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
```

### 2.5 Update get_greeting() with Proper Timeout

**File:** `web_app.py:73-90`

```python
async def get_greeting(self) -> str:
    """Waits for and returns the initial greeting message."""
    if not self._running_event.is_set():
        raise RuntimeError("Session is closed")

    self.touch()

    try:
        greeting = await asyncio.wait_for(
            self.greeting_queue.get(),
            timeout=GREETING_TIMEOUT_SECONDS
        )
        return greeting
    except asyncio.TimeoutError:
        logger.warning(f"Session {self.session_id}: Greeting timed out")
        return "Hello! I'm ready to help you transcribe videos. (Note: Initialization was slow)"
```

### 2.6 Update process_message() with Timeout and Processing Flag

**File:** `web_app.py:92-123`

```python
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
            return_when=asyncio.FIRST_COMPLETED
        )

        if not done:
            # Timeout occurred
            get_response.cancel()
            try:
                await get_response
            except asyncio.CancelledError:
                pass
            raise TimeoutError(f"Response timed out after {RESPONSE_TIMEOUT_SECONDS} seconds")

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
```

### 2.7 Update _worker_loop() with Better Error Handling

**File:** `web_app.py:125-191`

```python
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
                await self.greeting_queue.put(f"Hello! I encountered an issue during startup but I'm ready to help.")

            logger.info(f"Session {self.session_id}: Ready for input")

            # Main Event Loop with timeout on queue wait
            while self._running_event.is_set():
                try:
                    user_message = await asyncio.wait_for(
                        self.input_queue.get(),
                        timeout=1.0
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
                    logger.error(f"Session {self.session_id}: Error processing message: {e}")
                    await self.response_queue.put(e)

    except asyncio.CancelledError:
        logger.info(f"Session {self.session_id}: Worker cancelled")
        raise
    except Exception as e:
        logger.error(f"Session {self.session_id}: Worker crashed: {e}", exc_info=True)
    finally:
        self._running_event.clear()
        logger.info(f"Session {self.session_id}: Worker shutdown")
```

### 2.8 Add Session Cleanup Background Task

**File:** `web_app.py` (add after active_sessions definition)

```python
async def cleanup_expired_sessions() -> None:
    """Periodically remove expired sessions."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

        async with sessions_lock:
            expired_ids = [
                sid for sid, actor in active_sessions.items()
                if actor.is_expired() or not actor.is_running
            ]

        for sid in expired_ids:
            logger.info(f"Cleaning up expired session: {sid}")
            async with sessions_lock:
                if sid in active_sessions:
                    actor = active_sessions.pop(sid)
            if actor:
                await actor.stop()

@app.on_event("startup")
async def startup_event():
    """Start background cleanup task."""
    asyncio.create_task(cleanup_expired_sessions())
```

### 2.9 Update get_or_create_session() with Lock

**File:** `web_app.py:208-227`

```python
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
                status_code=503,
                detail="Service unavailable: API not configured"
            )

        actor = SessionActor(session_id)
        await actor.start()
        active_sessions[session_id] = actor
        return actor
```

---

## Part 3: Async Improvements for Tools

### 3.1 Wrap Transcription in Thread Pool

**File:** `agent_video/transcribe_tool.py`

Add import at top:
```python
import asyncio
```

Update lines 311-315:
```python
# Run the blocking transcription in a thread pool
result = await asyncio.to_thread(
    _perform_transcription,
    video_source=video_source,
    output_file=output_file,
    language=language,
)
```

### 3.2 Wrap File Writing in Thread Pool

**File:** `agent_video/file_tool.py`

Add import at top:
```python
import asyncio
```

Add helper function before write_file():
```python
def _write_file_sync(path: Path, content: str) -> tuple[int, int]:
    """
    Synchronous file write operation.

    Returns:
        Tuple of (file_size, line_count)
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    file_size = os.path.getsize(path)
    line_count = content.count("\n") + (
        1 if content and not content.endswith("\n") else 0
    )
    return file_size, line_count
```

Update the write section (lines 196-214):
```python
# Write the file asynchronously
try:
    file_size, line_count = await asyncio.to_thread(
        _write_file_sync, path, content
    )

    return {
        "content": [
            {
                "type": "text",
                "text": f"Successfully saved file: {path}\n"
                f"Size: {file_size:,} bytes\n"
                f"Lines: {line_count:,}",
            }
        ]
    }

except PermissionError:
    # ... existing error handling ...
```

---

## Part 4: Storage Infrastructure

### 4.1 Create Storage Manager

**File:** `storage.py` (NEW)

```python
"""
File-based storage manager for sessions and transcripts.

This module provides persistent storage for chat history and transcript metadata
using JSON files, suitable for local development use.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StorageManager:
    """File-based storage for sessions and transcripts."""

    def __init__(self, base_dir: Path | str = "data") -> None:
        self.base_dir = Path(base_dir)
        self.sessions_dir = self.base_dir / "sessions"
        self.transcripts_dir = self.base_dir / "transcripts"
        self.metadata_file = self.base_dir / "metadata.json"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create storage directories if they don't exist."""
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)

    def _load_metadata(self) -> dict[str, Any]:
        """Load global metadata from file."""
        if self.metadata_file.exists():
            return json.loads(self.metadata_file.read_text())
        return {"transcripts": {}}

    def _save_metadata(self, data: dict[str, Any]) -> None:
        """Save global metadata to file."""
        self.metadata_file.write_text(json.dumps(data, indent=2, default=str))

    # --- Session Methods ---

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> dict[str, Any]:
        """
        Save a chat message to session history.

        Args:
            session_id: UUID of the session
            role: "user" or "agent"
            content: Message content

        Returns:
            The saved message object
        """
        session_file = self.sessions_dir / f"{session_id}.json"

        if session_file.exists():
            session_data = json.loads(session_file.read_text())
        else:
            session_data = {
                "session_id": session_id,
                "title": "",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "messages": []
            }

        message = {
            "id": str(uuid.uuid4()),
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        session_data["messages"].append(message)
        session_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Set title from first user message
        if not session_data["title"] and role == "user":
            session_data["title"] = content[:50] + ("..." if len(content) > 50 else "")

        session_file.write_text(json.dumps(session_data, indent=2))
        return message

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get full session data by ID."""
        session_file = self.sessions_dir / f"{session_id}.json"
        if session_file.exists():
            return json.loads(session_file.read_text())
        return None

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """List all sessions with summary info."""
        sessions = []
        for f in self.sessions_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                sessions.append({
                    "session_id": data["session_id"],
                    "title": data.get("title", "Untitled"),
                    "created_at": data["created_at"],
                    "updated_at": data["updated_at"],
                    "message_count": len(data.get("messages", []))
                })
            except (json.JSONDecodeError, KeyError):
                continue

        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        return sessions[:limit]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session's history."""
        session_file = self.sessions_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            return True
        return False

    # --- Transcript Methods ---

    def register_transcript(
        self,
        file_path: str,
        original_source: str,
        source_type: str,
        session_id: str | None = None
    ) -> dict[str, Any]:
        """
        Register a transcript file in the metadata.

        Args:
            file_path: Path to the transcript file
            original_source: YouTube URL or uploaded filename
            source_type: "youtube", "upload", or "local"
            session_id: Optional link to originating session

        Returns:
            The transcript metadata entry
        """
        metadata = self._load_metadata()

        transcript_id = str(uuid.uuid4())[:8]
        path = Path(file_path)

        entry = {
            "id": transcript_id,
            "filename": path.name,
            "file_path": str(path.resolve()),
            "original_source": original_source,
            "source_type": source_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "file_size": path.stat().st_size if path.exists() else 0,
            "session_id": session_id
        }

        metadata["transcripts"][transcript_id] = entry
        self._save_metadata(metadata)
        return entry

    def list_transcripts(self) -> list[dict[str, Any]]:
        """List all registered transcripts."""
        metadata = self._load_metadata()
        transcripts = list(metadata.get("transcripts", {}).values())
        transcripts.sort(key=lambda x: x["created_at"], reverse=True)
        return transcripts

    def get_transcript(self, transcript_id: str) -> dict[str, Any] | None:
        """Get transcript metadata by ID."""
        metadata = self._load_metadata()
        return metadata.get("transcripts", {}).get(transcript_id)

    def delete_transcript(self, transcript_id: str) -> bool:
        """Delete a transcript and optionally its file."""
        metadata = self._load_metadata()
        if transcript_id in metadata.get("transcripts", {}):
            entry = metadata["transcripts"].pop(transcript_id)
            self._save_metadata(metadata)

            # Optionally delete the file
            file_path = Path(entry.get("file_path", ""))
            if file_path.exists():
                file_path.unlink()
            return True
        return False


# Global storage instance
storage = StorageManager()
```

### 4.2 Create Pydantic Models for Features

**File:** `web_app_models.py` (NEW)

```python
"""
Pydantic models for web app API endpoints.

These models define the request/response schemas for the VideoAgent API,
including chat, history, transcripts, and upload features.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class AgentStatus(str, Enum):
    """Possible states for the agent."""
    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    ERROR = "error"


class StatusResponse(BaseModel):
    """Response for /status endpoint."""
    status: AgentStatus
    session_id: str | None = None
    message: str | None = None


class ChatMessage(BaseModel):
    """A single chat message."""
    id: str
    role: str  # "user" | "agent"
    content: str
    timestamp: datetime


class SessionSummary(BaseModel):
    """Summary info for a chat session (for list views)."""
    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class SessionDetail(BaseModel):
    """Full session data including all messages."""
    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessage]


class HistoryListResponse(BaseModel):
    """Response for /history endpoint."""
    sessions: list[SessionSummary]
    total: int


class TranscriptMetadata(BaseModel):
    """Metadata for a saved transcript."""
    id: str
    filename: str
    original_source: str
    source_type: str  # "youtube" | "upload" | "local"
    created_at: datetime
    file_size: int
    session_id: str | None = None


class TranscriptListResponse(BaseModel):
    """Response for /transcripts endpoint."""
    transcripts: list[TranscriptMetadata]
    total: int


class UploadResponse(BaseModel):
    """Response for /upload endpoint."""
    success: bool
    file_id: str | None = None
    file_path: str | None = None
    error: str | None = None
```

---

## Part 5: New API Endpoints

### 5.1 Status Endpoint

**File:** `web_app.py`

```python
from web_app_models import StatusResponse, AgentStatus

@app.get("/status/{session_id}", response_model=StatusResponse)
async def get_status(session_id: str):
    """Get current status of a session's agent."""
    async with sessions_lock:
        if session_id not in active_sessions:
            return StatusResponse(
                status=AgentStatus.INITIALIZING,
                session_id=session_id,
                message="Session not yet initialized"
            )

        actor = active_sessions[session_id]

    if not actor.is_running:
        return StatusResponse(
            status=AgentStatus.ERROR,
            session_id=session_id,
            message="Session worker stopped"
        )

    if actor._is_processing:
        return StatusResponse(
            status=AgentStatus.PROCESSING,
            session_id=session_id
        )

    return StatusResponse(
        status=AgentStatus.READY,
        session_id=session_id
    )
```

### 5.2 History Endpoints

**File:** `web_app.py`

```python
from web_app_models import HistoryListResponse, SessionDetail, SessionSummary
from storage import storage

@app.get("/history", response_model=HistoryListResponse)
async def list_history(limit: int = 50):
    """List all chat sessions with previews."""
    sessions = storage.list_sessions(limit=limit)
    return HistoryListResponse(
        sessions=[SessionSummary(**s) for s in sessions],
        total=len(sessions)
    )

@app.get("/history/{session_id}", response_model=SessionDetail)
async def get_history(session_id: str):
    """Get full chat history for a session."""
    session = storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session history not found")
    return SessionDetail(**session)

@app.delete("/history/{session_id}")
async def delete_history(session_id: str):
    """Delete a session's history."""
    success = storage.delete_session(session_id)
    return {"success": success}
```

### 5.3 Transcripts Endpoints

**File:** `web_app.py`

```python
from fastapi.responses import FileResponse
from web_app_models import TranscriptListResponse, TranscriptMetadata

@app.get("/transcripts", response_model=TranscriptListResponse)
async def list_transcripts():
    """List all saved transcript files."""
    transcripts = storage.list_transcripts()
    return TranscriptListResponse(
        transcripts=[TranscriptMetadata(**t) for t in transcripts],
        total=len(transcripts)
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
        path=str(file_path),
        filename=metadata["filename"],
        media_type="text/plain"
    )

@app.delete("/transcripts/{transcript_id}")
async def delete_transcript(transcript_id: str):
    """Delete a transcript file."""
    success = storage.delete_transcript(transcript_id)
    return {"success": success}
```

### 5.4 File Upload Endpoint

**File:** `web_app.py`

```python
from fastapi import UploadFile, File, Form
import shutil

UPLOAD_DIR = Path("uploads")
ALLOWED_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

@app.post("/upload", response_model=UploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    session_id: str = Form(...)
):
    """Upload a video file for transcription."""
    # Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return UploadResponse(
            success=False,
            error=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Create session upload directory
    session_upload_dir = UPLOAD_DIR / session_id
    session_upload_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    file_id = str(uuid.uuid4())[:8]
    safe_filename = f"{file_id}_{file.filename}"
    file_path = session_upload_dir / safe_filename

    # Stream file to disk
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return UploadResponse(
            success=True,
            file_id=file_id,
            file_path=str(file_path.resolve())
        )
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return UploadResponse(success=False, error="Upload failed")
```

### 5.5 Integrate Storage with SessionActor

**File:** `web_app.py`

Update `process_message()` to save messages:
```python
async def process_message(self, message: str) -> str:
    # ... existing code ...

    self._is_processing = True

    # Save user message to history
    storage.save_message(self.session_id, 'user', message)

    try:
        # ... existing processing logic ...

        response_text = "\n".join(full_text)

        # Save agent response to history
        storage.save_message(self.session_id, 'agent', response_text)

        await self.response_queue.put(response_text)
    # ... rest of method ...
```

---

## Part 6: Update .gitignore

**File:** `.gitignore`

Add:
```
# Storage directories
data/
uploads/
```

---

## Testing Checklist

### Concurrency Tests
- [x] Concurrent session creation with same ID creates only one worker
- [x] Session cleanup occurs after TTL expires
- [x] Worker properly cancels on stop()
- [x] No race conditions when accessing active_sessions

### Async Tests
- [x] Transcription doesn't block event loop
- [x] File writing doesn't block event loop
- [x] Timeout fires correctly for long operations

### Storage Tests
- [x] Messages persist across server restarts
- [x] Session list sorted by updated_at
- [x] Transcript registration works correctly
- [x] Delete operations clean up files

### API Tests
- [x] All new endpoints return correct status codes
- [x] File upload accepts only valid video extensions
- [x] Download returns correct file with proper headers

---

## Implementation Order

1. **Logging & Config** - Foundation for all other changes
2. **Session Lock** - Prevents race conditions during subsequent changes
3. **asyncio.Event** - Replace is_running boolean
4. **Update SessionActor methods** - start, stop, get_greeting, process_message
5. **Worker loop update** - Better error handling, timeout on queue
6. **Cleanup task** - Session TTL management
7. **get_or_create_session update** - Use lock
8. **Async tool wrappers** - transcribe_tool.py, file_tool.py
9. **Storage infrastructure** - storage.py, web_app_models.py
10. **New endpoints** - status, history, transcripts, upload
11. **Integration** - Wire storage to SessionActor
