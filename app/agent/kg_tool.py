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

from typing import TYPE_CHECKING, Any, TypedDict
from uuid import uuid4

from claude_agent_sdk import tool

if TYPE_CHECKING:
    from app.kg.knowledge_base import KnowledgeBase
    from app.services.kg_service import KnowledgeGraphService


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TypedDict Return Types for MCP Tool Handlers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class MCPTextContent(TypedDict):
    """A single text content item in MCP response."""

    type: str  # Always "text"
    text: str


class MCPToolSuccess(TypedDict):
    """Successful MCP tool response with content array."""

    content: list[MCPTextContent]


class MCPToolError(TypedDict):
    """Error MCP tool response with success=False flag."""

    success: bool  # Always False
    error: str


# Union type for handler return values
MCPToolResponse = MCPToolSuccess | MCPToolError

# Maximum entity name length for input validation (security)
MAX_ENTITY_NAME_LENGTH = 500


def _validate_entity_name(name: str, param_name: str) -> dict[str, Any] | None:
    """Validate entity name length. Returns error dict if invalid, None if valid."""
    if name and len(name) > MAX_ENTITY_NAME_LENGTH:
        return {
            "success": False,
            "error": f"{param_name} exceeds maximum length ({MAX_ENTITY_NAME_LENGTH} chars)",
        }
    return None


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
            "transcript_id": {
                "type": "string",
                "description": "ID of the saved transcript (from save_transcript). "
                "Recommended for evidence linking. If not provided, auto-detection by title is attempted.",
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
        transcript_id = args.get("transcript_id")

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
            transcript_id=transcript_id,
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
# TOOL 6: ask_about_graph
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(
    "ask_about_graph",
    "Query the Knowledge Graph for insights. Supports multiple question types: "
    "key_entities (find important entities), connection (how two entities connect), "
    "common_ground (shared connections), groups (discover clusters), "
    "isolated (find disconnected groups), mentions (where entity appears), "
    "evidence (quotes for relationships), suggestions (what to explore next).",
    {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "ID of the Knowledge Graph project to query",
            },
            "question_type": {
                "type": "string",
                "enum": [
                    "key_entities",
                    "connection",
                    "common_ground",
                    "groups",
                    "isolated",
                    "mentions",
                    "evidence",
                    "suggestions",
                ],
                "description": "Type of insight query to perform",
            },
            "entity_1": {
                "type": "string",
                "description": "First entity name (for connection, common_ground, evidence, mentions)",
            },
            "entity_2": {
                "type": "string",
                "description": "Second entity name (for connection, common_ground, evidence)",
            },
            "method": {
                "type": "string",
                "enum": ["connections", "influence", "bridging"],
                "description": "Ranking method for key_entities (default: connections)",
            },
            "entity_type": {
                "type": "string",
                "description": "Filter by entity type (for key_entities)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results to return (default: 10)",
            },
        },
        "required": ["project_id", "question_type"],
    },
)
async def ask_about_graph(args: dict[str, Any]) -> dict[str, Any]:
    """
    Unified query interface for graph insights.

    Routes to the appropriate KnowledgeBase insight method based on
    question_type and formats the response for the agent.

    Args:
        args: Tool arguments containing:
            - project_id: Target KG project ID
            - question_type: Type of query to perform
            - entity_1, entity_2: Entity names for relationship queries
            - method: Ranking method for key_entities
            - entity_type: Filter for key_entities
            - limit: Max results

    Returns:
        MCP tool response with insights or error
    """
    try:
        project_id = args.get("project_id", "")
        question_type = args.get("question_type", "")

        if not project_id:
            return {"success": False, "error": "project_id is required"}
        if not question_type:
            return {"success": False, "error": "question_type is required"}

        kg_service = _get_kg_service()

        # Validate project exists
        project = await kg_service.get_project(project_id)
        if not project:
            return {"success": False, "error": f"Project '{project_id}' not found"}

        # Get the knowledge base
        kb = await kg_service.get_knowledge_base(project_id)
        if not kb:
            return {
                "success": False,
                "error": f"Project '{project_id}' has no knowledge base. "
                "Bootstrap and extract content first.",
            }

        # Route to appropriate query (handlers are synchronous)
        if question_type == "key_entities":
            return _handle_key_entities(kb, args, project.name)

        elif question_type == "connection":
            return _handle_connection(kb, args)

        elif question_type == "common_ground":
            return _handle_common_ground(kb, args)

        elif question_type == "groups":
            return _handle_groups(kb, project.name)

        elif question_type == "isolated":
            return _handle_isolated(kb, project.name)

        elif question_type == "mentions":
            return _handle_mentions(kb, args)

        elif question_type == "evidence":
            return _handle_evidence(kb, args)

        elif question_type == "suggestions":
            return _handle_suggestions(kb, project.name)

        else:
            return {
                "success": False,
                "error": f"Unknown question_type: {question_type}. "
                "Valid types: key_entities, connection, common_ground, groups, "
                "isolated, mentions, evidence, suggestions",
            }

    except Exception as e:
        return {"success": False, "error": f"Graph query failed: {e!s}"}


def _handle_key_entities(
    kb: "KnowledgeBase",
    args: dict[str, Any],
    project_name: str,
) -> dict[str, Any]:
    """Handle key_entities query type."""
    method = args.get("method", "connections")
    entity_type = args.get("entity_type")
    limit = args.get("limit", 10)

    results = kb.get_key_entities(limit=limit, method=method, entity_type=entity_type)

    if not results:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"## Key Entities in {project_name}\n\nNo entities found in the graph.",
                }
            ]
        }

    method_labels = {
        "connections": "Most Connected",
        "influence": "Most Influential",
        "bridging": "Key Bridges",
    }
    method_label = method_labels.get(method, "Key")

    lines = [
        f"## {method_label} Entities in {project_name}\n",
        "| Rank | Entity | Type | Score | Why |",
        "|------|--------|------|-------|-----|",
    ]

    for i, entity in enumerate(results, 1):
        score_display = (
            f"{entity['score']:.2%}" if method != "connections" else str(int(entity["score"]))
        )
        lines.append(
            f"| {i} | {entity['label']} | {entity['entity_type']} | "
            f"{score_display} | {entity['why']} |"
        )

    if entity_type:
        lines.append(f"\n*Filtered to {entity_type} entities*")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def _handle_connection(
    kb: "KnowledgeBase",
    args: dict[str, Any],
) -> dict[str, Any]:
    """Handle connection query type."""
    entity_1 = args.get("entity_1", "")
    entity_2 = args.get("entity_2", "")

    if not entity_1 or not entity_2:
        return {
            "success": False,
            "error": "Both entity_1 and entity_2 are required for connection queries",
        }

    # Validate entity name lengths
    if error := _validate_entity_name(entity_1, "entity_1"):
        return error
    if error := _validate_entity_name(entity_2, "entity_2"):
        return error

    result = kb.find_connection(entity_1, entity_2)

    if not result["connected"]:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"## Connection: {entity_1} to {entity_2}\n\n"
                    f"**Not connected:** {result['explanation']}",
                }
            ]
        }

    # Build path description
    path_lines = []
    for i, step in enumerate(result["path"]):
        if step["relationship"]:
            arrow = "->" if step["direction"] == "outgoing" else "<-"
            path_lines.append(f"  {step['entity']} {arrow} ({step['relationship']})")
        else:
            path_lines.append(f"  {step['entity']}")

    path_text = "\n".join(path_lines)

    text = (
        f"## Connection: {entity_1} to {entity_2}\n\n"
        f"**Connected:** Yes ({result['explanation']})\n\n"
        f"### Path\n```\n{path_text}\n```"
    )

    return {"content": [{"type": "text", "text": text}]}


def _handle_common_ground(
    kb: "KnowledgeBase",
    args: dict[str, Any],
) -> dict[str, Any]:
    """Handle common_ground query type."""
    entity_1 = args.get("entity_1", "")
    entity_2 = args.get("entity_2", "")

    if not entity_1 or not entity_2:
        return {
            "success": False,
            "error": "Both entity_1 and entity_2 are required for common_ground queries",
        }

    # Validate entity name lengths
    if error := _validate_entity_name(entity_1, "entity_1"):
        return error
    if error := _validate_entity_name(entity_2, "entity_2"):
        return error

    results = kb.find_common_ground(entity_1, entity_2)

    if not results:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"## Common Ground: {entity_1} & {entity_2}\n\n"
                    f"No shared connections found between {entity_1} and {entity_2}.",
                }
            ]
        }

    lines = [
        f"## Common Ground: {entity_1} & {entity_2}\n",
        f"Found {len(results)} shared connection(s):\n",
    ]

    for common in results:
        lines.append(f"### {common['entity']} ({common['entity_type']})")
        lines.append(f"- {entity_1}: {common['connection_to_first']}")
        lines.append(f"- {entity_2}: {common['connection_to_second']}")
        lines.append("")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def _handle_groups(kb: "KnowledgeBase", project_name: str) -> dict[str, Any]:
    """Handle groups query type."""
    results = kb.discover_groups()

    if not results:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"## Groups in {project_name}\n\n"
                    f"No distinct groups detected. The graph may be too small or "
                    f"highly connected.",
                }
            ]
        }

    lines = [
        f"## Groups in {project_name}\n",
        f"Detected {len(results)} cluster(s):\n",
    ]

    for i, group in enumerate(results, 1):
        sample_text = ", ".join(group["sample"])
        if group["size"] > 5:
            sample_text += f", ... (+{group['size'] - 5} more)"

        lines.append(f"### {i}. {group['name']}")
        lines.append(f"**Size:** {group['size']} entities")
        lines.append(f"**Members:** {sample_text}")
        lines.append("")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def _handle_isolated(kb: "KnowledgeBase", project_name: str) -> dict[str, Any]:
    """Handle isolated query type."""
    results = kb.find_isolated_topics()

    if not results:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"## Isolated Topics in {project_name}\n\n"
                    f"No isolated groups found. All entities are connected to the main graph.",
                }
            ]
        }

    lines = [
        f"## Isolated Topics in {project_name}\n",
        f"Found {len(results)} disconnected group(s):\n",
    ]

    for i, group in enumerate(results, 1):
        sample_text = ", ".join(group["sample"])
        if group["size"] > 5:
            sample_text += f", ... (+{group['size'] - 5} more)"

        lines.append(f"### Group {i}")
        lines.append(f"**Size:** {group['size']} entities")
        lines.append(f"**Entities:** {sample_text}")
        lines.append(f"*{group['explanation']}*")
        lines.append("")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def _handle_mentions(
    kb: "KnowledgeBase",
    args: dict[str, Any],
) -> dict[str, Any]:
    """Handle mentions query type."""
    entity = args.get("entity_1", "")

    if not entity:
        return {
            "success": False,
            "error": "entity_1 is required for mentions queries",
        }

    # Validate entity name length
    if error := _validate_entity_name(entity, "entity_1"):
        return error

    results = kb.get_mentions(entity)

    if not results:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"## Mentions of {entity}\n\n"
                    f"No source mentions found for '{entity}'. "
                    f"The entity may not exist or have no tracked sources.",
                }
            ]
        }

    lines = [
        f"## Mentions of {entity}\n",
        f"Found in {len(results)} source(s):\n",
        "| Source | Type |",
        "|--------|------|",
    ]

    for mention in results:
        lines.append(f"| {mention['source_title']} | {mention['source_type']} |")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def _handle_evidence(
    kb: "KnowledgeBase",
    args: dict[str, Any],
) -> dict[str, Any]:
    """Handle evidence query type."""
    entity_1 = args.get("entity_1", "")
    entity_2 = args.get("entity_2", "")

    if not entity_1 or not entity_2:
        return {
            "success": False,
            "error": "Both entity_1 and entity_2 are required for evidence queries",
        }

    # Validate entity name lengths
    if error := _validate_entity_name(entity_1, "entity_1"):
        return error
    if error := _validate_entity_name(entity_2, "entity_2"):
        return error

    results = kb.get_evidence(entity_1, entity_2)

    if not results:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"## Evidence: {entity_1} & {entity_2}\n\n"
                    f"No evidence found for relationships between these entities.",
                }
            ]
        }

    lines = [
        f"## Evidence: {entity_1} & {entity_2}\n",
        f"Found {len(results)} piece(s) of evidence:\n",
    ]

    for evidence in results:
        lines.append(f"### {evidence['relationship_type']}")
        lines.append(f"**Source:** {evidence['source_title']}")
        lines.append(f"**Confidence:** {evidence['confidence']:.0%}")
        if evidence["quote"]:
            lines.append(f'**Quote:** "{evidence["quote"]}"')
        else:
            lines.append("*No quote available*")
        lines.append("")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def _handle_suggestions(kb: "KnowledgeBase", project_name: str) -> dict[str, Any]:
    """Handle suggestions query type."""
    results = kb.get_smart_suggestions()

    if not results:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"## Suggestions for {project_name}\n\n"
                    f"No suggestions available. Try adding more content to the graph.",
                }
            ]
        }

    lines = [
        f"## Exploration Suggestions for {project_name}\n",
    ]

    priority_icons = {"high": "[!]", "medium": "[*]", "low": "[-]"}

    for suggestion in results:
        icon = priority_icons.get(suggestion["priority"], "[-]")
        lines.append(f"### {icon} {suggestion['question']}")
        lines.append(f"*{suggestion['why']}*")
        lines.append(f"**Action:** `{suggestion['action']}`")
        lines.append("")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 7: find_duplicate_entities
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(
    "find_duplicate_entities",
    "Find potential duplicate entities in a Knowledge Graph project. "
    "Uses string similarity, alias overlap, type matching, and graph context "
    "to identify entities that may refer to the same real-world thing.",
    {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "ID of the Knowledge Graph project to scan for duplicates",
            },
            "min_confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Minimum confidence threshold (0.0-1.0, default 0.7)",
            },
        },
        "required": ["project_id"],
    },
)
async def find_duplicate_entities(args: dict[str, Any]) -> dict[str, Any]:
    """
    Find potential duplicate entities in a KG project.

    Scans all nodes using the EntityMatcher algorithm which considers:
    - String similarity (Jaro-Winkler on labels)
    - Alias overlap (Jaccard similarity)
    - Type matching (same entity type bonus)
    - Graph context (shared neighbors)

    Args:
        args: Tool arguments containing:
            - project_id: Target KG project ID
            - min_confidence: Optional minimum confidence threshold (default 0.7)

    Returns:
        MCP tool response with candidate list or error
    """
    try:
        project_id = args.get("project_id", "")
        min_confidence = args.get("min_confidence", 0.7)

        if not project_id:
            return {"success": False, "error": "project_id is required"}

        # Validate min_confidence range
        if not 0.0 <= min_confidence <= 1.0:
            return {
                "success": False,
                "error": "min_confidence must be between 0.0 and 1.0",
            }

        kg_service = _get_kg_service()

        # Validate project exists
        project = await kg_service.get_project(project_id)
        if not project:
            return {"success": False, "error": f"Project '{project_id}' not found"}

        # Get knowledge base
        kb = await kg_service.get_knowledge_base(project_id)
        if not kb:
            return {
                "success": False,
                "error": f"Project '{project_id}' has no knowledge base. "
                "Bootstrap and extract content first.",
            }

        # Import resolution config and find candidates
        from app.kg.resolution import ResolutionConfig

        config = ResolutionConfig(review_threshold=min_confidence)
        candidates = kb.find_resolution_candidates(config)

        if not candidates:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"## Duplicate Scan Results\n\n"
                        f"No potential duplicates found in **{project.name}** "
                        f"above {min_confidence:.0%} confidence threshold.\n\n"
                        f"The graph has {len(kb._nodes)} unique entities.",
                    }
                ]
            }

        # Build formatted response
        lines = [
            "## Duplicate Scan Results\n",
            f"Found **{len(candidates)}** potential duplicate(s) in **{project.name}**:\n",
            "| Confidence | Entity A | Entity B | Signals |",
            "|------------|----------|----------|---------|",
        ]

        for candidate in candidates[:20]:  # Limit to top 20
            node_a = kb.get_node(candidate.node_a_id)
            node_b = kb.get_node(candidate.node_b_id)

            if not node_a or not node_b:
                continue

            # Format key signals
            signals = candidate.signals
            signal_parts = []
            if signals.get("string_sim", 0) > 0.5:
                signal_parts.append(f"name:{signals['string_sim']:.0%}")
            if signals.get("alias_sim", 0) > 0:
                signal_parts.append(f"alias:{signals['alias_sim']:.0%}")
            if signals.get("type_sim", 0) > 0:
                signal_parts.append("same-type")
            if signals.get("graph_sim", 0) > 0:
                signal_parts.append(f"neighbors:{signals['graph_sim']:.0%}")

            signal_str = ", ".join(signal_parts) if signal_parts else "low signals"

            lines.append(
                f"| {candidate.confidence:.0%} | "
                f"{node_a.label} ({node_a.entity_type}) | "
                f"{node_b.label} ({node_b.entity_type}) | "
                f"{signal_str} |"
            )

        if len(candidates) > 20:
            lines.append(f"\n*... and {len(candidates) - 20} more candidates*")

        # Add action guidance
        lines.append("\n### Next Steps")
        lines.append("- **High confidence (90%+)**: Consider auto-merging")
        lines.append("- **Medium confidence (70-90%)**: Review and confirm")
        lines.append("- **Low confidence (<70%)**: May be false positives")

        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    except Exception as e:
        return {"success": False, "error": f"Duplicate scan failed: {e!s}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 8: merge_entities_tool
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(
    "merge_entities_tool",
    "Merge two entities into one. The survivor entity keeps its label and absorbs "
    "the merged entity's aliases, relationships, and properties. "
    "Use for confirmed duplicates.",
    {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "ID of the Knowledge Graph project",
            },
            "survivor_id": {
                "type": "string",
                "description": "ID of the entity to keep (the survivor)",
            },
            "merged_id": {
                "type": "string",
                "description": "ID of the entity to merge into the survivor (will be removed)",
            },
        },
        "required": ["project_id", "survivor_id", "merged_id"],
    },
)
async def merge_entities_tool(args: dict[str, Any]) -> dict[str, Any]:
    """
    Merge two entities into one.

    The survivor entity keeps its primary label and absorbs:
    - Merged entity's label as an alias
    - All aliases from merged entity
    - All relationships (edges redirected to survivor)
    - Properties (survivor wins on conflict)
    - Source IDs (combined provenance)

    Args:
        args: Tool arguments containing:
            - project_id: Target KG project ID
            - survivor_id: ID of the node to keep
            - merged_id: ID of the node to merge in

    Returns:
        MCP tool response with merge confirmation or error
    """
    try:
        project_id = args.get("project_id", "")
        survivor_id = args.get("survivor_id", "")
        merged_id = args.get("merged_id", "")

        if not project_id:
            return {"success": False, "error": "project_id is required"}
        if not survivor_id:
            return {"success": False, "error": "survivor_id is required"}
        if not merged_id:
            return {"success": False, "error": "merged_id is required"}

        if survivor_id == merged_id:
            return {"success": False, "error": "Cannot merge an entity with itself"}

        kg_service = _get_kg_service()

        # Validate project exists
        project = await kg_service.get_project(project_id)
        if not project:
            return {"success": False, "error": f"Project '{project_id}' not found"}

        # Get knowledge base
        kb = await kg_service.get_knowledge_base(project_id)
        if not kb:
            return {
                "success": False,
                "error": f"Project '{project_id}' has no knowledge base.",
            }

        # Get nodes before merge for reporting
        survivor = kb.get_node(survivor_id)
        merged = kb.get_node(merged_id)

        if not survivor:
            return {
                "success": False,
                "error": f"Survivor entity '{survivor_id}' not found",
            }
        if not merged:
            return {"success": False, "error": f"Merged entity '{merged_id}' not found"}

        # Perform the merge
        history = kb.merge_nodes(
            survivor_id=survivor_id,
            merged_id=merged_id,
            merge_type="agent",
        )

        # Save updated KB
        from app.kg.persistence import save_knowledge_base

        save_knowledge_base(kb, kg_service.kb_path)

        # Update project stats and add to merge history
        project.thing_count = len(kb._nodes)
        project.connection_count = len(kb._edges)
        project.merge_history.append(history)
        await kg_service._save_project(project)

        text = (
            f"## Merge Complete\n\n"
            f"**Merged:** {merged.label} -> {survivor.label}\n\n"
            f"### Changes\n"
            f"- Added alias: '{history.merged_label}'\n"
            f"- New aliases: {len(history.merged_aliases)}\n"
            f"- Relationships redirected to survivor\n\n"
            f"**{survivor.label}** now represents both entities."
        )

        return {"content": [{"type": "text", "text": text}]}

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Merge failed: {e!s}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 9: review_pending_merges
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(
    "review_pending_merges",
    "Get pending merge candidates awaiting user review. "
    "Shows entity pairs with confidence scores for approval or rejection.",
    {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "ID of the Knowledge Graph project",
            },
        },
        "required": ["project_id"],
    },
)
async def review_pending_merges(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get pending merge candidates for review.

    Returns the list of resolution candidates stored in the project
    that are awaiting user confirmation.

    Args:
        args: Tool arguments containing:
            - project_id: Target KG project ID

    Returns:
        MCP tool response with pending candidates or error
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

        # Get knowledge base for node details
        kb = await kg_service.get_knowledge_base(project_id)

        # Filter for pending candidates only
        pending = [c for c in project.pending_merges if c.status == "pending"]

        if not pending:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"## Pending Merges\n\n"
                        f"No pending merge candidates for **{project.name}**.\n\n"
                        f"Use `find_duplicate_entities` to scan for potential duplicates.",
                    }
                ]
            }

        lines = [
            f"## Pending Merges for {project.name}\n",
            f"Found **{len(pending)}** candidate(s) awaiting review:\n",
        ]

        for i, candidate in enumerate(pending, 1):
            node_a = kb.get_node(candidate.node_a_id) if kb else None
            node_b = kb.get_node(candidate.node_b_id) if kb else None

            label_a = node_a.label if node_a else candidate.node_a_id
            label_b = node_b.label if node_b else candidate.node_b_id
            type_a = node_a.entity_type if node_a else "unknown"
            type_b = node_b.entity_type if node_b else "unknown"

            lines.append(f"### {i}. {label_a} <-> {label_b}")
            lines.append(f"- **Confidence:** {candidate.confidence:.0%}")
            lines.append(f"- **Types:** {type_a} / {type_b}")
            lines.append(f"- **Candidate ID:** `{candidate.id}`")

            # Show key signals
            if candidate.signals:
                signal_parts = []
                for key, value in candidate.signals.items():
                    if value > 0:
                        signal_parts.append(f"{key}: {value:.0%}")
                if signal_parts:
                    lines.append(f"- **Signals:** {', '.join(signal_parts)}")

            lines.append("")

        lines.append("### Actions")
        lines.append("- Use `approve_merge` with the candidate ID to confirm")
        lines.append("- Use `reject_merge` with the candidate ID to reject")

        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    except Exception as e:
        return {"success": False, "error": f"Failed to get pending merges: {e!s}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 10: approve_merge
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(
    "approve_merge",
    "Approve a pending merge candidate. The two entities will be merged, "
    "with the first entity (node_a) becoming the survivor.",
    {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "ID of the Knowledge Graph project",
            },
            "candidate_id": {
                "type": "string",
                "description": "ID of the pending merge candidate to approve",
            },
        },
        "required": ["project_id", "candidate_id"],
    },
)
async def approve_merge(args: dict[str, Any]) -> dict[str, Any]:
    """
    Approve a pending merge candidate.

    Finds the candidate by ID, executes the merge (node_a survives),
    and removes the candidate from the pending list.

    Args:
        args: Tool arguments containing:
            - project_id: Target KG project ID
            - candidate_id: ID of the candidate to approve

    Returns:
        MCP tool response with merge confirmation or error
    """
    try:
        project_id = args.get("project_id", "")
        candidate_id = args.get("candidate_id", "")

        if not project_id:
            return {"success": False, "error": "project_id is required"}
        if not candidate_id:
            return {"success": False, "error": "candidate_id is required"}

        kg_service = _get_kg_service()

        # Validate project exists
        project = await kg_service.get_project(project_id)
        if not project:
            return {"success": False, "error": f"Project '{project_id}' not found"}

        # Find the candidate
        candidate = None
        candidate_idx = -1
        for idx, c in enumerate(project.pending_merges):
            if c.id == candidate_id:
                candidate = c
                candidate_idx = idx
                break

        if not candidate:
            return {
                "success": False,
                "error": f"Candidate '{candidate_id}' not found in pending merges",
            }

        if candidate.status != "pending":
            return {
                "success": False,
                "error": f"Candidate '{candidate_id}' is not pending (status: {candidate.status})",
            }

        # Get knowledge base
        kb = await kg_service.get_knowledge_base(project_id)
        if not kb:
            return {
                "success": False,
                "error": f"Project '{project_id}' has no knowledge base.",
            }

        # Get node labels for response
        node_a = kb.get_node(candidate.node_a_id)
        node_b = kb.get_node(candidate.node_b_id)

        if not node_a or not node_b:
            # Remove invalid candidate
            project.pending_merges.pop(candidate_idx)
            await kg_service._save_project(project)
            return {
                "success": False,
                "error": "One or both entities no longer exist. Candidate removed.",
            }

        # Perform the merge (node_a is the survivor)
        history = kb.merge_nodes(
            survivor_id=candidate.node_a_id,
            merged_id=candidate.node_b_id,
            merge_type="user",
        )
        history.confidence = candidate.confidence

        # Save KB
        from app.kg.persistence import save_knowledge_base

        save_knowledge_base(kb, kg_service.kb_path)

        # Update project: remove candidate, add to history, update stats
        project.pending_merges.pop(candidate_idx)
        project.merge_history.append(history)
        project.thing_count = len(kb._nodes)
        project.connection_count = len(kb._edges)
        await kg_service._save_project(project)

        text = (
            f"## Merge Approved\n\n"
            f"**{node_b.label}** merged into **{node_a.label}** "
            f"(confidence: {candidate.confidence:.0%})\n\n"
            f"- Added alias: '{history.merged_label}'\n"
            f"- Relationships and properties transferred\n\n"
            f"Remaining pending: {len(project.pending_merges)}"
        )

        return {"content": [{"type": "text", "text": text}]}

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Approve failed: {e!s}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 11: reject_merge
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(
    "reject_merge",
    "Reject a pending merge candidate. The two entities will remain separate.",
    {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "ID of the Knowledge Graph project",
            },
            "candidate_id": {
                "type": "string",
                "description": "ID of the pending merge candidate to reject",
            },
        },
        "required": ["project_id", "candidate_id"],
    },
)
async def reject_merge(args: dict[str, Any]) -> dict[str, Any]:
    """
    Reject a pending merge candidate.

    Marks the candidate as rejected and removes it from the pending list.
    The two entities remain separate.

    Args:
        args: Tool arguments containing:
            - project_id: Target KG project ID
            - candidate_id: ID of the candidate to reject

    Returns:
        MCP tool response with rejection confirmation or error
    """
    try:
        project_id = args.get("project_id", "")
        candidate_id = args.get("candidate_id", "")

        if not project_id:
            return {"success": False, "error": "project_id is required"}
        if not candidate_id:
            return {"success": False, "error": "candidate_id is required"}

        kg_service = _get_kg_service()

        # Validate project exists
        project = await kg_service.get_project(project_id)
        if not project:
            return {"success": False, "error": f"Project '{project_id}' not found"}

        # Find and remove the candidate
        candidate = None
        candidate_idx = -1
        for idx, c in enumerate(project.pending_merges):
            if c.id == candidate_id:
                candidate = c
                candidate_idx = idx
                break

        if not candidate:
            return {
                "success": False,
                "error": f"Candidate '{candidate_id}' not found in pending merges",
            }

        # Get node labels for response (optional, for better messaging)
        kb = await kg_service.get_knowledge_base(project_id)
        node_a_label = candidate.node_a_id
        node_b_label = candidate.node_b_id

        if kb:
            node_a = kb.get_node(candidate.node_a_id)
            node_b = kb.get_node(candidate.node_b_id)
            if node_a:
                node_a_label = node_a.label
            if node_b:
                node_b_label = node_b.label

        # Mark as rejected and remove from pending
        candidate.status = "rejected"
        project.pending_merges.pop(candidate_idx)
        await kg_service._save_project(project)

        text = (
            f"## Merge Rejected\n\n"
            f"**{node_a_label}** and **{node_b_label}** will remain separate entities.\n\n"
            f"Remaining pending: {len(project.pending_merges)}"
        )

        return {"content": [{"type": "text", "text": text}]}

    except Exception as e:
        return {"success": False, "error": f"Reject failed: {e!s}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 12: compare_entities_semantic
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(
    "compare_entities_semantic",
    "Compare two entities for semantic similarity. Shows detailed breakdown "
    "of string similarity, alias overlap, type matching, and shared connections.",
    {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "ID of the Knowledge Graph project",
            },
            "node_a_id": {
                "type": "string",
                "description": "ID of the first entity to compare",
            },
            "node_b_id": {
                "type": "string",
                "description": "ID of the second entity to compare",
            },
        },
        "required": ["project_id", "node_a_id", "node_b_id"],
    },
)
async def compare_entities_semantic(args: dict[str, Any]) -> dict[str, Any]:
    """
    Compare two entities for semantic similarity.

    Provides detailed breakdown of all similarity signals:
    - String similarity (Jaro-Winkler on labels)
    - Alias overlap (Jaccard on alias sets)
    - Type matching (same entity type)
    - Graph context (shared neighbors)

    Args:
        args: Tool arguments containing:
            - project_id: Target KG project ID
            - node_a_id: ID of the first entity
            - node_b_id: ID of the second entity

    Returns:
        MCP tool response with detailed comparison or error
    """
    try:
        project_id = args.get("project_id", "")
        node_a_id = args.get("node_a_id", "")
        node_b_id = args.get("node_b_id", "")

        if not project_id:
            return {"success": False, "error": "project_id is required"}
        if not node_a_id:
            return {"success": False, "error": "node_a_id is required"}
        if not node_b_id:
            return {"success": False, "error": "node_b_id is required"}

        if node_a_id == node_b_id:
            return {"success": False, "error": "Cannot compare an entity with itself"}

        kg_service = _get_kg_service()

        # Validate project exists
        project = await kg_service.get_project(project_id)
        if not project:
            return {"success": False, "error": f"Project '{project_id}' not found"}

        # Get knowledge base
        kb = await kg_service.get_knowledge_base(project_id)
        if not kb:
            return {
                "success": False,
                "error": f"Project '{project_id}' has no knowledge base.",
            }

        # Get nodes
        node_a = kb.get_node(node_a_id)
        node_b = kb.get_node(node_b_id)

        if not node_a:
            return {"success": False, "error": f"Entity '{node_a_id}' not found"}
        if not node_b:
            return {"success": False, "error": f"Entity '{node_b_id}' not found"}

        # Compute similarity using EntityMatcher
        from app.kg.resolution import EntityMatcher

        matcher = EntityMatcher()
        confidence, signals = matcher.compute_similarity(node_a, node_b, kb)

        # Get shared neighbors
        neighbors_a = {n.label for n in kb.get_neighbors(node_a_id)}
        neighbors_b = {n.label for n in kb.get_neighbors(node_b_id)}
        shared_neighbors = neighbors_a & neighbors_b

        # Build detailed comparison
        lines = [
            "## Entity Comparison\n",
            f"### {node_a.label} vs {node_b.label}\n",
            f"**Overall Confidence:** {confidence:.1%}\n",
            "",
            "### Entity Details",
            "",
            "| Attribute | Entity A | Entity B |",
            "|-----------|----------|----------|",
            f"| Label | {node_a.label} | {node_b.label} |",
            f"| Type | {node_a.entity_type} | {node_b.entity_type} |",
            f"| Aliases | {', '.join(node_a.aliases) or 'none'} | {', '.join(node_b.aliases) or 'none'} |",
            f"| Connections | {len(neighbors_a)} | {len(neighbors_b)} |",
            "",
            "### Similarity Signals",
            "",
            "| Signal | Score | Description |",
            "|--------|-------|-------------|",
        ]

        # Format signals with descriptions
        signal_descriptions = {
            "string_sim": "Label text similarity (Jaro-Winkler)",
            "alias_sim": "Alias overlap (Jaccard)",
            "type_sim": "Same entity type",
            "graph_sim": "Shared neighbors",
            "semantic_sim": "Semantic embedding (placeholder)",
        }

        for signal, score in signals.items():
            desc = signal_descriptions.get(signal, signal)
            status = "High" if score >= 0.7 else "Medium" if score >= 0.4 else "Low"
            lines.append(f"| {signal} | {score:.1%} ({status}) | {desc} |")

        # Show shared neighbors if any
        if shared_neighbors:
            lines.append(f"\n### Shared Connections ({len(shared_neighbors)})")
            for neighbor in list(shared_neighbors)[:10]:
                lines.append(f"- {neighbor}")
            if len(shared_neighbors) > 10:
                lines.append(f"- ... and {len(shared_neighbors) - 10} more")

        # Recommendation
        lines.append("\n### Recommendation")
        if confidence >= 0.9:
            lines.append(
                f"**Strong match** ({confidence:.0%}) - These are likely the same entity. "
                "Consider merging automatically."
            )
        elif confidence >= 0.7:
            lines.append(
                f"**Possible match** ({confidence:.0%}) - Review carefully. "
                "May be the same entity with variations."
            )
        else:
            lines.append(
                f"**Weak match** ({confidence:.0%}) - Likely different entities. "
                "Do not merge without additional evidence."
            )

        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    except Exception as e:
        return {"success": False, "error": f"Comparison failed: {e!s}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EXPORTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

KG_TOOLS = [
    extract_to_kg,
    list_kg_projects,
    create_kg_project,
    bootstrap_kg_project,
    get_kg_stats,
    ask_about_graph,
    find_duplicate_entities,
    merge_entities_tool,
    review_pending_merges,
    approve_merge,
    reject_merge,
    compare_entities_semantic,
]
