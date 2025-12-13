"""
FastAPI application entry point.

Configures and creates the FastAPI application with:
- Service lifecycle management
- Exception handlers
- Router mounting
- Static file serving
"""

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Load environment variables first
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

# Apply filter to SDK logger to suppress benign exit code messages
from app.core.logging import ExitCodeFilter  # noqa: E402

logging.getLogger("claude_agent_sdk").addFilter(ExitCodeFilter())

# Import application components
from app.api.errors import register_exception_handlers  # noqa: E402
from app.api.routers import (  # noqa: E402
    chat_router,
    cost_router,
    history_router,
    status_router,
    transcripts_router,
    upload_router,
)
from app.services import services_lifespan  # noqa: E402
from app.ui.routes import router as ui_router  # noqa: E402

# Create FastAPI application with service lifecycle management
app = FastAPI(
    title="Agent Video to Data",
    description="AI-powered video transcription using Claude Agent SDK and OpenAI Whisper",
    version="1.0.0",
    lifespan=services_lifespan,
)

# Register exception handlers
register_exception_handlers(app)

# Mount static files
app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)

# Mount API routers
app.include_router(ui_router)
app.include_router(chat_router)
app.include_router(status_router)
app.include_router(history_router)
app.include_router(transcripts_router)
app.include_router(cost_router)
app.include_router(upload_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
