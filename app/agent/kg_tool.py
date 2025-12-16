"""
Knowledge Graph MCP Tools for Claude Agent.

Provides tools for the agent to interact with the Knowledge Graph service,
including project management, bootstrapping, and entity/relationship extraction.

Tool Return Format (per Claude Agent SDK):
- Success: {"content": [{"type": "text", "text": "..."}]}
- Error: {"success": False, "error": "message"}
- NEVER raise exceptions that escape the tool function
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from claude_agent_sdk import tool

if TYPE_CHECKING:
    from app.services.kg_service import KnowledgeGraphService

# Module-level cache for fallback singleton.
# This exists because KG tools can be invoked in two contexts:
# 1. FastAPI request context (ServiceContainer is available)
# 2. MCP agent context during bootstrap/extraction (ServiceContainer may not be available)
# The singleton fallback ensures tools work in both contexts without code duplication.
# In production, FastAPI context should always be available, but we keep the fallback
# for robustness during development/testing and edge cases.
_kg_service_singleton: "KnowledgeGraphService | None" = None


def _get_kg_service() -> "KnowledgeGraphService":
    """
    Get KnowledgeGraphService instance with automatic context detection.

    Resolution order:
    1. Try FastAPI ServiceContainer (works in request context) - primary path
    2. Fall back to lazy-initialized singleton (works in MCP agent context)

    The singleton fallback is rarely used in production but provides safety
    when tools are invoked outside the normal request lifecycle.
    """
    global _kg_service_singleton

    # First, try FastAPI container (works during HTTP requests)
    try:
        from app.services import get_services

        return get_services().kg
    except RuntimeError:
        # Services not initialized - we're outside FastAPI context.
        # This can happen during:
        # - Unit tests without full app initialization
        # - Direct tool invocation from MCP server
        pass

    # Fallback: create singleton for edge cases
    if _kg_service_singleton is None:
        from pathlib import Path
        from app.services.kg_service import KnowledgeGraphService

        _kg_service_singleton = KnowledgeGraphService(data_path=Path("data"))

    return _kg_service_singleton


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 1: extract_to_kg
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(
    "extract_to_kg",
    "Extract entities and relationships from a transcript into a Knowledge Graph project. "
    "The project must exist and be bootstrapped (have a domain profile). "
    "Returns extraction statistics including entity/relationship counts.",
    {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "ID of the target Knowledge Graph project",
            },
            "transcript": {
                "type": "string",
                "description": "Full transcript text to extract entities and relationships from",
            },
            "title": {
                "type": "string",
                "description": "Title of the source content (video/audio name)",
            },
            "source_id": {
                "type": "string",
                "description": "Optional unique identifier for the source. Auto-generated if not provided.",
            },
        },
        "required": ["project_id", "transcript", "title"],
    },
)
async def extract_to_kg(args: dict[str, Any]) -> dict[str, Any]:
    """
    Extract entities and relationships from transcript into KG project.

    Validates that the project exists and has been bootstrapped before
    attempting extraction. Generates a source_id if not provided.

    Args:
        args: Tool arguments containing:
            - project_id: Target KG project ID
            - transcript: Full transcript text to extract from
            - title: Title of the source content
            - source_id: Optional unique identifier for the source

    Returns:
        MCP tool response with extraction statistics or error
    """
    try:
        project_id = args.get("project_id", "")
        transcript = args.get("transcript", "")
        title = args.get("title", "")
        source_id = args.get("source_id") or uuid4().hex[:8]

        if not project_id:
            return {"success": False, "error": "project_id is required"}
        if not transcript:
            return {"success": False, "error": "transcript is required"}
        if not title:
            return {"success": False, "error": "title is required"}

        kg_service = _get_kg_service()

        # Validate project exists
        project = await kg_service.get_project(project_id)
        if not project:
            return {"success": False, "error": f"Project '{project_id}' not found"}

        # Validate project is bootstrapped
        if not project.domain_profile:
            return {
                "success": False,
                "error": f"Project '{project_id}' has not been bootstrapped. "
                "Run bootstrap_kg_project first to create a domain profile.",
            }

        # Perform extraction
        result = await kg_service.extract_from_transcript(
            project_id=project_id,
            transcript=transcript,
            title=title,
            source_id=source_id,
        )

        # Format success response
        text = (
            f"## Extraction Complete\n\n"
            f"**Source:** {title} (ID: {source_id})\n"
            f"**Project:** {project.name}\n\n"
            f"### Statistics\n"
            f"- Entities extracted: {result['entities_extracted']}\n"
            f"- Relationships extracted: {result['relationships_extracted']}\n"
            f"- New discoveries: {result['discoveries']}\n"
        )

        if result.get("summary"):
            text += f"\n### Summary\n{result['summary']}\n"

        return {"content": [{"type": "text", "text": text}]}

    except Exception as e:
        return {"success": False, "error": f"Extraction failed: {e!s}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 2: list_kg_projects
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(
    "list_kg_projects",
    "List all Knowledge Graph projects with their status and statistics. "
    "Returns project ID, name, state, and counts of entities/relationships/sources.",
    {
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def list_kg_projects(args: dict[str, Any]) -> dict[str, Any]:
    """
    List all KG projects with stats.

    Returns formatted markdown showing each project's ID, name, status,
    and counts of things, connections, and sources.

    Args:
        args: Tool arguments (none required)

    Returns:
        MCP tool response with project listing or error
    """
    try:
        kg_service = _get_kg_service()
        projects = await kg_service.list_projects()

        if not projects:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "No Knowledge Graph projects found. "
                        "Use `create_kg_project` to create one.",
                    }
                ]
            }

        # Build markdown table
        lines = [
            "## Knowledge Graph Projects\n",
            "| ID | Name | Status | Things | Connections | Sources |",
            "|---|---|---|---|---|---|",
        ]

        for p in projects:
            status = p.state.value if hasattr(p.state, "value") else str(p.state)
            lines.append(
                f"| `{p.id}` | {p.name} | {status} | "
                f"{p.thing_count} | {p.connection_count} | {p.source_count} |"
            )

        lines.append(f"\n**Total projects:** {len(projects)}")

        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    except Exception as e:
        return {"success": False, "error": f"Failed to list projects: {e!s}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 3: create_kg_project
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(
    "create_kg_project",
    "Create a new Knowledge Graph project. "
    "Returns the project ID which is needed for bootstrap and extraction operations.",
    {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "minLength": 1,
                "maxLength": 200,
                "description": "Human-readable name for the project (e.g., 'MK-Ultra Research', 'AI Interviews')",
            },
        },
        "required": ["name"],
    },
)
async def create_kg_project(args: dict[str, Any]) -> dict[str, Any]:
    """
    Create a new KG project.

    The project starts in CREATED state and must be bootstrapped
    with a transcript before extraction can occur.

    Args:
        args: Tool arguments containing:
            - name: Human-readable project name

    Returns:
        MCP tool response with project ID or error
    """
    try:
        name = args.get("name", "").strip()

        if not name:
            return {"success": False, "error": "Project name is required"}

        kg_service = _get_kg_service()
        project = await kg_service.create_project(name)

        text = (
            f"## Project Created\n\n"
            f"**Name:** {project.name}\n"
            f"**ID:** `{project.id}`\n"
            f"**Status:** {project.state.value}\n\n"
            f"Next step: Use `bootstrap_kg_project` with the first transcript "
            f"to create a domain profile for this project."
        )

        return {"content": [{"type": "text", "text": text}]}

    except Exception as e:
        return {"success": False, "error": f"Failed to create project: {e!s}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 4: bootstrap_kg_project
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(
    "bootstrap_kg_project",
    "Bootstrap a Knowledge Graph project from the first transcript. "
    "Analyzes content to infer entity types, relationship types, and seed entities. "
    "Must be called once before extraction. Fails if project is already bootstrapped.",
    {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "ID of the target Knowledge Graph project to bootstrap",
            },
            "transcript": {
                "type": "string",
                "description": "First transcript to analyze for domain inference",
            },
            "title": {
                "type": "string",
                "description": "Title of the source content for reference",
            },
        },
        "required": ["project_id", "transcript", "title"],
    },
)
async def bootstrap_kg_project(args: dict[str, Any]) -> dict[str, Any]:
    """
    Bootstrap project domain profile from first transcript.

    Runs Claude to analyze the transcript and infer:
    - Entity types (ThingTypes) relevant to the domain
    - Relationship types (ConnectionTypes) between entities
    - Seed entities as examples
    - Extraction context for future extractions

    Args:
        args: Tool arguments containing:
            - project_id: Target project ID
            - transcript: First transcript to analyze
            - title: Title of the source content

    Returns:
        MCP tool response with detected types or error
    """
    try:
        project_id = args.get("project_id", "")
        transcript = args.get("transcript", "")
        title = args.get("title", "")

        if not project_id:
            return {"success": False, "error": "project_id is required"}
        if not transcript:
            return {"success": False, "error": "transcript is required"}
        if not title:
            return {"success": False, "error": "title is required"}

        kg_service = _get_kg_service()

        # Validate project exists
        project = await kg_service.get_project(project_id)
        if not project:
            return {"success": False, "error": f"Project '{project_id}' not found"}

        # Check if already bootstrapped
        if project.domain_profile:
            return {
                "success": False,
                "error": f"Project '{project_id}' is already bootstrapped. "
                "Use `extract_to_kg` to add more content.",
            }

        # Generate source_id for bootstrap video
        source_id = uuid4().hex[:8]

        # Run bootstrap
        profile = await kg_service.bootstrap_from_transcript(
            project_id=project_id,
            transcript=transcript,
            title=title,
            source_id=source_id,
        )

        # Format entity types
        thing_types_text = "\n".join(
            f"- **{t.name}**: {t.description}" for t in profile.thing_types
        )

        # Format relationship types
        connection_types_text = "\n".join(
            f"- **{c.name}** ({c.display_name}): {c.description}"
            for c in profile.connection_types
        )

        # Format seed entities
        seed_entities_text = "\n".join(
            f"- {e.label} ({e.thing_type})" for e in profile.seed_entities[:10]
        )
        if len(profile.seed_entities) > 10:
            seed_entities_text += f"\n- ... and {len(profile.seed_entities) - 10} more"

        text = (
            f"## Bootstrap Complete\n\n"
            f"**Project:** {project.name}\n"
            f"**Source:** {title}\n"
            f"**Confidence:** {profile.bootstrap_confidence:.0%}\n\n"
            f"### Entity Types Detected ({len(profile.thing_types)})\n"
            f"{thing_types_text}\n\n"
            f"### Relationship Types Detected ({len(profile.connection_types)})\n"
            f"{connection_types_text}\n\n"
            f"### Seed Entities ({len(profile.seed_entities)})\n"
            f"{seed_entities_text}\n\n"
            f"The project is now ready for extraction. "
            f"Use `extract_to_kg` to process additional transcripts."
        )

        return {"content": [{"type": "text", "text": text}]}

    except Exception as e:
        return {"success": False, "error": f"Bootstrap failed: {e!s}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 5: get_kg_stats
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(
    "get_kg_stats",
    "Get detailed statistics for a Knowledge Graph project. "
    "Returns counts by entity type and relationship type.",
    {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "ID of the Knowledge Graph project to get statistics for",
            },
        },
        "required": ["project_id"],
    },
)
async def get_kg_stats(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get graph statistics for a project.

    Returns detailed breakdowns of nodes by entity type and
    edges by relationship type.

    Args:
        args: Tool arguments containing:
            - project_id: Target project ID

    Returns:
        MCP tool response with statistics or error
    """
    try:
        project_id = args.get("project_id", "")

        if not project_id:
            return {"success": False, "error": "project_id is required"}

        kg_service = _get_kg_service()

        # Validate project exists
        project = await kg_service.get_project(project_id)
        if not project:
            return {"success": False, "error": f"Project '{project_id}' not found"}

        # Get stats
        stats = await kg_service.get_graph_stats(project_id)

        if not stats:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"## Statistics for {project.name}\n\n"
                        f"No graph data yet. The project needs to be bootstrapped "
                        f"and have content extracted first.",
                    }
                ]
            }

        # Format node types
        node_by_type_text = ""
        if stats.get("nodes_by_type"):
            node_by_type_text = "\n".join(
                f"- {t}: {c}" for t, c in stats["nodes_by_type"].items()
            )
        else:
            node_by_type_text = "No nodes yet"

        # Format edge types
        edge_by_type_text = ""
        if stats.get("edges_by_type"):
            edge_by_type_text = "\n".join(
                f"- {t}: {c}" for t, c in stats["edges_by_type"].items()
            )
        else:
            edge_by_type_text = "No edges yet"

        text = (
            f"## Statistics for {project.name}\n\n"
            f"### Overview\n"
            f"- **Total Nodes:** {stats.get('node_count', 0)}\n"
            f"- **Total Edges:** {stats.get('edge_count', 0)}\n"
            f"- **Sources:** {stats.get('source_count', 0)}\n\n"
            f"### Nodes by Type\n{node_by_type_text}\n\n"
            f"### Edges by Type\n{edge_by_type_text}"
        )

        return {"content": [{"type": "text", "text": text}]}

    except Exception as e:
        return {"success": False, "error": f"Failed to get stats: {e!s}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EXPORTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

KG_TOOLS = [
    extract_to_kg,
    list_kg_projects,
    create_kg_project,
    bootstrap_kg_project,
    get_kg_stats,
]
