---
paths: tests/**/*.py
---

# Testing Conventions

## Framework
- Use pytest with `pytest-asyncio` for async tests
- Fixtures in `tests/conftest.py`
- Run: `uv run pytest` (or `pytest -v` for verbose)

## Test Organization
- `test_api.py` — FastAPI endpoints, validation
- `test_storage.py` — File persistence, atomicity
- `test_concurrency.py` — Race conditions, TTL
- `test_async.py` — Timeouts, queue behavior
- `test_cost.py` — Usage tracking
- `test_permissions.py` — Access controls
- `test_structured.py` — Schema validation

## Async Tests
```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result.success
```

## Fixtures
- Use `@pytest.fixture` for reusable test setup
- Prefer function-scoped fixtures for isolation
- Use `tmp_path` fixture for temporary file operations

## Assertions
- Use specific assertions: `assert result == expected`
- Test edge cases and error conditions
- Verify cleanup happens (temp files, sessions)
