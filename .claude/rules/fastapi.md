---
paths: app/api/**/*.py, app/models/**/*.py, app/main.py
---

# FastAPI Patterns

## Architecture
- `app/main.py` — Slim entry point (~60 lines), mounts routers
- `app/api/routers/` — Individual endpoint routers (chat, history, transcripts, cost, upload)
- `app/api/deps.py` — Dependency injection providers
- `app/api/errors.py` — Centralized error handlers

## Endpoint Design
- Use `HTTPException` with appropriate status codes
- Validate all inputs with Pydantic models
- Return Pydantic models or `dict` responses

## Dependency Injection
```python
# Define provider in app/api/deps.py
def get_session_service() -> SessionService:
    return get_services().session

# Use in routers
@router.post("/chat/init")
async def init(
    request: InitRequest,
    session_svc: SessionService = Depends(get_session_service)
):
    ...
```

## Security
- Validate UUID v4 format for session/transcript IDs
- Block system paths (`/etc`, `/usr`, `/bin`) in file operations
- Use `FileUploadValidator` for uploads (500MB limit)

## Pydantic Models
- `app/models/api.py` — API response schemas
- `app/models/requests.py` — API request schemas
- `app/models/service.py` — Service layer contracts
- `app/models/structured.py` — Agent output schemas

## Error Responses
```python
raise HTTPException(status_code=404, detail="Session not found")
raise HTTPException(status_code=400, detail="Invalid video format")
raise HTTPException(status_code=503, detail="Service unavailable")
```

## Session Management
- Sessions stored in `data/sessions/`
- SessionService wraps SessionActor lifecycle
- Sessions expire after 1 hour (TTL)
