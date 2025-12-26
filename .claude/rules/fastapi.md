---
paths: app/api/**/*.py, app/models/**/*.py, app/main.py
---

# FastAPI Patterns

## Architecture

| File | Purpose |
|------|---------|
| `app/main.py` | Slim entry point (~80 lines), mounts routers |
| `app/api/routers/` | 9 endpoint routers |
| `app/api/deps.py` | Dependency injection providers |
| `app/api/errors.py` | Centralized error handlers |

## Routers (9 total)

| Router | Prefix | Description |
|--------|--------|-------------|
| `chat.py` | `/chat`, `/status`, `/chat/activity` | Chat sessions, agent status, activity streaming |
| `history.py` | `/history` | Session history management |
| `transcripts.py` | `/transcripts` | Transcript library |
| `cost.py` | `/cost` | Token usage tracking |
| `upload.py` | `/upload` | Video file uploads |
| `kg.py` | `/kg` | Knowledge graph projects |
| `jobs.py` | `/jobs` | Background job queue |
| `audit.py` | `/audit` | Audit trail logs and statistics |
| (ui) | `/` | Web dashboard |

## Endpoint Design

- Use `HTTPException` with appropriate status codes
- Validate all inputs with Pydantic models
- Return Pydantic models or `dict` responses

### Route Ordering (CRITICAL)

FastAPI matches routes in declaration order. Place specific routes BEFORE parameterized routes:

```python
# ✅ CORRECT: List route first
@router.get("")
async def list_jobs(): ...

@router.get("/{job_id}")
async def get_job(job_id: str): ...

# ❌ WRONG: Parameterized route first catches everything
@router.get("/{job_id}")  # GET /jobs matches with job_id=""
async def get_job(job_id: str): ...

@router.get("")  # Never reached!
async def list_jobs(): ...
```

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
| `app/models/jobs.py` | Job queue models (Job, JobType, JobStatus, JobStage) |
| `app/models/errors.py` | Unified error schema (APIError, ErrorCode) |
| `app/models/audit.py` | Audit event models (ToolAuditEvent, SessionAuditEvent) |

## Error Responses

```python
raise HTTPException(status_code=400, detail="Invalid video format")
raise HTTPException(status_code=404, detail="Session not found")
raise HTTPException(status_code=410, detail="Session expired")  # Frontend handles gracefully
raise HTTPException(status_code=503, detail="Service unavailable")
```

**Note**: HTTP 410 (Gone) indicates session expiry. Frontend shows user-friendly message and clears session state.

## ServiceContainer Pattern

All services accessed via `get_services()` in deps.py:

```python
# Available services:
get_services().session       # SessionService
get_services().storage       # StorageService
get_services().transcription # TranscriptionService
get_services().kg            # KnowledgeGraphService
get_services().job_queue     # JobQueueService
get_services().audit         # AuditService
```

## Session Management

- Sessions stored in `data/sessions/`
- KG projects stored in `data/kg_projects/`
- SessionService wraps SessionActor lifecycle
- Sessions expire after 1 hour (TTL)
