---
paths: "**/*.py"
---

# Python Code Style

## Type Annotations (Strict Mode)

- ALWAYS include return types on ALL function signatures
- Use modern union syntax: `str | None` NOT `Optional[str]`
- Use builtin generics: `list[str]`, `dict[str, Any]` NOT `List`, `Dict`
- Add `# type: ignore[import-untyped]` for pydub imports

## Formatting

- Google-style docstrings for public functions
- Max ~50 lines per function (split if longer)
- ALWAYS use `pathlib.Path` over `os.path` for file operations

## Imports

```python
# Order: stdlib → third-party → local (blank line between groups)
import asyncio
from pathlib import Path

from fastapi import Depends
from pydantic import BaseModel

from app.core.session import SessionActor
from app.services import SessionService
```

## Async Patterns

- Use `async def` for ALL I/O-bound operations
- Use `asyncio.gather()` for parallel operations
- ALWAYS handle `asyncio.CancelledError` in long-running tasks
