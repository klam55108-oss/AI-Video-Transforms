---
paths: app/core/config.py, app/core/session.py, app/services/kg_service.py
---

# Configuration Patterns

## Centralized Settings (`app/core/config.py`)

All application configuration uses Pydantic Settings with environment variable overrides:

```python
from app.core.config import get_settings

settings = get_settings()
model = settings.claude_model
timeout = settings.response_timeout
```

## Environment Variables

All settings use the `APP_` prefix (automatically stripped by pydantic-settings):

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_CLAUDE_MODEL` | `claude-opus-4-5` | Claude model ID |
| `APP_CLAUDE_API_MAX_CONCURRENT` | `2` | Max concurrent Claude API calls |
| `APP_RESPONSE_TIMEOUT` | `300.0` | Agent response timeout (seconds) |
| `APP_GREETING_TIMEOUT` | `30.0` | Initial greeting timeout (seconds) |
| `APP_SESSION_TTL` | `3600.0` | Session expiry (seconds) |
| `APP_CLEANUP_INTERVAL` | `300.0` | Cleanup task interval (seconds) |
| `APP_GRACEFUL_SHUTDOWN_TIMEOUT` | `5.0` | Shutdown grace period (seconds) |
| `APP_QUEUE_MAX_SIZE` | `10` | Max pending messages per session |
| `APP_KG_PROJECT_CACHE_MAX_SIZE` | `100` | LRU cache size for KG projects |

## Settings Singleton

```python
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    """Cached singleton — instantiated once on first call."""
    return Settings()
```

## Critical Rules

- ALWAYS use `get_settings()` instead of instantiating `Settings()` directly
- ALWAYS access config at runtime, not module load (avoids import-time env reads)
- NEVER hardcode values that should be configurable
- NEVER store secrets in config — use environment variables directly

## Concurrency Control

The `APP_CLAUDE_API_MAX_CONCURRENT` setting controls a semaphore that limits parallel Claude API calls:

```python
# In KnowledgeGraphService
self._claude_semaphore = asyncio.Semaphore(
    get_settings().claude_api_max_concurrent
)

# Wrap Claude calls
async with self._claude_semaphore:
    result = await client.query(prompt)
```

## Cache Eviction

The `APP_KG_PROJECT_CACHE_MAX_SIZE` setting limits in-memory project cache with LRU eviction:

```python
from collections import OrderedDict

self._projects: OrderedDict[str, KGProject] = OrderedDict()

# On access, move to end (most recently used)
self._projects.move_to_end(project_id)

# On insert, evict oldest if over limit
if len(self._projects) >= max_size:
    self._projects.popitem(last=False)
```

## Testing Configuration

Override settings in tests using environment variables or monkeypatch:

```python
def test_with_custom_config(monkeypatch):
    monkeypatch.setenv("APP_CLAUDE_API_MAX_CONCURRENT", "1")
    # Clear cached settings
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.claude_api_max_concurrent == 1
```
