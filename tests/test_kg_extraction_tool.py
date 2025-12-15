"""
Tests for Knowledge Graph extraction MCP tool.

This module tests the extract_knowledge MCP tool used for entity and
relationship extraction during KG population:
- extract_knowledge: Process and validate extraction results from Claude

Each tool returns structured responses:
- Success: {"content": [{"type": "text", "text": "..."}], "_extraction_result": {...}}
- Error: {"success": False, "error": "message"}

Note: The @tool decorator from claude_agent_sdk wraps functions into SdkMcpTool
objects. We access the underlying handler function via the .handler attribute
for direct testing.
"""

from __future__ import annotations

import pytest

from app.kg.tools.extraction import (
    EXTRACTION_TOOL_NAMES,
    EXTRACTION_TOOLS,
    create_extraction_mcp_server,
    extract_knowledge,
)

# Extract underlying handler function from SdkMcpTool object
# The @tool decorator wraps functions, so we need .handler to get the callable
_extract_knowledge = extract_knowledge.handler


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EXTRACT KNOWLEDGE SUCCESS TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestExtractKnowledgeSuccess:
    """Tests for successful extract_knowledge tool invocation."""

    @pytest.mark.asyncio
    async def test_extract_knowledge_success(self):
        """Test successful extraction with valid entities and relationships."""
        args = {
            "entities": [
                {
                    "label": "CIA",
                    "entity_type": "Organization",
                    "aliases": ["Central Intelligence Agency", "The Agency"],
                    "description": "US intelligence agency",
                },
                {
                    "label": "Dr. Sidney Gottlieb",
                    "entity_type": "Person",
                    "aliases": ["Joseph Scheider"],
                    "description": "CIA chemist who directed MKULTRA",
                },
            ],
            "relationships": [
                {
                    "source_label": "Dr. Sidney Gottlieb",
                    "target_label": "CIA",
                    "relationship_type": "worked_for",
                    "confidence": 0.95,
                    "evidence": "Gottlieb worked for the CIA from 1951 to 1973.",
                }
            ],
            "summary": "Key figures in CIA mind control research identified.",
        }

        result = await _extract_knowledge(args)

        # Should return content format (success)
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "2 entities" in result["content"][0]["text"]
        assert "1 relationships" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_extract_knowledge_success_minimal_entities(self):
        """Test successful extraction with minimal required fields."""
        args = {
            "entities": [
                {
                    "label": "MKULTRA",
                    "entity_type": "Project",
                }
            ],
            "relationships": [],
        }

        result = await _extract_knowledge(args)

        assert "content" in result
        assert "1 entities" in result["content"][0]["text"]
        assert "0 relationships" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_extract_knowledge_success_with_discoveries(self):
        """Test successful extraction with type discoveries."""
        args = {
            "entities": [
                {
                    "label": "Frank Olson",
                    "entity_type": "Person",
                }
            ],
            "relationships": [],
            "discoveries": [
                {
                    "discovery_type": "thing_type",
                    "name": "experiment",
                    "display_name": "Experiment",
                    "description": "Scientific experiments conducted as part of research programs",
                    "examples": ["Operation Midnight Climax", "Subproject 68"],
                }
            ],
        }

        result = await _extract_knowledge(args)

        assert "content" in result
        assert "1 new type discoveries" in result["content"][0]["text"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EXTRACT KNOWLEDGE RETURNS RESULT TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestExtractKnowledgeReturnsResult:
    """Tests for extract_knowledge tool returning structured _extraction_result."""

    @pytest.mark.asyncio
    async def test_extract_knowledge_returns_result(self):
        """Test that successful extraction includes _extraction_result data."""
        args = {
            "entities": [
                {
                    "label": "CIA",
                    "entity_type": "Organization",
                    "aliases": ["Central Intelligence Agency"],
                    "description": "US intelligence agency",
                },
                {
                    "label": "Project MKULTRA",
                    "entity_type": "Project",
                    "aliases": ["MK-ULTRA", "MK Ultra"],
                    "description": "CIA mind control research program",
                },
            ],
            "relationships": [
                {
                    "source_label": "CIA",
                    "target_label": "Project MKULTRA",
                    "relationship_type": "funded",
                    "confidence": 0.99,
                    "evidence": "The CIA funded and operated Project MKULTRA.",
                }
            ],
            "summary": "Core entities of MKULTRA program identified.",
        }

        result = await _extract_knowledge(args)

        # Should include _extraction_result for service layer
        assert "_extraction_result" in result
        extraction_result = result["_extraction_result"]

        # Validate entities
        assert len(extraction_result["entities"]) == 2
        cia_entity = extraction_result["entities"][0]
        assert cia_entity["label"] == "CIA"
        assert cia_entity["entity_type"] == "Organization"
        assert "Central Intelligence Agency" in cia_entity["aliases"]

        # Validate relationships
        assert len(extraction_result["relationships"]) == 1
        rel = extraction_result["relationships"][0]
        assert rel["source_label"] == "CIA"
        assert rel["target_label"] == "Project MKULTRA"
        assert rel["relationship_type"] == "funded"
        assert rel["confidence"] == 0.99

        # Validate summary
        assert (
            extraction_result["summary"]
            == "Core entities of MKULTRA program identified."
        )

    @pytest.mark.asyncio
    async def test_extract_knowledge_returns_result_with_discoveries(self):
        """Test that _extraction_result includes validated discoveries."""
        args = {
            "entities": [{"label": "Entity1", "entity_type": "Person"}],
            "relationships": [],
            "discoveries": [
                {
                    "discovery_type": "connection_type",
                    "name": "supervised_by",
                    "display_name": "supervised by",
                    "description": "Direct supervisory relationship between individuals",
                    "examples": ["Gottlieb supervised by Dulles"],
                },
                {
                    "discovery_type": "thing_type",
                    "name": "document",
                    "display_name": "Document",
                    "description": "Official documents and records",
                    "examples": ["MKULTRA documents"],
                },
            ],
        }

        result = await _extract_knowledge(args)

        assert "_extraction_result" in result
        discoveries = result["_extraction_result"]["discoveries"]
        assert len(discoveries) == 2

        # Check connection_type discovery
        conn_discovery = next(
            d for d in discoveries if d["discovery_type"] == "connection_type"
        )
        assert conn_discovery["name"] == "supervised_by"
        assert conn_discovery["display_name"] == "supervised by"

        # Check thing_type discovery
        thing_discovery = next(
            d for d in discoveries if d["discovery_type"] == "thing_type"
        )
        assert thing_discovery["name"] == "document"

    @pytest.mark.asyncio
    async def test_extract_knowledge_returns_result_confidence_clamping(self):
        """Test that confidence values are clamped to valid range."""
        args = {
            "entities": [
                {"label": "Entity1", "entity_type": "Person"},
                {"label": "Entity2", "entity_type": "Person"},
            ],
            "relationships": [
                {
                    "source_label": "Entity1",
                    "target_label": "Entity2",
                    "relationship_type": "knows",
                    "confidence": 1.5,  # Should be clamped to 1.0
                },
                {
                    "source_label": "Entity2",
                    "target_label": "Entity1",
                    "relationship_type": "knows",
                    "confidence": -0.5,  # Should be clamped to 0.0
                },
            ],
        }

        result = await _extract_knowledge(args)

        assert "_extraction_result" in result
        relationships = result["_extraction_result"]["relationships"]

        # First relationship should be clamped to 1.0
        assert relationships[0]["confidence"] == 1.0

        # Second relationship should be clamped to 0.0
        assert relationships[1]["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_extract_knowledge_returns_result_default_confidence(self):
        """Test that missing confidence defaults to 1.0."""
        args = {
            "entities": [
                {"label": "Entity1", "entity_type": "Person"},
                {"label": "Entity2", "entity_type": "Person"},
            ],
            "relationships": [
                {
                    "source_label": "Entity1",
                    "target_label": "Entity2",
                    "relationship_type": "knows",
                    # No confidence provided
                }
            ],
        }

        result = await _extract_knowledge(args)

        assert "_extraction_result" in result
        relationships = result["_extraction_result"]["relationships"]
        assert relationships[0]["confidence"] == 1.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EXTRACT KNOWLEDGE ERROR HANDLING TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestExtractKnowledgeErrorHandling:
    """Tests for extract_knowledge tool error handling."""

    @pytest.mark.asyncio
    async def test_extract_knowledge_error_handling_missing_entities(self):
        """Test error handling when entities field is missing."""
        args = {
            "relationships": [
                {
                    "source_label": "A",
                    "target_label": "B",
                    "relationship_type": "knows",
                }
            ]
        }

        result = await _extract_knowledge(args)

        # Should succeed with empty entities (entities defaults to [])
        assert "content" in result
        assert "0 entities" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_extract_knowledge_error_handling_entities_not_array(self):
        """Test error handling when entities is not an array."""
        args = {
            "entities": "not an array",
            "relationships": [],
        }

        result = await _extract_knowledge(args)

        assert "success" in result
        assert result["success"] is False
        assert "entities must be an array" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_knowledge_error_handling_entity_not_object(self):
        """Test error handling when entity item is not an object."""
        args = {
            "entities": ["CIA", "FBI"],  # Strings instead of objects
            "relationships": [],
        }

        result = await _extract_knowledge(args)

        assert result["success"] is False
        assert "entities[0] must be an object" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_knowledge_error_handling_entity_missing_label(self):
        """Test error handling when entity is missing label field."""
        args = {
            "entities": [
                {
                    "entity_type": "Organization",
                    # Missing label
                }
            ],
            "relationships": [],
        }

        result = await _extract_knowledge(args)

        assert result["success"] is False
        assert "entities[0] missing 'label'" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_knowledge_error_handling_entity_missing_type(self):
        """Test error handling when entity is missing entity_type field."""
        args = {
            "entities": [
                {
                    "label": "CIA",
                    # Missing entity_type
                }
            ],
            "relationships": [],
        }

        result = await _extract_knowledge(args)

        assert result["success"] is False
        assert "entities[0] missing 'entity_type'" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_knowledge_error_handling_relationships_not_array(self):
        """Test error handling when relationships is not an array."""
        args = {
            "entities": [],
            "relationships": "not an array",
        }

        result = await _extract_knowledge(args)

        assert result["success"] is False
        assert "relationships must be an array" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_knowledge_error_handling_relationship_not_object(self):
        """Test error handling when relationship item is not an object."""
        args = {
            "entities": [],
            "relationships": ["knows"],  # String instead of object
        }

        result = await _extract_knowledge(args)

        assert result["success"] is False
        assert "relationships[0] must be an object" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_knowledge_error_handling_relationship_missing_source(self):
        """Test error handling when relationship is missing source_label."""
        args = {
            "entities": [],
            "relationships": [
                {
                    "target_label": "CIA",
                    "relationship_type": "works_for",
                    # Missing source_label
                }
            ],
        }

        result = await _extract_knowledge(args)

        assert result["success"] is False
        assert "relationships[0] missing 'source_label'" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_knowledge_error_handling_relationship_missing_target(self):
        """Test error handling when relationship is missing target_label."""
        args = {
            "entities": [],
            "relationships": [
                {
                    "source_label": "Gottlieb",
                    "relationship_type": "works_for",
                    # Missing target_label
                }
            ],
        }

        result = await _extract_knowledge(args)

        assert result["success"] is False
        assert "relationships[0] missing 'target_label'" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_knowledge_error_handling_relationship_missing_type(self):
        """Test error handling when relationship is missing relationship_type."""
        args = {
            "entities": [],
            "relationships": [
                {
                    "source_label": "Gottlieb",
                    "target_label": "CIA",
                    # Missing relationship_type
                }
            ],
        }

        result = await _extract_knowledge(args)

        assert result["success"] is False
        assert "relationships[0] missing 'relationship_type'" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_knowledge_error_handling_invalid_discoveries_skipped(self):
        """Test that invalid discoveries are skipped rather than failing."""
        args = {
            "entities": [{"label": "CIA", "entity_type": "Organization"}],
            "relationships": [],
            "discoveries": [
                # Valid discovery
                {
                    "discovery_type": "thing_type",
                    "name": "document",
                    "display_name": "Document",
                    "description": "Official documents",
                },
                # Invalid: missing required fields (should be skipped)
                {"discovery_type": "thing_type", "name": "incomplete"},
                # Invalid: not an object (should be skipped)
                "not a discovery object",
                # Invalid: wrong discovery_type (should be skipped)
                {
                    "discovery_type": "invalid_type",
                    "name": "test",
                    "display_name": "Test",
                    "description": "Invalid type",
                },
            ],
        }

        result = await _extract_knowledge(args)

        # Should succeed with only the valid discovery
        assert "content" in result
        assert "_extraction_result" in result
        discoveries = result["_extraction_result"]["discoveries"]
        assert len(discoveries) == 1
        assert discoveries[0]["name"] == "document"

    @pytest.mark.asyncio
    async def test_extract_knowledge_error_handling_invalid_confidence_type(self):
        """Test that non-numeric confidence is replaced with default."""
        args = {
            "entities": [
                {"label": "A", "entity_type": "Person"},
                {"label": "B", "entity_type": "Person"},
            ],
            "relationships": [
                {
                    "source_label": "A",
                    "target_label": "B",
                    "relationship_type": "knows",
                    "confidence": "high",  # Invalid type, should become 1.0
                }
            ],
        }

        result = await _extract_knowledge(args)

        assert "_extraction_result" in result
        relationships = result["_extraction_result"]["relationships"]
        assert relationships[0]["confidence"] == 1.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCP SERVER CREATION TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestExtractionMCPServerCreation:
    """Tests for MCP server factory and tool registration."""

    def test_create_extraction_mcp_server(self):
        """Test that create_extraction_mcp_server returns a valid MCP server."""
        server = create_extraction_mcp_server()

        # Server should be created successfully
        assert server is not None
        # The exact attributes depend on SDK implementation, but server should exist

    def test_extraction_tool_names(self):
        """Test that EXTRACTION_TOOL_NAMES contains expected tool."""
        expected_tool_names = [
            "mcp__kg-extraction__extract_knowledge",
        ]

        assert EXTRACTION_TOOL_NAMES == expected_tool_names
        assert len(EXTRACTION_TOOL_NAMES) == 1

    def test_extraction_tools_list_contains_all_tools(self):
        """Test that EXTRACTION_TOOLS list contains all SdkMcpTool objects."""
        assert len(EXTRACTION_TOOLS) == 1

        # Verify tool name (SdkMcpTool objects have a 'name' attribute)
        assert EXTRACTION_TOOLS[0].name == "extract_knowledge"

    def test_tool_names_follow_mcp_pattern(self):
        """Test that tool names follow MCP naming convention."""
        for tool_name in EXTRACTION_TOOL_NAMES:
            # Should follow pattern: mcp__<server-name>__<tool-name>
            assert tool_name.startswith("mcp__kg-extraction__")
            parts = tool_name.split("__")
            assert len(parts) == 3
            assert parts[0] == "mcp"
            assert parts[1] == "kg-extraction"
            assert parts[2] == "extract_knowledge"
