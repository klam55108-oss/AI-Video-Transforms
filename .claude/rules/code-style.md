---
paths: "**/*.py"
---

# Python Code Style

## Type Annotations (Strict Mode)

- ALWAYS include return types on ALL function signatures
- Use modern union syntax: `str | None` NOT `Optional[str]`
- Use builtin generics: `list[str]`, `dict[str, Any]` NOT `List`, `Dict`
- Add `# type: ignore[import-untyped]` for pydub imports
- Use `from __future__ import annotations` for forward references

```python
# ✅ Correct
def get_session(session_id: str) -> Session | None:
    ...

async def process_items(items: list[Item]) -> dict[str, Any]:
    ...

# ❌ Wrong
def get_session(session_id: str) -> Optional[Session]:  # Use | None
    ...

def process_items(items: List[Item]) -> Dict[str, Any]:  # Use builtins
    ...
```

## Formatting

- Google-style docstrings for public functions
- Max ~50 lines per function (split if longer)
- ALWAYS use `pathlib.Path` over `os.path` for file operations
- 4-space indentation (enforced by ruff)

```python
def transcribe_video(video_path: Path, output_format: str = "text") -> str:
    """Transcribe video to text using OpenAI Whisper.

    Args:
        video_path: Path to the video file.
        output_format: Output format (text, json, vtt).

    Returns:
        Transcription text.

    Raises:
        FileNotFoundError: If video file doesn't exist.
    """
    ...
```

## Imports

```python
# Order: stdlib → third-party → local (blank line between groups)
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import Depends
from pydantic import BaseModel, Field

from app.core.session import SessionActor
from app.services import SessionService
```

## Async Patterns

- Use `async def` for ALL I/O-bound operations
- Use `asyncio.gather()` for parallel operations
- ALWAYS handle `asyncio.CancelledError` in long-running tasks
- Use `asyncio.Queue` for producer-consumer patterns

```python
# ✅ Correct: Parallel execution
results = await asyncio.gather(
    fetch_transcript(id1),
    fetch_transcript(id2),
    fetch_transcript(id3),
)

# ✅ Correct: Handle cancellation
async def long_running_task():
    try:
        while True:
            await process_next()
    except asyncio.CancelledError:
        await cleanup()
        raise
```

## Pydantic Models

- Use `Field()` for validation and documentation
- Use `model_dump()` not deprecated `.dict()`
- Use `model_validate()` not deprecated `.parse_obj()`

```python
class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Project name")
```

## Error Handling

- Use specific exception types, not bare `Exception`
- Log errors with context before re-raising
- Return structured errors in API/tool boundaries

```python
# ✅ Correct
try:
    result = await process()
except FileNotFoundError as e:
    logger.error(f"File not found: {e}")
    raise HTTPException(status_code=404, detail=str(e))

# ❌ Wrong
except Exception:
    raise  # Too broad
```
