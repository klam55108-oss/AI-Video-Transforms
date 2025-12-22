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
| `APP_DATA_PATH` | `data` | Base path for data storage |
| `APP_CLAUDE_MODEL` | `claude-opus-4-5` | Claude model ID |
| `APP_CLAUDE_API_MAX_CONCURRENT` | `2` | Max concurrent Claude API calls |
| `APP_RESPONSE_TIMEOUT` | `300.0` | Agent response timeout (seconds) |
| `APP_GREETING_TIMEOUT` | `30.0` | Initial greeting timeout (seconds) |
| `APP_SESSION_TTL` | `3600.0` | Session expiry (seconds) |
| `APP_CLEANUP_INTERVAL` | `300.0` | Cleanup task interval (seconds) |
| `APP_GRACEFUL_SHUTDOWN_TIMEOUT` | `5.0` | Shutdown grace period (seconds) |
| `APP_QUEUE_MAX_SIZE` | `10` | Max pending messages per session |
| `APP_KG_PROJECT_CACHE_MAX_SIZE` | `100` | LRU cache size for KG projects |
| `APP_KG_POLL_INTERVAL_MS` | `5000` | Frontend KG status poll interval (ms) |
| `APP_STATUS_POLL_INTERVAL_MS` | `3000` | Frontend agent status poll interval (ms) |
| `APP_JOB_MAX_CONCURRENT` | `2` | Max concurrent background job execution |
| `APP_JOB_POLL_INTERVAL_MS` | `1000` | Frontend job status poll interval (ms) |
| `APP_EXPORT_TTL_HOURS` | `24` | Auto-cleanup exports older than this |
| `APP_BATCH_EXPORT_MAX_PROJECTS` | `50` | Max projects in single batch export |
| `APP_JOB_PERSIST_INTERVAL_PERCENT` | `10` | Persist job state every N% progress |
| `APP_JOB_RETENTION_HOURS` | `168` | Keep completed jobs for N hours (7 days) |

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

## Frontend Configuration Injection

Poll intervals are injected into the frontend via Jinja2 template:

```python
# app/ui/routes.py
settings = get_settings()
return templates.TemplateResponse(
    request,
    "index.html",
    {
        "kg_poll_interval_ms": settings.kg_poll_interval_ms,
        "status_poll_interval_ms": settings.status_poll_interval_ms,
    },
)
```

```html
<!-- app/templates/index.html -->
<script>
    window.APP_CONFIG = {
        KG_POLL_INTERVAL_MS: {{ kg_poll_interval_ms }},
        STATUS_POLL_INTERVAL_MS: {{ status_poll_interval_ms }}
    };
</script>
```

```javascript
// app/static/script.js - reads with fallback
const KG_POLL_INTERVAL_MS = window.APP_CONFIG?.KG_POLL_INTERVAL_MS || 5000;
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
