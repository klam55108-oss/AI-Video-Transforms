---
paths: app/api/**/*.py, app/models/**/*.py, app/main.py
---

# FastAPI Patterns

## Architecture

| File | Purpose |
|------|---------|
| `app/main.py` | Slim entry point (~80 lines), mounts routers |
| `app/api/routers/` | 7 endpoint routers |
| `app/api/deps.py` | Dependency injection providers |
| `app/api/errors.py` | Centralized error handlers |

## Routers (7 total)

| Router | Prefix | Description |
|--------|--------|-------------|
| `chat.py` | `/chat`, `/status` | Chat sessions, agent status |
| `history.py` | `/history` | Session history management |
| `transcripts.py` | `/transcripts` | Transcript library |
| `cost.py` | `/cost` | Token usage tracking |
| `upload.py` | `/upload` | Video file uploads |
| `kg.py` | `/kg` | Knowledge graph projects |
| (ui) | `/` | Web dashboard |

## Endpoint Design

- Use `HTTPException` with appropriate status codes
- Validate all inputs with Pydantic models
- Return Pydantic models or `dict` responses

## Dependency Injection (CRITICAL)

```python
# ✅ CORRECT: Define provider in app/api/deps.py
def get_session_service() -> SessionService:
    return get_services().session

def get_kg_service() -> KnowledgeGraphService:
    return get_services().kg

# ✅ CORRECT: Use in routers
@router.post("/chat/init")
async def init(
    request: InitRequest,
    session_svc: SessionService = Depends(get_session_service)
):
    ...

# ❌ NEVER: Import services directly in routers
from app.core.session import SessionActor  # NEVER do this in routers
```

## Security Rules

- ALWAYS validate UUID v4 format for session/transcript IDs
- NEVER allow file operations on system paths (`/etc`, `/usr`, `/bin`)
- ALWAYS use `FileUploadValidator` for uploads (500MB limit)
- NEVER trust user input without Pydantic validation

## Pydantic Models

| Location | Purpose |
|----------|---------|
| `app/models/api.py` | API response schemas (CreateProjectResponse, etc.) |
| `app/models/requests.py` | API request schemas (CreateProjectRequest, BootstrapRequest, etc.) |
| `app/models/service.py` | Service layer contracts |
| `app/models/structured.py` | Agent output schemas |

## Error Responses

```python
raise HTTPException(status_code=404, detail="Session not found")
raise HTTPException(status_code=400, detail="Invalid video format")
raise HTTPException(status_code=503, detail="Service unavailable")
```

## ServiceContainer Pattern

All services accessed via `get_services()` in deps.py:

```python
# Available services:
get_services().session      # SessionService
get_services().storage      # StorageService
get_services().transcription # TranscriptionService
get_services().kg           # KnowledgeGraphService
```

## Session Management

- Sessions stored in `data/sessions/`
- KG projects stored in `data/kg_projects/`
- SessionService wraps SessionActor lifecycle
- Sessions expire after 1 hour (TTL)
