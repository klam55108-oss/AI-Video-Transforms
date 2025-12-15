"""
Bootstrap MCP tools for domain inference.

These tools are called by Claude to analyze transcript content and build a
DomainProfile. The profile captures entity types, relationship types, seed
entities, and extraction context — all inferred from the first video.

Tool Order (must be called sequentially):
    1. analyze_content_domain - Identify domain and content type
    2. identify_thing_types - Extract 4-8 entity types
    3. identify_connection_types - Extract 5-10 relationship types
    4. identify_seed_entities - Extract 5-15 key entities
    5. generate_extraction_context - Create extraction guidance
    6. finalize_domain_profile - Finalize with name and confidence

Response Format:
    - Success: {"content": [{"type": "text", "text": "..."}], "_bootstrap_data": {...}}
    - Error: {"success": False, "error": "message"}

The _bootstrap_data field contains structured data that the service layer
collects to build the final DomainProfile.
"""

from __future__ import annotations

import threading
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BOOTSTRAP DATA COLLECTOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Thread-local storage for bootstrap data collection.
# Each bootstrap operation should call clear_bootstrap_collector() before starting
# and get_bootstrap_data() after completion to retrieve collected tool results.
_bootstrap_collector: dict[str, Any] = {}
_collector_lock = threading.Lock()


def clear_bootstrap_collector() -> None:
    """Clear the bootstrap data collector before starting a new bootstrap."""
    global _bootstrap_collector
    with _collector_lock:
        _bootstrap_collector = {}


def get_bootstrap_data() -> dict[str, Any]:
    """Get all collected bootstrap data from tool invocations."""
    with _collector_lock:
        return _bootstrap_collector.copy()


def _store_bootstrap_data(step: str, data: Any) -> None:
    """Store data from a bootstrap tool invocation."""
    with _collector_lock:
        _bootstrap_collector[step] = data


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BOOTSTRAP TOOLS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(
    "analyze_content_domain",
    "Analyze transcript content to identify the research domain, content type, and "
    "key characteristics. Call this FIRST before any other bootstrap tools.",
    {
        "type": "object",
        "properties": {
            "content_type": {
                "type": "string",
                "description": "Type of content: documentary, interview, lecture, "
                "news, podcast, music, tutorial, etc.",
            },
            "domain": {
                "type": "string",
                "description": "Research domain: history, science, music, politics, "
                "true_crime, technology, entertainment, etc.",
            },
            "topic_summary": {
                "type": "string",
                "description": "2-3 sentence summary of what this content is about.",
            },
            "key_themes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Main themes or topics covered (3-7 themes).",
            },
            "complexity": {
                "type": "string",
                "enum": ["simple", "moderate", "complex"],
                "description": "How interconnected/complex is the subject matter?",
            },
        },
        "required": [
            "content_type",
            "domain",
            "topic_summary",
            "key_themes",
            "complexity",
        ],
    },
)
async def analyze_content_domain(args: dict[str, Any]) -> dict[str, Any]:
    """
    Record the analysis of content domain characteristics.

    This structures the agent's initial observations about the content,
    setting the stage for more detailed entity and relationship identification.

    Args:
        args: Dictionary with content_type, domain, topic_summary, key_themes, complexity

    Returns:
        Structured response with confirmation and _bootstrap_data for collection
    """
    try:
        # Validate required fields
        required = [
            "content_type",
            "domain",
            "topic_summary",
            "key_themes",
            "complexity",
        ]
        for field in required:
            if field not in args:
                return {"success": False, "error": f"Missing required field: {field}"}

        # Validate key_themes is a list
        if not isinstance(args["key_themes"], list):
            return {"success": False, "error": "key_themes must be an array"}

        # Validate complexity enum
        if args["complexity"] not in ["simple", "moderate", "complex"]:
            return {
                "success": False,
                "error": "complexity must be one of: simple, moderate, complex",
            }

        data = {
            "content_type": args["content_type"],
            "domain": args["domain"],
            "topic_summary": args["topic_summary"],
            "key_themes": args["key_themes"],
            "complexity": args["complexity"],
        }

        # Store data in collector for service layer
        _store_bootstrap_data("analyze_content_domain", data)

        summary_preview = args["topic_summary"][:100]
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Domain analysis recorded: {args['domain']} / "
                    f"{args['content_type']} — {summary_preview}...",
                }
            ],
        }
    except Exception as e:
        return {"success": False, "error": f"analyze_content_domain failed: {e}"}


@tool(
    "identify_thing_types",
    "Identify the types of entities/things that should be extracted from this content. "
    "Call AFTER analyze_content_domain. Aim for 4-8 distinct thing types.",
    {
        "type": "object",
        "properties": {
            "thing_types": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Type name (PascalCase, e.g., Person, Organization, Event)",
                        },
                        "description": {
                            "type": "string",
                            "description": "What this type represents in this domain",
                        },
                        "examples": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "2-3 examples found in the content",
                        },
                        "icon": {
                            "type": "string",
                            "description": "Emoji icon for UI display (e.g., person for Person)",
                        },
                        "priority": {
                            "type": "integer",
                            "enum": [1, 2, 3],
                            "description": "1=high priority, 2=medium, 3=low",
                        },
                    },
                    "required": ["name", "description", "examples"],
                },
                "description": "List of 4-8 thing types to extract from this domain",
            },
        },
        "required": ["thing_types"],
    },
)
async def identify_thing_types(args: dict[str, Any]) -> dict[str, Any]:
    """
    Record identified thing types (entity categories) for the domain.

    Thing types define what categories of entities the extraction process
    should look for (e.g., Person, Organization, Project, Document).

    Args:
        args: Dictionary with thing_types array

    Returns:
        Structured response with confirmation and _bootstrap_data
    """
    try:
        if "thing_types" not in args:
            return {"success": False, "error": "Missing required field: thing_types"}

        thing_types = args["thing_types"]
        if not isinstance(thing_types, list):
            return {"success": False, "error": "thing_types must be an array"}

        if len(thing_types) < 1:
            return {"success": False, "error": "At least one thing type is required"}

        # Normalize and validate each thing type
        normalized_types = []
        for i, t in enumerate(thing_types):
            if not isinstance(t, dict):
                return {
                    "success": False,
                    "error": f"thing_types[{i}] must be an object",
                }

            if "name" not in t:
                return {"success": False, "error": f"thing_types[{i}] missing 'name'"}
            if "description" not in t:
                return {
                    "success": False,
                    "error": f"thing_types[{i}] missing 'description'",
                }
            if "examples" not in t:
                return {
                    "success": False,
                    "error": f"thing_types[{i}] missing 'examples'",
                }

            normalized_types.append(
                {
                    "name": t["name"],
                    "description": t["description"],
                    "examples": t.get("examples", []),
                    "icon": t.get("icon", "package"),
                    "priority": t.get("priority", 2),
                }
            )

        # Store data in collector for service layer
        _store_bootstrap_data("identify_thing_types", normalized_types)

        type_names = [t["name"] for t in normalized_types]
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Identified {len(normalized_types)} thing types: {', '.join(type_names)}",
                }
            ],
        }
    except Exception as e:
        return {"success": False, "error": f"identify_thing_types failed: {e}"}


@tool(
    "identify_connection_types",
    "Identify the types of relationships/connections between entities. "
    "Call AFTER identify_thing_types. Aim for 5-10 connection types.",
    {
        "type": "object",
        "properties": {
            "connection_types": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Internal name (snake_case, e.g., worked_for, directed)",
                        },
                        "display_name": {
                            "type": "string",
                            "description": "Human-readable name (e.g., 'worked for', 'directed')",
                        },
                        "description": {
                            "type": "string",
                            "description": "What this relationship means between entities",
                        },
                        "examples": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 2,
                                "maxItems": 2,
                            },
                            "description": "Example pairs: [[source, target], ...]",
                        },
                        "directional": {
                            "type": "boolean",
                            "description": "Is A->B different from B->A? (default: true)",
                        },
                    },
                    "required": ["name", "display_name", "description"],
                },
                "description": "List of 5-10 connection types to track",
            },
        },
        "required": ["connection_types"],
    },
)
async def identify_connection_types(args: dict[str, Any]) -> dict[str, Any]:
    """
    Record identified connection types (relationship categories) for the domain.

    Connection types define what kinds of relationships the extraction process
    should look for between entities (e.g., worked_for, funded_by, mentioned_in).

    Args:
        args: Dictionary with connection_types array

    Returns:
        Structured response with confirmation and _bootstrap_data
    """
    try:
        if "connection_types" not in args:
            return {
                "success": False,
                "error": "Missing required field: connection_types",
            }

        connection_types = args["connection_types"]
        if not isinstance(connection_types, list):
            return {"success": False, "error": "connection_types must be an array"}

        if len(connection_types) < 1:
            return {
                "success": False,
                "error": "At least one connection type is required",
            }

        # Normalize and validate each connection type
        normalized_types = []
        for i, c in enumerate(connection_types):
            if not isinstance(c, dict):
                return {
                    "success": False,
                    "error": f"connection_types[{i}] must be an object",
                }

            if "name" not in c:
                return {
                    "success": False,
                    "error": f"connection_types[{i}] missing 'name'",
                }
            if "display_name" not in c:
                return {
                    "success": False,
                    "error": f"connection_types[{i}] missing 'display_name'",
                }
            if "description" not in c:
                return {
                    "success": False,
                    "error": f"connection_types[{i}] missing 'description'",
                }

            # Convert example tuples if they exist
            examples = c.get("examples", [])
            tuple_examples = [
                tuple(ex) if isinstance(ex, list) else ex for ex in examples
            ]

            normalized_types.append(
                {
                    "name": c["name"],
                    "display_name": c["display_name"],
                    "description": c["description"],
                    "examples": tuple_examples,
                    "directional": c.get("directional", True),
                }
            )

        # Store data in collector for service layer
        _store_bootstrap_data("identify_connection_types", normalized_types)

        display_names = [c["display_name"] for c in normalized_types]
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Identified {len(normalized_types)} connection types: "
                    f"{', '.join(display_names)}",
                }
            ],
        }
    except Exception as e:
        return {"success": False, "error": f"identify_connection_types failed: {e}"}


@tool(
    "identify_seed_entities",
    "Identify key entities from the content to seed the knowledge graph. "
    "These ensure consistency across future extractions. "
    "Call AFTER identify_connection_types. Aim for 5-15 seed entities.",
    {
        "type": "object",
        "properties": {
            "seed_entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "description": "Primary name/label for this entity",
                        },
                        "thing_type": {
                            "type": "string",
                            "description": "Which thing type this entity belongs to",
                        },
                        "aliases": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Alternative names/spellings/abbreviations",
                        },
                        "description": {
                            "type": "string",
                            "description": "Brief description of this entity (optional)",
                        },
                    },
                    "required": ["label", "thing_type"],
                },
                "description": "5-15 key entities to seed the knowledge graph",
            },
        },
        "required": ["seed_entities"],
    },
)
async def identify_seed_entities(args: dict[str, Any]) -> dict[str, Any]:
    """
    Record seed entities for graph initialization.

    Seed entities are the most important, central entities found in the content.
    They help maintain naming consistency across future extractions
    (e.g., always "CIA" not "the Agency" or "Central Intelligence Agency").

    Args:
        args: Dictionary with seed_entities array

    Returns:
        Structured response with confirmation and _bootstrap_data
    """
    try:
        if "seed_entities" not in args:
            return {"success": False, "error": "Missing required field: seed_entities"}

        seed_entities = args["seed_entities"]
        if not isinstance(seed_entities, list):
            return {"success": False, "error": "seed_entities must be an array"}

        if len(seed_entities) < 1:
            return {"success": False, "error": "At least one seed entity is required"}

        # Normalize and validate each seed entity
        normalized_entities = []
        for i, e in enumerate(seed_entities):
            if not isinstance(e, dict):
                return {
                    "success": False,
                    "error": f"seed_entities[{i}] must be an object",
                }

            if "label" not in e:
                return {
                    "success": False,
                    "error": f"seed_entities[{i}] missing 'label'",
                }
            if "thing_type" not in e:
                return {
                    "success": False,
                    "error": f"seed_entities[{i}] missing 'thing_type'",
                }

            normalized_entities.append(
                {
                    "label": e["label"],
                    "thing_type": e["thing_type"],
                    "aliases": e.get("aliases", []),
                    "description": e.get("description"),
                    "confidence": 1.0,  # Seed entities have high confidence
                }
            )

        # Store data in collector for service layer
        _store_bootstrap_data("identify_seed_entities", normalized_entities)

        # Show preview of first 5 entities
        labels = [e["label"] for e in normalized_entities]
        preview = ", ".join(labels[:5])
        suffix = "..." if len(labels) > 5 else ""

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Identified {len(normalized_entities)} seed entities: {preview}{suffix}",
                }
            ],
        }
    except Exception as e:
        return {"success": False, "error": f"identify_seed_entities failed: {e}"}


@tool(
    "generate_extraction_context",
    "Generate domain-specific context that will guide future extraction. "
    "This context is embedded in extraction prompts to improve accuracy. "
    "Call AFTER identify_seed_entities.",
    {
        "type": "object",
        "properties": {
            "context": {
                "type": "string",
                "description": "Domain context paragraph(s) for extraction prompts. "
                "Include: domain-specific terminology, important patterns to watch for, "
                "disambiguation guidance (e.g., 'The Agency' = CIA), naming conventions, "
                "and any special extraction rules for this domain.",
            },
        },
        "required": ["context"],
    },
)
async def generate_extraction_context(args: dict[str, Any]) -> dict[str, Any]:
    """
    Record extraction context for prompt generation.

    The extraction context provides domain-specific guidance that will be
    embedded in future extraction prompts. This helps Claude consistently
    identify entities and relationships specific to this domain.

    Args:
        args: Dictionary with context string

    Returns:
        Structured response with confirmation and _bootstrap_data
    """
    try:
        if "context" not in args:
            return {"success": False, "error": "Missing required field: context"}

        context = args["context"]
        if not isinstance(context, str):
            return {"success": False, "error": "context must be a string"}

        if len(context) < 50:
            return {
                "success": False,
                "error": "context should be at least 50 characters for useful guidance",
            }

        # Store data in collector for service layer
        _store_bootstrap_data("generate_extraction_context", context)

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Extraction context generated ({len(context)} chars)",
                }
            ],
        }
    except Exception as e:
        return {"success": False, "error": f"generate_extraction_context failed: {e}"}


@tool(
    "finalize_domain_profile",
    "Finalize and create the domain profile from all gathered information. "
    "Call this LAST after all other bootstrap tools have been called.",
    {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Short name for this domain "
                "(e.g., 'CIA Mind Control Research', 'NF Discography', 'SpaceX History')",
            },
            "description": {
                "type": "string",
                "description": "2-3 sentence description of what this research domain covers",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confidence in this domain profile (0.0-1.0). "
                "Higher if content was clear and comprehensive, lower if ambiguous.",
            },
        },
        "required": ["name", "description", "confidence"],
    },
)
async def finalize_domain_profile(args: dict[str, Any]) -> dict[str, Any]:
    """
    Finalize the domain profile with name, description, and confidence.

    This is the last step in the bootstrap process. The collected data from
    all previous tools will be assembled into a complete DomainProfile by
    the service layer.

    Args:
        args: Dictionary with name, description, and confidence

    Returns:
        Structured response with confirmation and _bootstrap_data
    """
    try:
        # Validate required fields
        required = ["name", "description", "confidence"]
        for field in required:
            if field not in args:
                return {"success": False, "error": f"Missing required field: {field}"}

        name = args["name"]
        description = args["description"]
        confidence = args["confidence"]

        if not isinstance(name, str) or len(name) < 3:
            return {"success": False, "error": "name must be at least 3 characters"}

        if not isinstance(description, str) or len(description) < 20:
            return {
                "success": False,
                "error": "description must be at least 20 characters",
            }

        if not isinstance(confidence, (int, float)):
            return {"success": False, "error": "confidence must be a number"}

        if confidence < 0.0 or confidence > 1.0:
            return {"success": False, "error": "confidence must be between 0.0 and 1.0"}

        data = {
            "name": name,
            "description": description,
            "confidence": float(confidence),
        }

        # Store data in collector for service layer
        _store_bootstrap_data("finalize_domain_profile", data)

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Domain profile finalized: '{name}' (confidence: {confidence:.0%})",
                }
            ],
        }
    except Exception as e:
        return {"success": False, "error": f"finalize_domain_profile failed: {e}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCP SERVER FACTORY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BOOTSTRAP_TOOLS = [
    analyze_content_domain,
    identify_thing_types,
    identify_connection_types,
    identify_seed_entities,
    generate_extraction_context,
    finalize_domain_profile,
]


def create_bootstrap_mcp_server() -> Any:
    """
    Create MCP server for bootstrap tools.

    Returns a configured MCP server that can be passed to ClaudeAgentOptions.
    The server exposes all 6 bootstrap tools for domain inference.

    Returns:
        MCP server instance for use with Claude Agent SDK
    """
    return create_sdk_mcp_server(
        name="kg-bootstrap",
        version="1.0.0",
        tools=BOOTSTRAP_TOOLS,
    )


# Tool names for allowlist (matches pattern: mcp__<server-name>__<tool-name>)
BOOTSTRAP_TOOL_NAMES = [
    "mcp__kg-bootstrap__analyze_content_domain",
    "mcp__kg-bootstrap__identify_thing_types",
    "mcp__kg-bootstrap__identify_connection_types",
    "mcp__kg-bootstrap__identify_seed_entities",
    "mcp__kg-bootstrap__generate_extraction_context",
    "mcp__kg-bootstrap__finalize_domain_profile",
]
