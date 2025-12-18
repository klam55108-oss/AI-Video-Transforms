---
paths: tests/**/*.py
---

# Testing Conventions

## Framework

- Use pytest with `pytest-asyncio` for async tests
- Fixtures defined in `tests/conftest.py`
- Run: `uv run pytest` or `uv run pytest -v` for verbose

## Test Organization (601 tests across 29 modules)

### Core Tests
| File | Description |
|------|-------------|
| `test_api.py` | FastAPI endpoints, validation |
| `test_api_deps.py` | Dependency injection providers |
| `test_api_integration.py` | End-to-end API integration |
| `test_config.py` | Settings, env overrides, singleton caching |
| `test_services.py` | Service layer (SessionService, StorageService) |
| `test_storage.py` | File persistence, atomicity |
| `test_concurrency.py` | Race conditions, TTL |
| `test_async.py` | Timeouts, queue behavior |
| `test_cost.py` | Usage tracking |
| `test_permissions.py` | Access controls, path validation |
| `test_structured.py` | Schema validation |
| `test_transcribe_tool.py` | Transcription logic |
| `test_job_queue.py` | Job queue service and API |
| `test_error_schema.py` | Unified error schema |

### Knowledge Graph Tests
| File | Description |
|------|-------------|
| `test_kg_api.py` | KG API endpoints |
| `test_kg_api_extraction.py` | Extraction API tests |
| `test_kg_domain.py` | Domain models (ThingType, KGProject) |
| `test_kg_e2e_flow.py` | End-to-end KG workflows |
| `test_kg_extraction_tool.py` | Extraction tool logic |
| `test_kg_integration.py` | KG integration tests |
| `test_kg_knowledge_base.py` | Graph storage (NetworkX) |
| `test_kg_mcp_tools.py` | KG MCP tool registration |
| `test_kg_persistence.py` | JSON/GraphML export |
| `test_kg_schemas.py` | Extraction schemas |
| `test_kg_service.py` | KnowledgeGraphService |
| `test_kg_service_extraction.py` | Service extraction logic |
| `test_kg_templates.py` | Prompt templates |
| `test_kg_tools.py` | Bootstrap/extraction tools |

### MCP Server Tests
| File | Description |
|------|-------------|
| `test_codex_mcp.py` | Codex tools, error handling |

## Async Tests

```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result.success
```

## FastAPI Dependency Overrides (CRITICAL)

```python
# ✅ CORRECT: Use app.dependency_overrides
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

- Services auto-initialized at test session start via conftest.py
- NEVER call `services_lifespan()` in individual tests
- If testing lifespan, save/restore `_services` global

## Centralized Fixtures (conftest.py)

```python
# Available fixtures:
@pytest.fixture
def kg_service(tmp_path: Path) -> KnowledgeGraphService

@pytest.fixture
def sample_domain_profile() -> DomainProfile

@pytest.fixture
def sample_transcript() -> str
```

## Best Practices

- Use `@pytest.fixture` for reusable test setup
- Prefer function-scoped fixtures for isolation
- Use `tmp_path` fixture for temporary file operations
- Test edge cases and error conditions
- Verify cleanup happens (temp files, sessions)
