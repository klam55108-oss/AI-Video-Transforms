"""
Tests for Knowledge Graph bootstrap MCP tools.

This module tests the MCP tools used for domain inference during bootstrap:
- analyze_content_domain: Domain and content type analysis
- identify_thing_types: Entity type discovery
- identify_connection_types: Relationship type discovery
- identify_seed_entities: Key entity identification
- generate_extraction_context: Extraction guidance generation
- finalize_domain_profile: Profile finalization

Each tool returns structured responses:
- Success: {"content": [{"type": "text", "text": "..."}]}
- Error: {"success": False, "error": "message"}

Tools also store data in a collector via _bootstrap_collector for assembly
into a DomainProfile by the service layer.

Note: The @tool decorator from claude_agent_sdk wraps functions into SdkMcpTool
objects. We access the underlying handler function via the .handler attribute
for direct testing.
"""

from __future__ import annotations

import pytest

from app.kg.tools.bootstrap import (
    BOOTSTRAP_TOOL_NAMES,
    BOOTSTRAP_TOOLS,
    analyze_content_domain,
    clear_bootstrap_collector,
    create_bootstrap_mcp_server,
    finalize_domain_profile,
    generate_extraction_context,
    get_bootstrap_data,
    identify_connection_types,
    identify_seed_entities,
    identify_thing_types,
)

# Extract underlying handler functions from SdkMcpTool objects
# The @tool decorator wraps functions, so we need .handler to get the callable
_analyze_content_domain = analyze_content_domain.handler
_identify_thing_types = identify_thing_types.handler
_identify_connection_types = identify_connection_types.handler
_identify_seed_entities = identify_seed_entities.handler
_generate_extraction_context = generate_extraction_context.handler
_finalize_domain_profile = finalize_domain_profile.handler


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST FIXTURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.fixture(autouse=True)
def clear_collector():
    """Clear bootstrap collector before each test."""
    clear_bootstrap_collector()
    yield
    clear_bootstrap_collector()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ANALYZE CONTENT DOMAIN TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestAnalyzeContentDomain:
    """Tests for analyze_content_domain tool."""

    @pytest.mark.asyncio
    async def test_analyze_content_domain_success(self):
        """Test successful domain analysis with valid inputs."""
        args = {
            "content_type": "documentary",
            "domain": "history",
            "topic_summary": "This documentary explores the CIA's MKUltra program and its impact on American society during the Cold War era.",
            "key_themes": ["government secrecy", "mind control", "cold war"],
            "complexity": "complex",
        }

        result = await _analyze_content_domain(args)

        # Should return content format (success)
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "Domain analysis recorded" in result["content"][0]["text"]
        assert "history" in result["content"][0]["text"]
        assert "documentary" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_analyze_content_domain_returns_bootstrap_data(self):
        """Test that tool stores data in bootstrap collector."""
        args = {
            "content_type": "interview",
            "domain": "science",
            "topic_summary": "An interview discussing recent breakthroughs in quantum computing research.",
            "key_themes": ["quantum computing", "research", "technology"],
            "complexity": "moderate",
        }

        await _analyze_content_domain(args)

        # Verify data was stored in collector
        bootstrap_data = get_bootstrap_data()
        assert "analyze_content_domain" in bootstrap_data

        stored = bootstrap_data["analyze_content_domain"]
        assert stored["content_type"] == "interview"
        assert stored["domain"] == "science"
        assert stored["complexity"] == "moderate"
        assert len(stored["key_themes"]) == 3

    @pytest.mark.asyncio
    async def test_analyze_content_domain_error_handling(self):
        """Test error handling for missing required fields."""
        # Missing content_type
        args = {
            "domain": "history",
            "topic_summary": "A summary",
            "key_themes": ["theme1"],
            "complexity": "simple",
        }

        result = await _analyze_content_domain(args)

        assert "success" in result
        assert result["success"] is False
        assert "error" in result
        assert "content_type" in result["error"]

    @pytest.mark.asyncio
    async def test_analyze_content_domain_invalid_complexity(self):
        """Test error handling for invalid complexity value."""
        args = {
            "content_type": "documentary",
            "domain": "history",
            "topic_summary": "A summary of the documentary content.",
            "key_themes": ["theme1"],
            "complexity": "invalid_value",
        }

        result = await _analyze_content_domain(args)

        assert result["success"] is False
        assert "complexity" in result["error"]

    @pytest.mark.asyncio
    async def test_analyze_content_domain_invalid_key_themes_type(self):
        """Test error handling when key_themes is not an array."""
        args = {
            "content_type": "documentary",
            "domain": "history",
            "topic_summary": "A summary of the documentary content.",
            "key_themes": "not an array",
            "complexity": "simple",
        }

        result = await _analyze_content_domain(args)

        assert result["success"] is False
        assert "key_themes" in result["error"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# IDENTIFY THING TYPES TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestIdentifyThingTypes:
    """Tests for identify_thing_types tool."""

    @pytest.mark.asyncio
    async def test_identify_thing_types_success(self):
        """Test successful thing type identification."""
        args = {
            "thing_types": [
                {
                    "name": "Person",
                    "description": "A human individual mentioned in the content",
                    "examples": ["Dr. Sidney Gottlieb", "Frank Olson"],
                    "icon": "👤",
                    "priority": 1,
                },
                {
                    "name": "Organization",
                    "description": "A company, agency, or institution",
                    "examples": ["CIA", "FBI"],
                    "icon": "🏢",
                    "priority": 1,
                },
            ]
        }

        result = await _identify_thing_types(args)

        assert "content" in result
        assert result["content"][0]["type"] == "text"
        assert "2 thing types" in result["content"][0]["text"]
        assert "Person" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_identify_thing_types_creates_thing_type_objects(self):
        """Test that tool stores normalized thing type data in collector."""
        args = {
            "thing_types": [
                {
                    "name": "Document",
                    "description": "Official records and reports",
                    "examples": ["MKULTRA documents"],
                },
                {
                    "name": "Project",
                    "description": "Research programs and operations",
                    "examples": ["Project BLUEBIRD"],
                    "icon": "📋",
                    "priority": 2,
                },
            ]
        }

        await _identify_thing_types(args)

        bootstrap_data = get_bootstrap_data()
        assert "identify_thing_types" in bootstrap_data

        thing_types = bootstrap_data["identify_thing_types"]
        assert len(thing_types) == 2

        # Check first type has defaults applied
        doc_type = thing_types[0]
        assert doc_type["name"] == "Document"
        assert doc_type["icon"] == "package"  # Default icon
        assert doc_type["priority"] == 2  # Default priority

        # Check second type preserves provided values
        proj_type = thing_types[1]
        assert proj_type["name"] == "Project"
        assert proj_type["icon"] == "📋"
        assert proj_type["priority"] == 2

    @pytest.mark.asyncio
    async def test_identify_thing_types_error_handling(self):
        """Test error handling for missing required fields."""
        # Missing thing_types entirely
        result = await _identify_thing_types({})

        assert result["success"] is False
        assert "thing_types" in result["error"]

    @pytest.mark.asyncio
    async def test_identify_thing_types_empty_array(self):
        """Test error handling for empty thing_types array."""
        args = {"thing_types": []}

        result = await _identify_thing_types(args)

        assert result["success"] is False
        assert "At least one" in result["error"]

    @pytest.mark.asyncio
    async def test_identify_thing_types_missing_required_field_in_type(self):
        """Test error handling when a thing type is missing required fields."""
        args = {
            "thing_types": [
                {
                    "name": "Person",
                    # Missing description and examples
                }
            ]
        }

        result = await _identify_thing_types(args)

        assert result["success"] is False
        assert "description" in result["error"] or "examples" in result["error"]

    @pytest.mark.asyncio
    async def test_identify_thing_types_invalid_type_format(self):
        """Test error handling when thing_types contains non-objects."""
        args = {"thing_types": ["Person", "Organization"]}

        result = await _identify_thing_types(args)

        assert result["success"] is False
        assert "must be an object" in result["error"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# IDENTIFY CONNECTION TYPES TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestIdentifyConnectionTypes:
    """Tests for identify_connection_types tool."""

    @pytest.mark.asyncio
    async def test_identify_connection_types_success(self):
        """Test successful connection type identification."""
        args = {
            "connection_types": [
                {
                    "name": "worked_for",
                    "display_name": "worked for",
                    "description": "Employment relationship between person and organization",
                    "examples": [["Dr. Gottlieb", "CIA"]],
                    "directional": True,
                },
                {
                    "name": "funded_by",
                    "display_name": "funded by",
                    "description": "Financial support relationship",
                },
            ]
        }

        result = await _identify_connection_types(args)

        assert "content" in result
        assert "2 connection types" in result["content"][0]["text"]
        assert "worked for" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_identify_connection_types_creates_connection_type_objects(self):
        """Test that tool stores normalized connection type data in collector."""
        args = {
            "connection_types": [
                {
                    "name": "led_by",
                    "display_name": "led by",
                    "description": "Leadership relationship",
                    "examples": [["Project MKULTRA", "Dr. Gottlieb"]],
                },
                {
                    "name": "collaborated_with",
                    "display_name": "collaborated with",
                    "description": "Collaboration between entities",
                    "directional": False,
                },
            ]
        }

        await _identify_connection_types(args)

        bootstrap_data = get_bootstrap_data()
        assert "identify_connection_types" in bootstrap_data

        connection_types = bootstrap_data["identify_connection_types"]
        assert len(connection_types) == 2

        # Check first type defaults and example conversion
        led_by = connection_types[0]
        assert led_by["name"] == "led_by"
        assert led_by["display_name"] == "led by"
        assert led_by["directional"] is True  # Default
        assert isinstance(led_by["examples"], list)

        # Check second type with explicit directional=False
        collab = connection_types[1]
        assert collab["directional"] is False

    @pytest.mark.asyncio
    async def test_identify_connection_types_error_handling_missing_field(self):
        """Test error handling for missing required fields."""
        result = await _identify_connection_types({})

        assert result["success"] is False
        assert "connection_types" in result["error"]

    @pytest.mark.asyncio
    async def test_identify_connection_types_empty_array(self):
        """Test error handling for empty connection_types array."""
        args = {"connection_types": []}

        result = await _identify_connection_types(args)

        assert result["success"] is False
        assert "At least one" in result["error"]

    @pytest.mark.asyncio
    async def test_identify_connection_types_missing_required_in_type(self):
        """Test error handling when a connection type is missing required fields."""
        args = {
            "connection_types": [
                {
                    "name": "worked_for",
                    # Missing display_name and description
                }
            ]
        }

        result = await _identify_connection_types(args)

        assert result["success"] is False
        assert "display_name" in result["error"] or "description" in result["error"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# IDENTIFY SEED ENTITIES TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestIdentifySeedEntities:
    """Tests for identify_seed_entities tool."""

    @pytest.mark.asyncio
    async def test_identify_seed_entities_success(self):
        """Test successful seed entity identification."""
        args = {
            "seed_entities": [
                {
                    "label": "CIA",
                    "thing_type": "Organization",
                    "aliases": ["Central Intelligence Agency", "The Agency"],
                    "description": "US intelligence agency",
                },
                {
                    "label": "Dr. Sidney Gottlieb",
                    "thing_type": "Person",
                },
            ]
        }

        result = await _identify_seed_entities(args)

        assert "content" in result
        assert "2 seed entities" in result["content"][0]["text"]
        assert "CIA" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_identify_seed_entities_creates_seed_entity_objects(self):
        """Test that tool stores normalized seed entity data in collector."""
        args = {
            "seed_entities": [
                {
                    "label": "MKULTRA",
                    "thing_type": "Project",
                    "aliases": ["MK-ULTRA", "MK Ultra"],
                    "description": "CIA mind control program",
                },
                {
                    "label": "Frank Olson",
                    "thing_type": "Person",
                },
            ]
        }

        await _identify_seed_entities(args)

        bootstrap_data = get_bootstrap_data()
        assert "identify_seed_entities" in bootstrap_data

        entities = bootstrap_data["identify_seed_entities"]
        assert len(entities) == 2

        # Check first entity with all fields
        mkultra = entities[0]
        assert mkultra["label"] == "MKULTRA"
        assert mkultra["thing_type"] == "Project"
        assert "MK-ULTRA" in mkultra["aliases"]
        assert mkultra["confidence"] == 1.0  # Seed entities have high confidence

        # Check second entity with defaults
        olson = entities[1]
        assert olson["label"] == "Frank Olson"
        assert olson["aliases"] == []
        assert olson["description"] is None
        assert olson["confidence"] == 1.0

    @pytest.mark.asyncio
    async def test_identify_seed_entities_error_handling(self):
        """Test error handling for missing required field."""
        result = await _identify_seed_entities({})

        assert result["success"] is False
        assert "seed_entities" in result["error"]

    @pytest.mark.asyncio
    async def test_identify_seed_entities_empty_array(self):
        """Test error handling for empty seed_entities array."""
        args = {"seed_entities": []}

        result = await _identify_seed_entities(args)

        assert result["success"] is False
        assert "At least one" in result["error"]

    @pytest.mark.asyncio
    async def test_identify_seed_entities_missing_required_in_entity(self):
        """Test error handling when seed entity is missing required fields."""
        args = {
            "seed_entities": [
                {
                    "label": "CIA",
                    # Missing thing_type
                }
            ]
        }

        result = await _identify_seed_entities(args)

        assert result["success"] is False
        assert "thing_type" in result["error"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GENERATE EXTRACTION CONTEXT TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestGenerateExtractionContext:
    """Tests for generate_extraction_context tool."""

    @pytest.mark.asyncio
    async def test_generate_extraction_context_success(self):
        """Test successful extraction context generation."""
        context = (
            "This domain covers CIA research programs from the 1950s-1970s. "
            "Key terminology: 'The Agency' refers to CIA, 'Subproject' refers to "
            "individual MKULTRA experiments. Always use canonical names for "
            "organizations (CIA not 'the Company')."
        )
        args = {"context": context}

        result = await _generate_extraction_context(args)

        assert "content" in result
        assert "Extraction context generated" in result["content"][0]["text"]
        assert f"{len(context)} chars" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_generate_extraction_context_stores_data(self):
        """Test that tool stores context in bootstrap collector."""
        context = (
            "Domain-specific guidance for extraction: Look for person-organization "
            "relationships, project hierarchies, and document references. "
            "Disambiguate common abbreviations."
        )
        args = {"context": context}

        await _generate_extraction_context(args)

        bootstrap_data = get_bootstrap_data()
        assert "generate_extraction_context" in bootstrap_data
        assert bootstrap_data["generate_extraction_context"] == context

    @pytest.mark.asyncio
    async def test_generate_extraction_context_error_missing_field(self):
        """Test error handling for missing context field."""
        result = await _generate_extraction_context({})

        assert result["success"] is False
        assert "context" in result["error"]

    @pytest.mark.asyncio
    async def test_generate_extraction_context_error_too_short(self):
        """Test error handling when context is too short."""
        args = {"context": "Too short"}

        result = await _generate_extraction_context(args)

        assert result["success"] is False
        assert "at least 50 characters" in result["error"]

    @pytest.mark.asyncio
    async def test_generate_extraction_context_error_wrong_type(self):
        """Test error handling when context is not a string."""
        args = {"context": 12345}

        result = await _generate_extraction_context(args)

        assert result["success"] is False
        assert "string" in result["error"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FINALIZE DOMAIN PROFILE TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestFinalizeDomainProfile:
    """Tests for finalize_domain_profile tool."""

    @pytest.mark.asyncio
    async def test_finalize_domain_profile_success(self):
        """Test successful domain profile finalization."""
        args = {
            "name": "CIA Mind Control Research",
            "description": "A comprehensive knowledge graph covering the CIA's MKULTRA "
            "program and related mind control research from the Cold War era.",
            "confidence": 0.85,
        }

        result = await _finalize_domain_profile(args)

        assert "content" in result
        assert "Domain profile finalized" in result["content"][0]["text"]
        assert "CIA Mind Control Research" in result["content"][0]["text"]
        assert "85%" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_finalize_domain_profile_includes_confidence(self):
        """Test that finalization stores confidence value correctly."""
        args = {
            "name": "SpaceX History",
            "description": "Knowledge graph about SpaceX development and missions.",
            "confidence": 0.92,
        }

        await _finalize_domain_profile(args)

        bootstrap_data = get_bootstrap_data()
        assert "finalize_domain_profile" in bootstrap_data

        stored = bootstrap_data["finalize_domain_profile"]
        assert stored["name"] == "SpaceX History"
        assert stored["confidence"] == 0.92
        assert isinstance(stored["confidence"], float)

    @pytest.mark.asyncio
    async def test_finalize_domain_profile_error_missing_name(self):
        """Test error handling for missing name field."""
        args = {
            "description": "A valid description for the profile.",
            "confidence": 0.8,
        }

        result = await _finalize_domain_profile(args)

        assert result["success"] is False
        assert "name" in result["error"]

    @pytest.mark.asyncio
    async def test_finalize_domain_profile_error_short_name(self):
        """Test error handling for name that is too short."""
        args = {
            "name": "AB",  # Less than 3 characters
            "description": "A valid description for the profile.",
            "confidence": 0.8,
        }

        result = await _finalize_domain_profile(args)

        assert result["success"] is False
        assert "name" in result["error"]

    @pytest.mark.asyncio
    async def test_finalize_domain_profile_error_short_description(self):
        """Test error handling for description that is too short."""
        args = {
            "name": "Valid Name",
            "description": "Too short",  # Less than 20 characters
            "confidence": 0.8,
        }

        result = await _finalize_domain_profile(args)

        assert result["success"] is False
        assert "description" in result["error"]

    @pytest.mark.asyncio
    async def test_finalize_domain_profile_error_invalid_confidence(self):
        """Test error handling for confidence outside valid range."""
        args = {
            "name": "Valid Name",
            "description": "A valid description for the profile.",
            "confidence": 1.5,  # Greater than 1.0
        }

        result = await _finalize_domain_profile(args)

        assert result["success"] is False
        assert "confidence" in result["error"]

    @pytest.mark.asyncio
    async def test_finalize_domain_profile_error_negative_confidence(self):
        """Test error handling for negative confidence value."""
        args = {
            "name": "Valid Name",
            "description": "A valid description for the profile.",
            "confidence": -0.5,
        }

        result = await _finalize_domain_profile(args)

        assert result["success"] is False
        assert "confidence" in result["error"]

    @pytest.mark.asyncio
    async def test_finalize_domain_profile_accepts_integer_confidence(self):
        """Test that integer confidence values are accepted and converted to float."""
        args = {
            "name": "Test Domain",
            "description": "A valid description for the profile.",
            "confidence": 1,  # Integer instead of float
        }

        result = await _finalize_domain_profile(args)

        assert "content" in result
        bootstrap_data = get_bootstrap_data()
        assert bootstrap_data["finalize_domain_profile"]["confidence"] == 1.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCP SERVER CREATION TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestMCPServerCreation:
    """Tests for MCP server factory and tool registration."""

    def test_create_bootstrap_mcp_server(self):
        """Test that create_bootstrap_mcp_server returns a valid MCP server."""
        server = create_bootstrap_mcp_server()

        # Server should be created successfully
        assert server is not None
        # Server should have a name attribute (SDK pattern)
        # The exact attributes depend on SDK implementation

    def test_bootstrap_tool_names_list(self):
        """Test that BOOTSTRAP_TOOL_NAMES contains all expected tools."""
        expected_tool_names = [
            "mcp__kg-bootstrap__analyze_content_domain",
            "mcp__kg-bootstrap__identify_thing_types",
            "mcp__kg-bootstrap__identify_connection_types",
            "mcp__kg-bootstrap__identify_seed_entities",
            "mcp__kg-bootstrap__generate_extraction_context",
            "mcp__kg-bootstrap__finalize_domain_profile",
        ]

        assert BOOTSTRAP_TOOL_NAMES == expected_tool_names
        assert len(BOOTSTRAP_TOOL_NAMES) == 6

    def test_bootstrap_tools_list_contains_all_tools(self):
        """Test that BOOTSTRAP_TOOLS list contains all SdkMcpTool objects."""
        assert len(BOOTSTRAP_TOOLS) == 6

        # Verify tool names (SdkMcpTool objects have a 'name' attribute)
        tool_names = [
            "analyze_content_domain",
            "identify_thing_types",
            "identify_connection_types",
            "identify_seed_entities",
            "generate_extraction_context",
            "finalize_domain_profile",
        ]

        for tool, expected_name in zip(BOOTSTRAP_TOOLS, tool_names):
            # SdkMcpTool has a 'name' attribute, not __name__
            assert tool.name == expected_name

    def test_tool_names_follow_mcp_pattern(self):
        """Test that tool names follow MCP naming convention."""
        for tool_name in BOOTSTRAP_TOOL_NAMES:
            # Should follow pattern: mcp__<server-name>__<tool-name>
            assert tool_name.startswith("mcp__kg-bootstrap__")
            parts = tool_name.split("__")
            assert len(parts) == 3
            assert parts[0] == "mcp"
            assert parts[1] == "kg-bootstrap"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BOOTSTRAP COLLECTOR TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestBootstrapCollector:
    """Tests for bootstrap data collection utilities."""

    def test_clear_bootstrap_collector(self):
        """Test that clear_bootstrap_collector empties the collector."""
        # The fixture already clears, but verify behavior
        bootstrap_data = get_bootstrap_data()
        assert bootstrap_data == {}

    @pytest.mark.asyncio
    async def test_collector_accumulates_data_across_tools(self):
        """Test that multiple tool calls accumulate data in collector."""
        # Call first tool
        await _analyze_content_domain(
            {
                "content_type": "documentary",
                "domain": "history",
                "topic_summary": "A documentary about historical events and their impact.",
                "key_themes": ["history", "events"],
                "complexity": "simple",
            }
        )

        # Call second tool
        await _identify_thing_types(
            {
                "thing_types": [
                    {
                        "name": "Person",
                        "description": "Individual",
                        "examples": ["John Doe"],
                    }
                ]
            }
        )

        # Verify both are in collector
        bootstrap_data = get_bootstrap_data()
        assert "analyze_content_domain" in bootstrap_data
        assert "identify_thing_types" in bootstrap_data

    def test_get_bootstrap_data_returns_copy(self):
        """Test that get_bootstrap_data returns a copy, not the original."""
        data1 = get_bootstrap_data()
        data2 = get_bootstrap_data()

        # Modifying one should not affect the other
        data1["test_key"] = "test_value"
        assert "test_key" not in data2
