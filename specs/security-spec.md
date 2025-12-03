# Security & Code Quality Spec

## Overview

This spec covers security improvements, input validation, error handling, HTTP status codes, and code quality enhancements for the VideoAgent web application.

---

## Target Files

| File | Action | Description |
|------|--------|-------------|
| `web_app.py` | MODIFY | Input validation, error handling, HTTP status codes |
| `templates/index.html` | MODIFY | Add DOMPurify CDN |
| `static/script.js` | MODIFY | XSS protection, sessionStorage |

---

## Part 1: XSS Protection (High Priority)

### 1.1 Add DOMPurify Library

**File:** `templates/index.html:12` (after marked.js)

```html
<!-- Markdown rendering -->
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<!-- XSS protection for rendered HTML -->
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js"></script>
```

### 1.2 Sanitize Markdown Output

**File:** `static/script.js:86`

Find the line where markdown is rendered:
```javascript
bubble.innerHTML = marked.parse(text);
```

Replace with:
```javascript
// Configure DOMPurify with safe defaults for markdown
const PURIFY_CONFIG = {
    ALLOWED_TAGS: [
        'p', 'br', 'strong', 'em', 'b', 'i',
        'code', 'pre',
        'ul', 'ol', 'li',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'blockquote', 'hr',
        'a',
        'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'span', 'div'
    ],
    ALLOWED_ATTR: ['href', 'class', 'target', 'rel'],
    ALLOW_DATA_ATTR: false,
    FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed'],
    FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover']
};

bubble.innerHTML = DOMPurify.sanitize(marked.parse(text), PURIFY_CONFIG);
```

### 1.3 Test XSS Vectors

After implementation, test with these payloads:
```
<script>alert('xss')</script>
<img src=x onerror="alert('xss')">
<a href="javascript:alert('xss')">click</a>
<div onmouseover="alert('xss')">hover</div>
[link](javascript:alert('xss'))
```

All should be sanitized and display as plain text or be stripped.

---

## Part 2: Session Security (High Priority)

### 2.1 Switch to sessionStorage

**File:** `static/script.js:3-8`

**Current (Vulnerable):**
```javascript
function getSessionId() {
    let sessionId = localStorage.getItem('agent_session_id');
    if (!sessionId) {
        sessionId = crypto.randomUUID();
        localStorage.setItem('agent_session_id', sessionId);
    }
    return sessionId;
}
```

**Fixed:**
```javascript
function getSessionId() {
    // Use sessionStorage for browser-session-only scope
    // This prevents session persistence across browser restarts
    // and isolates sessions per tab
    let sessionId = sessionStorage.getItem('agent_session_id');
    if (!sessionId) {
        sessionId = crypto.randomUUID();
        sessionStorage.setItem('agent_session_id', sessionId);
    }
    return sessionId;
}
```

### 2.2 Update Reset Handler

**File:** `static/script.js:253`

Change:
```javascript
localStorage.removeItem('agent_session_id');
```

To:
```javascript
sessionStorage.removeItem('agent_session_id');
```

---

## Part 3: Input Validation (High Priority)

### 3.1 Add UUID Validation Pattern

**File:** `web_app.py` (after imports)

```python
import re
from pydantic import BaseModel, Field, field_validator

# UUID v4 validation pattern
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    re.IGNORECASE
)
```

### 3.2 Update Pydantic Models with Validators

**File:** `web_app.py:196-205`

Replace existing models:
```python
class ChatRequest(BaseModel):
    """Request model for chat messages."""
    session_id: str = Field(
        ...,
        min_length=36,
        max_length=36,
        description="UUID v4 session identifier"
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="User message content"
    )

    @field_validator('session_id')
    @classmethod
    def validate_session_id_format(cls, v: str) -> str:
        """Validate session_id is a valid UUID v4."""
        if not UUID_PATTERN.match(v):
            raise ValueError('session_id must be a valid UUID v4 format')
        return v

    @field_validator('message')
    @classmethod
    def validate_message_not_empty(cls, v: str) -> str:
        """Validate message is not just whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError('message cannot be empty or whitespace only')
        return stripped


class ChatResponse(BaseModel):
    """Response model for chat messages."""
    response: str
    session_id: str


class InitRequest(BaseModel):
    """Request model for session initialization."""
    session_id: str = Field(
        ...,
        min_length=36,
        max_length=36,
        description="UUID v4 session identifier"
    )

    @field_validator('session_id')
    @classmethod
    def validate_session_id_format(cls, v: str) -> str:
        """Validate session_id is a valid UUID v4."""
        if not UUID_PATTERN.match(v):
            raise ValueError('session_id must be a valid UUID v4 format')
        return v
```

### 3.3 Add Path Parameter Validation for DELETE

**File:** `web_app.py:268-273`

```python
@app.delete("/chat/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session."""
    # Validate session ID format
    if not UUID_PATTERN.match(session_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid session ID format"
        )

    async with sessions_lock:
        if session_id not in active_sessions:
            raise HTTPException(
                status_code=404,
                detail="Session not found"
            )
        actor = active_sessions.pop(session_id)

    await actor.stop()
    logger.info(f"Session deleted: {session_id}")

    return {"status": "success", "message": f"Session {session_id} closed"}
```

---

## Part 4: Error Handling & HTTP Status Codes (Medium Priority)

### 4.1 Add Custom Exception Handling

**File:** `web_app.py` (after imports)

```python
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Custom exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return 422 with structured validation error details."""
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"]
        })

    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": errors
        }
    )
```

### 4.2 Add Safe Error Handler Function

**File:** `web_app.py` (after exception handler)

```python
def handle_endpoint_error(e: Exception, context: str) -> HTTPException:
    """
    Convert exceptions to safe HTTP responses.

    Logs full error details server-side but returns
    generic messages to clients to prevent information leakage.
    """
    if isinstance(e, HTTPException):
        return e

    if isinstance(e, TimeoutError):
        logger.warning(f"{context}: Timeout - {e}")
        return HTTPException(
            status_code=504,
            detail="Request timed out. Please try again."
        )

    if isinstance(e, RuntimeError):
        error_msg = str(e).lower()
        if "closed" in error_msg:
            logger.warning(f"{context}: Session closed - {e}")
            return HTTPException(
                status_code=410,
                detail="Session is closed"
            )

    # Log full error details but don't expose to client
    logger.error(f"{context}: {type(e).__name__}: {e}", exc_info=True)
    return HTTPException(
        status_code=500,
        detail="An internal error occurred. Please try again."
    )
```

### 4.3 Update Endpoint Error Handling

**File:** `web_app.py:237-249` (chat_init endpoint)

```python
@app.post("/chat/init", response_model=ChatResponse)
async def chat_init(request: InitRequest):
    """Initialize a chat session and return the greeting message."""
    try:
        actor = await get_or_create_session(request.session_id)
        greeting = await actor.get_greeting()
        return ChatResponse(
            response=greeting,
            session_id=request.session_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise handle_endpoint_error(e, f"chat_init session={request.session_id}")
```

**File:** `web_app.py:251-266` (chat endpoint)

```python
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Process a chat message and return the response."""
    try:
        actor = await get_or_create_session(request.session_id)
        response_text = await actor.process_message(request.message)
        return ChatResponse(
            response=response_text,
            session_id=request.session_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise handle_endpoint_error(e, f"chat session={request.session_id}")
```

### 4.4 Update get_or_create_session

**File:** `web_app.py:208-227`

```python
async def get_or_create_session(session_id: str) -> SessionActor:
    """Retrieves an existing session or spawns a new actor."""
    async with sessions_lock:
        if session_id in active_sessions:
            actor = active_sessions[session_id]
            if actor.is_running:
                return actor
            else:
                del active_sessions[session_id]
                logger.warning(f"Cleaned up dead session: {session_id}")

        logger.info(f"Initializing new session actor: {session_id}")

        # Check API key - return 503 Service Unavailable if not configured
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(
                status_code=503,
                detail="Service unavailable: API not configured"
            )

        actor = SessionActor(session_id)
        await actor.start()
        active_sessions[session_id] = actor
        return actor
```

---

## Part 5: HTTP Status Code Reference

### Status Codes Used

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Successful GET/POST/DELETE |
| 400 | Bad Request | Invalid session ID format |
| 404 | Not Found | Session/resource doesn't exist |
| 410 | Gone | Session was closed |
| 422 | Unprocessable Entity | Validation errors (Pydantic) |
| 500 | Internal Server Error | Unexpected server errors |
| 503 | Service Unavailable | API not configured |
| 504 | Gateway Timeout | Request timeout |

### Frontend Handling

**File:** `static/script.js`

Update error handling to differentiate status codes:
```javascript
async function sendMessage(message, showInUI = true) {
    // ... existing code ...

    try {
        const response = await fetch('/chat', { /* ... */ });

        // Handle specific status codes
        switch (response.status) {
            case 400:
                const badReq = await response.json();
                throw new Error(`Invalid request: ${badReq.detail}`);

            case 404:
                throw new Error('Session not found. Please refresh the page.');

            case 410:
                sessionStorage.removeItem('agent_session_id');
                throw new Error('Session expired. Please refresh to start a new session.');

            case 422:
                const validation = await response.json();
                const errorMsg = validation.errors?.map(e => e.message).join(', ') || 'Validation error';
                throw new Error(errorMsg);

            case 503:
                throw new Error('Service temporarily unavailable. Please try again later.');

            case 504:
                throw new Error('Request timed out. Try a shorter video or check your connection.');

            case 500:
            default:
                if (!response.ok) {
                    const error = await response.json().catch(() => ({}));
                    throw new Error(error.detail || 'An error occurred');
                }
        }

        // Success handling...
    } catch (error) {
        // Error display...
    }
}
```

---

## Part 6: Logging Improvements (Medium Priority)

### 6.1 Configure Logging Module

**File:** `web_app.py` (after imports)

```python
import logging
from logging.handlers import RotatingFileHandler

# Configure logging
def setup_logging():
    """Configure application logging."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # Optional: File handler for debugging
    # file_handler = RotatingFileHandler(
    #     'logs/app.log',
    #     maxBytes=10*1024*1024,  # 10MB
    #     backupCount=5
    # )
    # file_handler.setLevel(logging.DEBUG)
    # logger.addHandler(file_handler)

    return logger

logger = setup_logging()
```

### 6.2 Replace print() Statements

Find all `print()` statements and replace with appropriate log levels:

| Original | Replacement |
|----------|-------------|
| `print(f"Session started")` | `logger.info(f"Session started")` |
| `print(f"Error: {e}")` | `logger.error(f"Error: {e}", exc_info=True)` |
| `print(f"Warning: {msg}")` | `logger.warning(f"Warning: {msg}")` |
| Debug/trace info | `logger.debug(f"...")` |

### 6.3 Sensitive Data Protection

Never log:
- API keys or tokens
- Full exception stack traces to client responses
- User message content (unless in debug mode)
- Session IDs in error responses (use generic messages)

Example safe logging:
```python
# Good - logs useful context without exposing sensitive data
logger.info(f"Session {session_id[:8]}...: Worker started")
logger.error(f"Session {session_id[:8]}...: Error processing", exc_info=True)

# Bad - exposes full session ID and user data
logger.info(f"Session {session_id}: Processing message: {message}")
```

---

## Part 7: Code Quality Improvements (Low Priority)

### 7.1 Type Hint Improvements

**File:** `web_app.py`

Add missing type hints:
```python
from typing import Dict, Optional, Any

active_sessions: Dict[str, SessionActor] = {}
sessions_lock: asyncio.Lock = asyncio.Lock()
```

### 7.2 Docstring Updates

Add docstrings to all public functions:
```python
async def get_or_create_session(session_id: str) -> SessionActor:
    """
    Retrieve an existing session or create a new one.

    Args:
        session_id: UUID v4 identifier for the session

    Returns:
        SessionActor instance for the session

    Raises:
        HTTPException: 503 if API key not configured
    """
    # ... implementation ...
```

---

## Testing Checklist

### XSS Protection Tests (Frontend - Already Implemented)
- [x] `<script>alert(1)</script>` → sanitized
- [x] `<img onerror="alert(1)">` → sanitized
- [x] `<a href="javascript:...">` → href stripped
- [x] Valid markdown still renders correctly

### Input Validation Tests (Backend - Verified)
- [x] Empty message → 422 with validation error
- [x] Whitespace-only message → 422
- [x] Message > 50000 chars → 422 (field constraint added)
- [x] Invalid UUID format → 422 (Pydantic validation) / 400 (DELETE path param)
- [x] Valid UUID → accepted
- [x] Invalid UUID v4 pattern (not version 4) → 422

### Error Handling Tests (Backend - Verified)
- [x] Missing API key → 503 (implemented in get_or_create_session)
- [x] Session not found (DELETE) → 404
- [x] Timeout → 504 (implemented in handle_endpoint_error)
- [x] Closed session → 410 (implemented in handle_endpoint_error)
- [x] Server error → 500 with generic message

### Session Security Tests (Frontend - Already Implemented)
- [x] New tab gets new session ID
- [x] Session ID not in localStorage
- [x] Session cleared on reset

---

## Implementation Order

1. **DOMPurify** - Add CDN, configure sanitization
2. **sessionStorage** - Replace localStorage
3. **UUID validation** - Add pattern and validators
4. **Pydantic models** - Update with Field validators
5. **Error handler function** - Create handle_endpoint_error
6. **Exception handler** - Add RequestValidationError handler
7. **Endpoint updates** - Apply error handling to all endpoints
8. **DELETE endpoint** - Add validation and 404
9. **Logging** - Configure module, replace print()
10. **Frontend status handling** - Handle new status codes

---

## Security Considerations Summary

| Risk | Mitigation | Priority |
|------|------------|----------|
| XSS via markdown | DOMPurify sanitization | HIGH |
| Session fixation | sessionStorage instead of localStorage | HIGH |
| Invalid input | Pydantic validators with UUID pattern | HIGH |
| Information leakage | Generic error messages to client | MEDIUM |
| Unbounded input | max_length on message field | MEDIUM |
| Missing auth | Out of scope for local dev | LOW |
| Rate limiting | Out of scope for local dev | LOW |
