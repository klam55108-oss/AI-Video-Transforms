"""
Extraction MCP tool — extracts entities using DomainProfile.

This module provides the MCP tool that Claude uses to report extraction results.
Unlike the bootstrap tools (which collect data step-by-step), the extraction tool
receives the complete extraction output in a single call.

The tool validates the extraction data against our schemas and returns both:
1. A human-readable summary (for the agent conversation)
2. A structured `_extraction_result` (for the service layer to persist)

Response Format:
    - Success: {"content": [{"type": "text", "text": "..."}], "_extraction_result": {...}}
    - Error: {"success": False, "error": "message"}

The _extraction_result field contains the validated ExtractionResult data
that the service layer uses to populate the KnowledgeBase.
"""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from app.kg.schemas import (
    ExtractedDiscovery,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)


@tool(
    "extract_knowledge",
    "Extract entities and relationships from content based on the domain profile. "
    "Call this tool with all extracted entities, relationships, and any new type "
    "discoveries. Returns structured extraction results for storage.",
    {
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "description": "Entities extracted from the content",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "description": "Primary name for this entity",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Type from the domain profile "
                            "(e.g., Person, Organization, Event)",
                        },
                        "aliases": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Alternative names/spellings for this entity",
                        },
                        "description": {
                            "type": "string",
                            "description": "Brief description of this entity",
                        },
                    },
                    "required": ["label", "entity_type"],
                },
            },
            "relationships": {
                "type": "array",
                "description": "Relationships between entities",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_label": {
                            "type": "string",
                            "description": "Label of the source entity",
                        },
                        "target_label": {
                            "type": "string",
                            "description": "Label of the target entity",
                        },
                        "relationship_type": {
                            "type": "string",
                            "description": "Type from the domain profile "
                            "(e.g., worked_for, directed, mentioned_in)",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "Confidence score (0.0-1.0)",
                        },
                        "evidence": {
                            "type": "string",
                            "description": "Supporting quote or context from the source",
                        },
                    },
                    "required": ["source_label", "target_label", "relationship_type"],
                },
            },
            "discoveries": {
                "type": "array",
                "description": "New types discovered that aren't in the domain profile",
                "items": {
                    "type": "object",
                    "properties": {
                        "discovery_type": {
                            "type": "string",
                            "enum": ["thing_type", "connection_type"],
                            "description": "Type of discovery",
                        },
                        "name": {
                            "type": "string",
                            "description": "Internal identifier (snake_case)",
                        },
                        "display_name": {
                            "type": "string",
                            "description": "Human-readable name",
                        },
                        "description": {
                            "type": "string",
                            "description": "Why this type seems important",
                        },
                        "examples": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Examples found in the content",
                        },
                    },
                    "required": [
                        "discovery_type",
                        "name",
                        "display_name",
                        "description",
                    ],
                },
            },
            "summary": {
                "type": "string",
                "description": "2-3 sentence summary of key information extracted",
            },
        },
        "required": ["entities", "relationships"],
    },
)
async def extract_knowledge(args: dict[str, Any]) -> dict[str, Any]:
    """
    Process and validate extraction results from Claude.

    This tool receives the complete extraction output from Claude after it has
    analyzed content using the domain profile. It validates the data against
    our Pydantic schemas and returns both a summary for the conversation and
    structured data for persistence.

    Args:
        args: Dictionary containing:
            - entities: List of extracted entities
            - relationships: List of extracted relationships
            - discoveries: Optional list of new type discoveries
            - summary: Optional summary of extraction

    Returns:
        On success: {"content": [...], "_extraction_result": {...}}
        On failure: {"success": False, "error": "..."}
    """
    try:
        # Validate entities
        raw_entities = args.get("entities", [])
        if not isinstance(raw_entities, list):
            return {"success": False, "error": "entities must be an array"}

        entities: list[ExtractedEntity] = []
        for i, e in enumerate(raw_entities):
            if not isinstance(e, dict):
                return {"success": False, "error": f"entities[{i}] must be an object"}
            if "label" not in e:
                return {"success": False, "error": f"entities[{i}] missing 'label'"}
            if "entity_type" not in e:
                return {
                    "success": False,
                    "error": f"entities[{i}] missing 'entity_type'",
                }

            entities.append(
                ExtractedEntity(
                    label=e["label"],
                    entity_type=e["entity_type"],
                    aliases=e.get("aliases", []),
                    description=e.get("description"),
                    properties=e.get("properties", {}),
                )
            )

        # Validate relationships
        raw_relationships = args.get("relationships", [])
        if not isinstance(raw_relationships, list):
            return {"success": False, "error": "relationships must be an array"}

        relationships: list[ExtractedRelationship] = []
        for i, r in enumerate(raw_relationships):
            if not isinstance(r, dict):
                return {
                    "success": False,
                    "error": f"relationships[{i}] must be an object",
                }
            if "source_label" not in r:
                return {
                    "success": False,
                    "error": f"relationships[{i}] missing 'source_label'",
                }
            if "target_label" not in r:
                return {
                    "success": False,
                    "error": f"relationships[{i}] missing 'target_label'",
                }
            if "relationship_type" not in r:
                return {
                    "success": False,
                    "error": f"relationships[{i}] missing 'relationship_type'",
                }

            # Clamp confidence to valid range
            confidence = r.get("confidence", 1.0)
            if not isinstance(confidence, (int, float)):
                confidence = 1.0
            confidence = max(0.0, min(1.0, float(confidence)))

            relationships.append(
                ExtractedRelationship(
                    source_label=r["source_label"],
                    target_label=r["target_label"],
                    relationship_type=r["relationship_type"],
                    confidence=confidence,
                    evidence=r.get("evidence"),
                    properties=r.get("properties", {}),
                )
            )

        # Validate discoveries (optional)
        raw_discoveries = args.get("discoveries", [])
        if not isinstance(raw_discoveries, list):
            raw_discoveries = []

        discoveries: list[ExtractedDiscovery] = []
        for i, d in enumerate(raw_discoveries):
            if not isinstance(d, dict):
                continue  # Skip invalid discoveries rather than failing

            # All required fields must be present
            if not all(
                k in d
                for k in ["discovery_type", "name", "display_name", "description"]
            ):
                continue

            # Validate discovery_type
            if d["discovery_type"] not in ["thing_type", "connection_type"]:
                continue

            discoveries.append(
                ExtractedDiscovery(
                    discovery_type=d["discovery_type"],
                    name=d["name"],
                    display_name=d["display_name"],
                    description=d["description"],
                    examples=d.get("examples", []),
                )
            )

        # Build the extraction result
        result = ExtractionResult(
            entities=entities,
            relationships=relationships,
            discoveries=discoveries,
            summary=args.get("summary"),
        )

        # Build response summary
        entity_count = len(result.entities)
        relationship_count = len(result.relationships)
        discovery_count = len(result.discoveries)

        summary_parts = [
            f"Extracted {entity_count} entities and {relationship_count} relationships"
        ]
        if discovery_count > 0:
            summary_parts.append(f"with {discovery_count} new type discoveries")
        if result.summary:
            summary_parts.append(f"— {result.summary}")

        return {
            "content": [
                {
                    "type": "text",
                    "text": ". ".join(summary_parts),
                }
            ],
            "_extraction_result": result.model_dump(),
        }
    except Exception as e:
        return {"success": False, "error": f"extract_knowledge failed: {e}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCP SERVER FACTORY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXTRACTION_TOOLS = [extract_knowledge]


def create_extraction_mcp_server() -> Any:
    """
    Create MCP server for extraction tools.

    Returns a configured MCP server that can be passed to ClaudeAgentOptions.
    The server exposes the extract_knowledge tool for entity/relationship extraction.

    Returns:
        MCP server instance for use with Claude Agent SDK
    """
    return create_sdk_mcp_server(
        name="kg-extraction",
        version="1.0.0",
        tools=EXTRACTION_TOOLS,
    )


# Tool names for allowlist (matches pattern: mcp__<server-name>__<tool-name>)
EXTRACTION_TOOL_NAMES = [
    "mcp__kg-extraction__extract_knowledge",
]
