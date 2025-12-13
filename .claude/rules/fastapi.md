---
paths: app/main.py, app/models/**/*.py, app/core/validators.py
---

# FastAPI Patterns

## Endpoint Design
- Use `HTTPException` with appropriate status codes for errors
- Validate all inputs with Pydantic models
- Return Pydantic models or `dict` responses

## Security
- Validate UUID v4 format for session/transcript IDs
- Block system paths (`/etc`, `/usr`, `/bin`) in file operations
- Use `FileUploadValidator` for uploaded files (500MB limit)

## Pydantic Models
- Define in `app/models/api.py` for request/response schemas
- Define in `app/models/structured.py` for agent output schemas
- Use `model_validate()` for runtime validation

## Error Responses
```python
raise HTTPException(status_code=404, detail="Session not found")
raise HTTPException(status_code=400, detail="Invalid video format")
raise HTTPException(status_code=503, detail="Service unavailable")
```

## Session Management
- Sessions stored in `data/sessions/`
- Use `storage.save_session()` and `storage.load_session()`
- Sessions expire after 1 hour (TTL)
