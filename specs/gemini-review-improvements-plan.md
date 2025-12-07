# Implementation Plan: Gemini Review Recommendations

## Overview

This plan addresses three recommendations from Gemini's code review:

| Priority | Recommendation | Effort |
|----------|----------------|--------|
| 🔴 High | Add read protection to `transcribe_video` | Low |
| 🟡 Medium | Progress feedback for long transcriptions | Medium |
| 🟢 Low | Replace MoviePy with direct FFmpeg | Medium |

---

## 1. Add Read Protection to `transcribe_video` (🔴 High Priority)

### Problem
The `transcribe_video` tool allows reading from any path, including sensitive system directories. While write operations are protected via `permissions.py`, read operations are not.

### Solution
Extend the existing permission system to validate read paths using OWASP best practices.

### Files to Modify

| File | Change |
|------|--------|
| `app/core/permissions.py` | Add `validate_read_path()` function + extend permission handler |
| `app/agent/transcribe_tool.py` | Add path validation before file access |
| `tests/test_permissions.py` | Add tests for read path validation |

### Implementation Details

#### 1.1 Add `validate_read_path()` to `permissions.py`

```python
def validate_read_path(
    file_path: str,
    allowed_extensions: list[str] | None = None,
) -> tuple[bool, str]:
    """
    Validate file path for read operations using OWASP best practices.

    - Resolves path to prevent traversal attacks (../etc/passwd)
    - Checks against BLOCKED_SYSTEM_PATHS
    - Optionally validates file extension
    """
    try:
        path = Path(file_path).resolve()
    except (OSError, ValueError) as e:
        return False, f"Invalid path format: {e}"

    # Check blocked paths
    path_str = str(path)
    for blocked in BLOCKED_SYSTEM_PATHS:
        if path_str.startswith(blocked):
            return False, f"Cannot read from system directory: {blocked}"

    # Check extension if specified
    if allowed_extensions:
        if path.suffix.lower() not in allowed_extensions:
            return False, f"Unsupported file format: {path.suffix}"

    return True, ""
```

#### 1.2 Update permission handler for transcribe_video

Add to `permission_handler()` in `permissions.py`:

```python
# Handle read operations for transcribe_video
if tool_name == "mcp__video-tools__transcribe_video":
    video_source = input_data.get("video_source", "")

    # Skip validation for YouTube URLs
    if not _is_url(video_source):
        is_valid, error_msg = validate_read_path(
            video_source,
            allowed_extensions=[".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".flv"]
        )
        if not is_valid:
            return PermissionResultDeny(
                message=error_msg,
                interrupt=True,
            )
```

#### 1.3 Add defensive validation in `transcribe_tool.py`

In `_perform_transcription()`, after YouTube detection:

```python
if not is_youtube:
    from app.core.permissions import validate_read_path, BLOCKED_SYSTEM_PATHS

    is_valid, error_msg = validate_read_path(
        video_source,
        allowed_extensions=[".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".flv"]
    )
    if not is_valid:
        return {
            "success": False,
            "error": error_msg,
            "source": video_source,
        }
```

### Tests to Add

```python
# test_permissions.py
@pytest.mark.parametrize("path,expected", [
    ("/etc/passwd", False),
    ("/home/user/video.mp4", True),
    ("../../../etc/passwd", False),
    ("/var/log/auth.log", False),
])
def test_validate_read_path(path, expected):
    is_valid, _ = validate_read_path(path)
    assert is_valid == expected
```

---

## 2. Progress Feedback for Transcriptions (🟡 Medium Priority)

### Problem
Long transcriptions show only "Processing..." with no segment-level progress. Users have no visibility into operation status.

### Solution
Implement **both**:
1. SSE (Server-Sent Events) endpoint for real-time progress streaming
2. Enhanced `/status` endpoint with progress info (for polling fallback)

UI: **Visual progress bar** with percentage + segment text.

### Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend  │◄────│ SSE /progress/   │◄────│  SessionActor   │
│ EventSource │     │ StreamingResponse│     │ progress dict   │
│ + Progress  │     │                  │     │                 │
│    Bar UI   │     │ + /status (poll) │     │                 │
└─────────────┘     └──────────────────┘     └─────────────────┘
                                                      ▲
                                                      │
                                              ┌───────┴───────┐
                                              │ transcribe_   │
                                              │ tool callback │
                                              └───────────────┘
```

### Files to Modify

| File | Change |
|------|--------|
| `app/core/session.py` | Add `progress` dict to SessionActor |
| `app/agent/transcribe_tool.py` | Add progress callback parameter |
| `app/main.py` | Add `/progress/{session_id}` SSE + enhance `/status` |
| `app/models/api.py` | Add `ProgressUpdate` model + update `StatusResponse` |
| `app/static/script.js` | Add EventSource + progress bar UI |
| `app/templates/index.html` | Add progress bar HTML element |
| `app/static/style.css` | Add progress bar styles |

### Implementation Details

#### 2.1 Add progress tracking to SessionActor (`session.py`)

```python
class SessionActor:
    def __init__(self, session_id: str):
        # ... existing code ...
        self.current_progress: dict[str, Any] = {
            "stage": None,      # "extracting", "splitting", "transcribing", "saving"
            "current": 0,       # Current segment
            "total": 0,         # Total segments
            "details": None,    # Human-readable message
        }

    def update_progress(self, stage: str, current: int, total: int, details: str | None = None) -> None:
        """Thread-safe progress update."""
        self.current_progress = {
            "stage": stage,
            "current": current,
            "total": total,
            "details": details or f"{stage}: {current}/{total}",
        }
```

#### 2.2 Add SSE endpoint + enhance /status (`main.py`)

```python
from fastapi.responses import StreamingResponse
import json

# NEW: SSE endpoint for real-time streaming
@app.get("/progress/{session_id}")
async def progress_stream(session_id: str):
    """SSE endpoint for real-time progress updates."""
    actor = active_sessions.get(session_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        while actor.is_processing:
            progress = actor.current_progress
            yield f"data: {json.dumps(progress)}\n\n"
            await asyncio.sleep(0.5)  # 500ms update interval

        # Final message
        yield f"data: {json.dumps({'stage': 'complete', 'current': 0, 'total': 0})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

# ENHANCED: Add progress to existing /status endpoint
@app.get("/status/{session_id}", response_model=StatusResponse)
async def get_status(session_id: str):
    actor = active_sessions.get(session_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Session not found")

    return StatusResponse(
        status=actor.status,
        session_id=session_id,
        message=actor.current_progress.get("details"),
        progress=ProgressUpdate(
            stage=actor.current_progress.get("stage"),
            current=actor.current_progress.get("current", 0),
            total=actor.current_progress.get("total", 0),
            percentage=_calc_percentage(actor.current_progress),
        ) if actor.is_processing else None,
    )

def _calc_percentage(progress: dict) -> int:
    if progress.get("total", 0) == 0:
        return 0
    return int((progress.get("current", 0) / progress["total"]) * 100)
```

#### 2.2b Update models (`api.py`)

```python
class ProgressUpdate(BaseModel):
    stage: str | None = None
    current: int = 0
    total: int = 0
    percentage: int = 0
    details: str | None = None

class StatusResponse(BaseModel):
    status: AgentStatus
    session_id: str | None = None
    message: str | None = None
    progress: ProgressUpdate | None = None  # NEW
```

#### 2.3 Add progress callback to transcribe_tool

Modify `_perform_transcription()` signature:

```python
def _perform_transcription(
    video_source: str,
    output_file: str | None = None,
    language: str | None = None,
    progress_callback: Callable[[str, int, int, str | None], None] | None = None,
) -> dict[str, Any]:
```

Add callbacks in the transcription flow:

```python
# After audio extraction
if progress_callback:
    progress_callback("extracting", 1, 1, "Audio extracted successfully")

# In segment loop
for i, segment in enumerate(segments):
    if progress_callback:
        progress_callback("transcribing", i + 1, len(segments), f"Transcribing segment {i + 1} of {len(segments)}")

    segment_text = _transcribe_segment(...)
```

#### 2.4 Wire callback through session context

Since MCP tools run in isolation, use a thread-safe global registry:

```python
# app/core/progress_registry.py
from threading import Lock
from typing import Callable

_progress_callbacks: dict[str, Callable] = {}
_lock = Lock()

def register_callback(session_id: str, callback: Callable) -> None:
    with _lock:
        _progress_callbacks[session_id] = callback

def get_callback(session_id: str) -> Callable | None:
    with _lock:
        return _progress_callbacks.get(session_id)

def unregister_callback(session_id: str) -> None:
    with _lock:
        _progress_callbacks.pop(session_id, None)
```

#### 2.5 Frontend Progress Bar UI

**HTML (`index.html`)** - Add progress bar container:

```html
<!-- Add inside the status indicator area -->
<div id="progress-container" class="hidden mt-2">
    <div class="flex items-center gap-2">
        <div class="flex-1 bg-slate-700 rounded-full h-2 overflow-hidden">
            <div id="progress-bar" class="bg-blue-500 h-full transition-all duration-300" style="width: 0%"></div>
        </div>
        <span id="progress-percent" class="text-xs text-slate-400 w-12">0%</span>
    </div>
    <p id="progress-details" class="text-xs text-slate-400 mt-1">Initializing...</p>
</div>
```

**JavaScript (`script.js`)** - EventSource + progress bar:

```javascript
let progressEventSource = null;

function connectProgressStream(sessionId) {
    if (progressEventSource) {
        progressEventSource.close();
    }

    progressEventSource = new EventSource(`/progress/${sessionId}`);

    progressEventSource.onmessage = (event) => {
        const progress = JSON.parse(event.data);
        updateProgressBar(progress);
    };

    progressEventSource.onerror = () => {
        progressEventSource.close();
        hideProgressBar();
    };

    showProgressBar();
}

function updateProgressBar(progress) {
    const container = document.getElementById('progress-container');
    const bar = document.getElementById('progress-bar');
    const percent = document.getElementById('progress-percent');
    const details = document.getElementById('progress-details');

    if (progress.stage === 'complete') {
        hideProgressBar();
        return;
    }

    container.classList.remove('hidden');

    // Calculate percentage
    const pct = progress.total > 0
        ? Math.round((progress.current / progress.total) * 100)
        : 0;

    bar.style.width = `${pct}%`;
    percent.textContent = `${pct}%`;
    details.textContent = progress.details || `${progress.stage}: ${progress.current}/${progress.total}`;
}

function showProgressBar() {
    document.getElementById('progress-container').classList.remove('hidden');
}

function hideProgressBar() {
    document.getElementById('progress-container').classList.add('hidden');
    document.getElementById('progress-bar').style.width = '0%';
}

// Connect when processing starts
async function sendMessage(message) {
    // ... existing code ...
    connectProgressStream(sessionId);  // Start SSE when sending message
    // ... rest of code ...
}
```

**CSS (`style.css`)** - Progress bar animation:

```css
#progress-bar {
    transition: width 0.3s ease-out;
}

#progress-container.hidden {
    display: none;
}
```

---

## 3. Replace MoviePy with Direct FFmpeg (🟢 Low Priority)

### Problem
MoviePy adds Python overhead and is slower than direct FFmpeg for simple audio extraction. Per web research, MoviePy can be 20+ seconds slower than FFmpeg subprocess for the same operation.

### Solution
Replace MoviePy's `VideoFileClip` with direct `ffmpeg` subprocess calls. **FFmpeg only - no fallback** (require FFmpeg, fail with clear error if not found).

### Files to Modify

| File | Change |
|------|--------|
| `app/agent/transcribe_tool.py` | Replace `_extract_audio_from_video()` |
| `pyproject.toml` | Remove `moviepy` dependency |

### Implementation Details

#### 3.1 Replace `_extract_audio_from_video()` function

```python
import subprocess
import shutil

def _extract_audio_from_video(video_path: str, output_dir: str) -> str:
    """Extract audio from video file using FFmpeg directly."""
    # Check ffmpeg availability
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg not found. Please install FFmpeg.")

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    output_audio_path = os.path.join(output_dir, f"{base_name}_audio.wav")

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vn",                    # No video
        "-acodec", "pcm_s16le",   # PCM 16-bit (same as MoviePy)
        "-ar", "44100",           # Sample rate
        "-ac", "2",               # Stereo
        "-y",                     # Overwrite
        output_audio_path
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300  # 5 minute timeout
    )

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr}")

    return output_audio_path
```

#### 3.2 Benefits

| Aspect | MoviePy | Direct FFmpeg |
|--------|---------|---------------|
| Startup time | ~2-3s (Python import) | ~50ms |
| Memory | Higher (loads video metadata) | Lower |
| Dependencies | Large (numpy, decorator, etc.) | None (system binary) |
| Error messages | Python tracebacks | Clear FFmpeg errors |

#### 3.3 Update `pyproject.toml`

```diff
dependencies = [
    "claude-agent-sdk>=0.1.10",
    "fastapi>=0.123.5",
-   "moviepy>=2.2.1",
    "pydub>=0.25.1",
    # ... rest
]
```

#### 3.4 Remove type ignore comment

```diff
- from moviepy import VideoFileClip  # type: ignore[import-untyped]
+ # No MoviePy import needed - using FFmpeg directly
```

---

## Implementation Order

1. **Phase 1: Security (Day 1)**
   - Implement read path validation
   - Add tests
   - This is the highest priority security fix

2. **Phase 2: Progress Feedback (Days 2-3)**
   - Add SessionActor progress tracking
   - Implement SSE endpoint
   - Wire up transcribe_tool callback
   - Update frontend

3. **Phase 3: FFmpeg Migration (Day 4)**
   - Replace MoviePy function
   - Test with various video formats
   - Remove dependency

---

## Testing Strategy

### Unit Tests
- Path validation edge cases (traversal, symlinks, extensions)
- Progress callback invocation
- FFmpeg command construction

### Integration Tests
- SSE endpoint connection/disconnection
- Full transcription with progress updates
- Error handling during transcription

### Manual Testing
- YouTube URL transcription (should skip path validation)
- Local file transcription with progress UI
- Attempt to read from /etc/ (should be blocked)

---

## Rollback Plan

Each feature can be reverted independently:
1. **Read protection**: Remove validation calls, keep backward compatibility
2. **Progress feedback**: SSE endpoint is additive, frontend falls back to polling
3. **FFmpeg**: Keep MoviePy as fallback, feature-flag the implementation

---

## Summary: All Files to Modify

| File | Changes |
|------|---------|
| `app/core/permissions.py` | Add `validate_read_path()`, extend permission handler |
| `app/core/session.py` | Add `current_progress` dict + `update_progress()` |
| `app/core/progress_registry.py` | **NEW FILE** - Thread-safe callback registry |
| `app/agent/transcribe_tool.py` | Add path validation, progress callback, replace MoviePy |
| `app/main.py` | Add `/progress` SSE endpoint, enhance `/status` |
| `app/models/api.py` | Add `ProgressUpdate` model, update `StatusResponse` |
| `app/static/script.js` | Add EventSource + progress bar functions |
| `app/templates/index.html` | Add progress bar HTML |
| `app/static/style.css` | Add progress bar styles |
| `pyproject.toml` | Remove `moviepy` dependency |
| `tests/test_permissions.py` | Add read path validation tests |

**Total: 10 modified files + 1 new file**

---

## User Decisions Captured

- **FFmpeg**: FFmpeg only, no MoviePy fallback
- **Progress UI**: Visual progress bar with percentage
- **Status API**: Enhance both `/status` AND add `/progress` SSE endpoint

---

## Sources

- [OWASP Path Traversal Prevention](https://owasp.org/www-community/attacks/Path_Traversal)
- [FastAPI StreamingResponse Docs](https://fastapi.tiangolo.com/advanced/custom-response/)
- [FFmpeg vs MoviePy Performance (GitHub Issue #2165)](https://github.com/Zulko/moviepy/issues/2165)
- [FastAPI SSE Best Practices (Medium)](https://medium.com/@connect.hashblock/real-time-streaming-api-with-fastapi-sse-and-async-event-buffers-building-lightning-fast-data-ad00afb1c0f1)
- Local: `/home/rudycosta3/agent-video-to-data/ai_docs/CLAUDE_AGENT_SDK_SUMMARY.md`
