"""
API router modules.

This package contains FastAPI routers organized by feature area:
- chat: Chat session endpoints
- history: Session history management
- transcripts: Transcript file operations
- upload: Video file upload handling
- cost: Usage and cost tracking
- health: Health check for monitoring
- jobs: Job queue management
- audit: Agent hook-based audit logs
"""

from app.api.routers.audit import router as audit_router
from app.api.routers.chat import health_router
from app.api.routers.chat import router as chat_router
from app.api.routers.chat import status_router
from app.api.routers.cost import router as cost_router
from app.api.routers.history import router as history_router
from app.api.routers.jobs import router as jobs_router
from app.api.routers.transcripts import router as transcripts_router
from app.api.routers.upload import router as upload_router

__all__ = [
    "audit_router",
    "chat_router",
    "cost_router",
    "health_router",
    "history_router",
    "jobs_router",
    "status_router",
    "transcripts_router",
    "upload_router",
]
