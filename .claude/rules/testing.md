---
paths: tests/**/*.py
---

# Testing Conventions

## Framework

- Use pytest with `pytest-asyncio` for async tests
- Fixtures defined in `tests/conftest.py`
- Run: `uv run pytest` or `uv run pytest -v` for verbose

## Test Organization (230 tests)
- `test_api.py` — FastAPI endpoints, validation
- `test_api_deps.py` — Dependency injection providers
- `test_api_integration.py` — End-to-end API integration
- `test_services.py` — Service layer (SessionService, StorageService)
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

## FastAPI Dependency Overrides
```python
# CORRECT: Use app.dependency_overrides
from app.api.deps import get_session_service
from app.main import app

mock_service = MockSessionService()
app.dependency_overrides[get_session_service] = lambda: mock_service
try:
    async with AsyncClient(transport=ASGITransport(app=app)) as client:
        response = await client.post("/chat/init", ...)
finally:
    app.dependency_overrides.pop(get_session_service, None)

# ❌ WRONG: patch() doesn't work with FastAPI Depends()
# with patch("app.api.deps.get_session_service"):  # NEVER do this!
```

## Service Initialization

Tests rely on conftest.py session-scoped fixture:
- Services auto-initialized at test session start
- NEVER call `services_lifespan()` in individual tests
- If testing lifespan, save/restore `_services` global

## Fixtures
- Use `@pytest.fixture` for reusable test setup
- Prefer function-scoped fixtures for isolation
- Use `tmp_path` fixture for temporary file operations

## Assertions
- Use specific assertions: `assert result == expected`
- Test edge cases and error conditions
- Verify cleanup happens (temp files, sessions)
