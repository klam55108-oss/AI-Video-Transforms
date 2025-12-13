# Python Code Style

## Type Annotations
- ALL function signatures must include return types
- Use modern union syntax: `str | None` not `Optional[str]`
- Use builtin generics: `list[str]`, `dict[str, Any]` not `List`, `Dict`
- Add `# type: ignore[import-untyped]` for moviepy, pydub imports

## Formatting
- Google-style docstrings for public functions
- Max ~50 lines per function (split if longer)
- Use `pathlib.Path` over `os.path` for all file operations

## Imports
- Group: stdlib → third-party → local
- Absolute imports for app modules: `from app.core.session import SessionActor`

## Async Patterns
- Use `async def` for I/O-bound operations
- Prefer `asyncio.gather()` for parallel operations
- Always handle `asyncio.CancelledError` in long-running tasks
