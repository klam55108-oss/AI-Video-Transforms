"""
API layer package.

Provides HTTP endpoint routing, error handling, and request/response models.
"""

from app.api.errors import handle_endpoint_error, register_exception_handlers

__all__ = ["handle_endpoint_error", "register_exception_handlers"]
