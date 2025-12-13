"""
UI routes for serving the web interface.

Provides endpoints for serving HTML templates and static assets.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Configure templates
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request) -> HTMLResponse:
    """
    Serve the main application interface.

    Args:
        request: The incoming HTTP request

    Returns:
        HTML response with the main application template
    """
    return templates.TemplateResponse(request, "index.html")
