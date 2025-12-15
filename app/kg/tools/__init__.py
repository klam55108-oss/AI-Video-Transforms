"""
Knowledge Graph MCP tools.

This module provides MCP tools for:
- Bootstrap: Domain inference from transcript content
- Extraction: Entity and relationship extraction using DomainProfile

Exports:
    - create_bootstrap_mcp_server: Factory for bootstrap MCP server
    - BOOTSTRAP_TOOL_NAMES: List of bootstrap tool names for allowlisting
    - create_extraction_mcp_server: Factory for extraction MCP server
    - EXTRACTION_TOOL_NAMES: List of extraction tool names for allowlisting
"""

from app.kg.tools.bootstrap import (
    BOOTSTRAP_TOOL_NAMES,
    create_bootstrap_mcp_server,
)
from app.kg.tools.extraction import (
    EXTRACTION_TOOL_NAMES,
    create_extraction_mcp_server,
)

__all__ = [
    "create_bootstrap_mcp_server",
    "BOOTSTRAP_TOOL_NAMES",
    "create_extraction_mcp_server",
    "EXTRACTION_TOOL_NAMES",
]
