"""
Tests for Knowledge Graph Service — Extraction functionality.

This module tests the extraction-related methods of KnowledgeGraphService:
- extract_from_transcript (with mocked ClaudeSDKClient)
- _apply_extraction_to_kb
- _get_or_create_kb
- export_graph
- get_graph_stats

Uses tmp_path fixture for isolated test directories.
All tests are async using @pytest.mark.asyncio.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.kg.domain import (
    ConnectionType,
    DomainProfile,
    ProjectState,
    SeedEntity,
    ThingType,
)
from app.kg.knowledge_base import KnowledgeBase
from app.kg.models import Node, Source, SourceType
from app.kg.persistence import save_knowledge_base
from app.kg.schemas import (
    ExtractedDiscovery,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)
from app.services.kg_service import KnowledgeGraphService


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIXTURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.fixture
def kg_service(tmp_path: Path) -> KnowledgeGraphService:
    """Create a KnowledgeGraphService with isolated tmp_path directory."""
    return KnowledgeGraphService(data_path=tmp_path)


@pytest.fixture
def sample_domain_profile() -> DomainProfile:
    """Create a sample DomainProfile for testing extraction."""
    return DomainProfile(
        name="Test Domain",
        description="A test domain for unit testing purposes",
        thing_types=[
            ThingType(
                name="Person",
                description="A human individual",
                examples=["Alice", "Bob"],
                priority=1,
            ),
            ThingType(
                name="Organization",
                description="A company or institution",
                examples=["ACME Corp"],
                priority=2,
            ),
        ],
        connection_types=[
            ConnectionType(
                name="works_for",
                display_name="works for",
                description="Employment relationship",
                examples=[("Alice", "ACME Corp")],
            ),
            ConnectionType(
                name="collaborated_with",
                display_name="collaborated with",
                description="Professional collaboration",
                examples=[("Alice", "Bob")],
            ),
        ],
        seed_entities=[
            SeedEntity(
                label="Alice",
                thing_type="Person",
                aliases=["Alice Smith"],
                description="Main protagonist",
            ),
        ],
        extraction_context="Extract entities and relationships from test content.",
        bootstrap_confidence=0.85,
        bootstrapped_from="source123",
    )


@pytest.fixture
def sample_extraction_result() -> ExtractionResult:
    """Create a sample ExtractionResult for testing."""
    return ExtractionResult(
        entities=[
            ExtractedEntity(
                label="John Doe",
                entity_type="Person",
                aliases=["JD", "Johnny"],
                description="A test person",
            ),
            ExtractedEntity(
                label="TechCorp",
                entity_type="Organization",
                aliases=["Tech Corporation"],
                description="A technology company",
            ),
        ],
        relationships=[
            ExtractedRelationship(
                source_label="John Doe",
                target_label="TechCorp",
                relationship_type="works_for",
                confidence=0.95,
                evidence="John Doe has been employed at TechCorp since 2020.",
            ),
        ],
        discoveries=[
            ExtractedDiscovery(
                discovery_type="thing_type",
                name="Product",
                display_name="Product",
                description="A commercial product or service",
                examples=["Widget X", "Service Y"],
            ),
        ],
        summary="Extracted 2 entities and 1 relationship from the transcript.",
    )


@pytest.fixture
def sample_knowledge_base(sample_domain_profile: DomainProfile) -> KnowledgeBase:
    """Create a sample KnowledgeBase with some initial data."""
    kb = KnowledgeBase(
        name="Test KB",
        description="A test knowledge base",
        domain_profile=sample_domain_profile,
    )

    # Add some initial nodes
    kb.add_node(Node(label="Alice", entity_type="Person", description="Initial person"))
    kb.add_node(Node(label="ACME Corp", entity_type="Organization"))

    # Add a source
    kb.add_source(
        Source(id="initial_source", title="Initial Video", source_type=SourceType.VIDEO)
    )

    return kb


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EXTRACT FROM TRANSCRIPT TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestExtractFromTranscript:
    """Tests for extract_from_transcript with mocked Claude client."""

    @pytest.mark.asyncio
    async def test_extract_project_not_found(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that extraction raises ValueError for non-existent project."""
        with pytest.raises(ValueError, match="not found"):
            await kg_service.extract_from_transcript(
                project_id="nonexistent12",
                transcript="Some transcript content",
                title="Test Video",
                source_id="source123",
            )

    @pytest.mark.asyncio
    async def test_extract_no_domain_profile(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that extraction raises ValueError when project has no domain profile."""
        project = await kg_service.create_project("No Profile Project")

        with pytest.raises(ValueError, match="no domain profile"):
            await kg_service.extract_from_transcript(
                project_id=project.id,
                transcript="Some transcript content",
                title="Test Video",
                source_id="source123",
            )

    @pytest.mark.asyncio
    async def test_extract_success_returns_stats(
        self,
        kg_service: KnowledgeGraphService,
        sample_domain_profile: DomainProfile,
        sample_extraction_result: ExtractionResult,
    ) -> None:
        """Test successful extraction returns correct statistics."""
        # Create project with domain profile
        project = await kg_service.create_project("Extraction Test")
        project.domain_profile = sample_domain_profile
        project.state = ProjectState.ACTIVE
        await kg_service._save_project(project)

        # Mock the Claude client and extraction result
        with patch("app.services.kg_service.ClaudeSDKClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.query = AsyncMock()

            # Mock receive_response to return a ResultMessage with extraction data
            from claude_agent_sdk import ResultMessage

            mock_result = MagicMock(spec=ResultMessage)
            mock_result.is_error = False
            mock_result.num_turns = 2
            mock_result.total_cost_usd = 0.005
            mock_result.tool_results = [
                {"_extraction_result": sample_extraction_result.model_dump()}
            ]

            async def mock_receive():
                yield mock_result

            mock_client.receive_response = mock_receive
            mock_client_class.return_value = mock_client

            result = await kg_service.extract_from_transcript(
                project_id=project.id,
                transcript="John Doe works at TechCorp since 2020...",
                title="Interview Video",
                source_id="video456",
            )

        # Verify result statistics
        assert result["entities_extracted"] == 2
        assert result["relationships_extracted"] == 1
        assert result["discoveries"] == 1
        assert result["summary"] is not None

    @pytest.mark.asyncio
    async def test_extract_updates_project_stats(
        self,
        kg_service: KnowledgeGraphService,
        sample_domain_profile: DomainProfile,
        sample_extraction_result: ExtractionResult,
    ) -> None:
        """Test that extraction updates project statistics."""
        # Create project with domain profile
        project = await kg_service.create_project("Stats Update Test")
        project.domain_profile = sample_domain_profile
        project.state = ProjectState.ACTIVE
        await kg_service._save_project(project)

        with patch("app.services.kg_service.ClaudeSDKClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.query = AsyncMock()

            from claude_agent_sdk import ResultMessage

            mock_result = MagicMock(spec=ResultMessage)
            mock_result.is_error = False
            mock_result.num_turns = 2
            mock_result.total_cost_usd = 0.005
            mock_result.tool_results = [
                {"_extraction_result": sample_extraction_result.model_dump()}
            ]

            async def mock_receive():
                yield mock_result

            mock_client.receive_response = mock_receive
            mock_client_class.return_value = mock_client

            await kg_service.extract_from_transcript(
                project_id=project.id,
                transcript="Test transcript content",
                title="Test Video",
                source_id="video789",
            )

        # Verify project was updated
        updated_project = await kg_service.get_project(project.id)
        assert updated_project is not None
        assert updated_project.thing_count >= 2  # At least the extracted entities
        assert updated_project.connection_count >= 1
        assert updated_project.source_count >= 1
        assert updated_project.kb_id is not None

    @pytest.mark.asyncio
    async def test_extract_adds_discoveries_to_pending(
        self,
        kg_service: KnowledgeGraphService,
        sample_domain_profile: DomainProfile,
        sample_extraction_result: ExtractionResult,
    ) -> None:
        """Test that discoveries are added to pending confirmations."""
        project = await kg_service.create_project("Discovery Test")
        project.domain_profile = sample_domain_profile
        project.state = ProjectState.ACTIVE
        await kg_service._save_project(project)

        with patch("app.services.kg_service.ClaudeSDKClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.query = AsyncMock()

            from claude_agent_sdk import ResultMessage

            mock_result = MagicMock(spec=ResultMessage)
            mock_result.is_error = False
            mock_result.num_turns = 2
            mock_result.total_cost_usd = 0.005
            mock_result.tool_results = [
                {"_extraction_result": sample_extraction_result.model_dump()}
            ]

            async def mock_receive():
                yield mock_result

            mock_client.receive_response = mock_receive
            mock_client_class.return_value = mock_client

            await kg_service.extract_from_transcript(
                project_id=project.id,
                transcript="Test transcript",
                title="Test Video",
                source_id="video_disc",
            )

        # Verify discoveries were added
        updated_project = await kg_service.get_project(project.id)
        assert updated_project is not None
        assert len(updated_project.pending_discoveries) == 1
        assert updated_project.pending_discoveries[0].name == "Product"
        assert updated_project.pending_discoveries[0].found_in_source == "video_disc"

    @pytest.mark.asyncio
    async def test_extract_agent_error_raises_runtime_error(
        self,
        kg_service: KnowledgeGraphService,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """Test that agent errors are propagated as RuntimeError."""
        project = await kg_service.create_project("Error Test")
        project.domain_profile = sample_domain_profile
        project.state = ProjectState.ACTIVE
        await kg_service._save_project(project)

        with patch("app.services.kg_service.ClaudeSDKClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.query = AsyncMock()

            from claude_agent_sdk import ResultMessage

            mock_result = MagicMock(spec=ResultMessage)
            mock_result.is_error = True
            mock_result.result = "Agent failed to process content"

            async def mock_receive():
                yield mock_result

            mock_client.receive_response = mock_receive
            mock_client_class.return_value = mock_client

            with pytest.raises(RuntimeError, match="Extraction agent error"):
                await kg_service.extract_from_transcript(
                    project_id=project.id,
                    transcript="Test transcript",
                    title="Test Video",
                    source_id="error_source",
                )

    @pytest.mark.asyncio
    async def test_extract_no_result_raises_value_error(
        self,
        kg_service: KnowledgeGraphService,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """Test that missing extraction result raises ValueError."""
        project = await kg_service.create_project("No Result Test")
        project.domain_profile = sample_domain_profile
        project.state = ProjectState.ACTIVE
        await kg_service._save_project(project)

        with patch("app.services.kg_service.ClaudeSDKClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.query = AsyncMock()

            from claude_agent_sdk import ResultMessage

            mock_result = MagicMock(spec=ResultMessage)
            mock_result.is_error = False
            mock_result.num_turns = 2
            mock_result.total_cost_usd = 0.005
            mock_result.tool_results = None  # No extraction result

            async def mock_receive():
                yield mock_result

            mock_client.receive_response = mock_receive
            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError, match="no results returned"):
                await kg_service.extract_from_transcript(
                    project_id=project.id,
                    transcript="Test transcript",
                    title="Test Video",
                    source_id="no_result_source",
                )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# APPLY EXTRACTION TO KB TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestApplyExtractionToKB:
    """Tests for _apply_extraction_to_kb method."""

    def test_apply_adds_entities_as_nodes(
        self,
        kg_service: KnowledgeGraphService,
        sample_knowledge_base: KnowledgeBase,
        sample_extraction_result: ExtractionResult,
    ) -> None:
        """Test that extracted entities are added as nodes to the KB."""
        initial_node_count = len(sample_knowledge_base._nodes)

        kg_service._apply_extraction_to_kb(
            sample_knowledge_base,
            sample_extraction_result,
            source_id="test_source",
        )

        # Should have added 2 new nodes (John Doe, TechCorp)
        assert len(sample_knowledge_base._nodes) == initial_node_count + 2

        # Verify nodes exist
        john = sample_knowledge_base.get_node_by_label("John Doe")
        assert john is not None
        assert john.entity_type == "Person"
        assert "JD" in john.aliases
        assert "Johnny" in john.aliases

        techcorp = sample_knowledge_base.get_node_by_label("TechCorp")
        assert techcorp is not None
        assert techcorp.entity_type == "Organization"

    def test_apply_adds_relationships_as_edges(
        self,
        kg_service: KnowledgeGraphService,
        sample_knowledge_base: KnowledgeBase,
        sample_extraction_result: ExtractionResult,
    ) -> None:
        """Test that extracted relationships are added as edges."""
        initial_edge_count = len(sample_knowledge_base._edges)

        kg_service._apply_extraction_to_kb(
            sample_knowledge_base,
            sample_extraction_result,
            source_id="test_source",
        )

        # Should have added 1 edge (John Doe -> TechCorp)
        assert len(sample_knowledge_base._edges) == initial_edge_count + 1

        # Find the edge
        john = sample_knowledge_base.get_node_by_label("John Doe")
        techcorp = sample_knowledge_base.get_node_by_label("TechCorp")
        assert john is not None
        assert techcorp is not None

        edge = sample_knowledge_base.get_edge_between(john.id, techcorp.id)
        assert edge is not None
        assert edge.has_relationship("works_for")

        # Verify relationship details
        rel = edge.relationships[0]
        assert rel.confidence == 0.95
        assert rel.evidence is not None
        assert rel.source_id == "test_source"

    def test_apply_tracks_source_on_nodes(
        self,
        kg_service: KnowledgeGraphService,
        sample_knowledge_base: KnowledgeBase,
        sample_extraction_result: ExtractionResult,
    ) -> None:
        """Test that nodes track the source they came from."""
        kg_service._apply_extraction_to_kb(
            sample_knowledge_base,
            sample_extraction_result,
            source_id="extraction_source_42",
        )

        john = sample_knowledge_base.get_node_by_label("John Doe")
        assert john is not None
        assert "extraction_source_42" in john.source_ids

    def test_apply_handles_existing_entity_with_new_aliases(
        self,
        kg_service: KnowledgeGraphService,
        sample_knowledge_base: KnowledgeBase,
    ) -> None:
        """Test that extraction merges aliases for existing entities."""
        # Create extraction result with existing entity but new aliases
        result = ExtractionResult(
            entities=[
                ExtractedEntity(
                    label="Alice",  # Already exists in sample_knowledge_base
                    entity_type="Person",
                    aliases=["Ali", "Alice Johnson"],  # New aliases
                    description="Updated description",
                ),
            ],
            relationships=[],
            discoveries=[],
        )

        kg_service._apply_extraction_to_kb(
            sample_knowledge_base,
            result,
            source_id="new_source",
        )

        alice = sample_knowledge_base.get_node_by_label("Alice")
        assert alice is not None
        # New aliases should be added
        assert "Ali" in alice.aliases
        assert "Alice Johnson" in alice.aliases

    def test_apply_empty_extraction_result(
        self,
        kg_service: KnowledgeGraphService,
        sample_knowledge_base: KnowledgeBase,
    ) -> None:
        """Test that empty extraction result doesn't cause errors."""
        initial_node_count = len(sample_knowledge_base._nodes)
        initial_edge_count = len(sample_knowledge_base._edges)

        empty_result = ExtractionResult(
            entities=[],
            relationships=[],
            discoveries=[],
        )

        kg_service._apply_extraction_to_kb(
            sample_knowledge_base,
            empty_result,
            source_id="empty_source",
        )

        # Counts should remain the same
        assert len(sample_knowledge_base._nodes) == initial_node_count
        assert len(sample_knowledge_base._edges) == initial_edge_count


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET OR CREATE KB TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestGetOrCreateKB:
    """Tests for _get_or_create_kb method."""

    @pytest.mark.asyncio
    async def test_creates_new_kb_when_no_kb_id(
        self,
        kg_service: KnowledgeGraphService,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """Test that a new KB is created when project has no kb_id."""
        project = await kg_service.create_project("New KB Project")
        project.domain_profile = sample_domain_profile
        await kg_service._save_project(project)

        kb = await kg_service._get_or_create_kb(project)

        assert kb is not None
        assert kb.name == project.name
        assert kb.domain_profile == sample_domain_profile

    @pytest.mark.asyncio
    async def test_loads_existing_kb_when_kb_id_exists(
        self,
        kg_service: KnowledgeGraphService,
        tmp_path: Path,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """Test that existing KB is loaded when project has kb_id."""
        # Create and save a KB first
        existing_kb = KnowledgeBase(
            name="Existing KB",
            description="Pre-existing knowledge base",
            domain_profile=sample_domain_profile,
        )
        existing_kb.add_node(Node(label="Existing Node", entity_type="Person"))
        save_knowledge_base(existing_kb, kg_service.kb_path)

        # Create project with kb_id pointing to existing KB
        project = await kg_service.create_project("Existing KB Project")
        project.domain_profile = sample_domain_profile
        project.kb_id = existing_kb.id
        await kg_service._save_project(project)

        kb = await kg_service._get_or_create_kb(project)

        assert kb is not None
        assert kb.id == existing_kb.id
        assert kb.name == "Existing KB"
        # Verify the node was loaded
        assert kb.get_node_by_label("Existing Node") is not None

    @pytest.mark.asyncio
    async def test_creates_new_kb_when_kb_id_not_found(
        self,
        kg_service: KnowledgeGraphService,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """Test that new KB is created when kb_id points to non-existent KB."""
        project = await kg_service.create_project("Missing KB Project")
        project.domain_profile = sample_domain_profile
        project.kb_id = "nonexistent_kb"  # Points to non-existent KB
        await kg_service._save_project(project)

        kb = await kg_service._get_or_create_kb(project)

        assert kb is not None
        # Should be a new KB since the old one wasn't found
        assert kb.id != "nonexistent_kb"
        assert kb.name == project.name


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EXPORT GRAPH TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestExportGraph:
    """Tests for export_graph method."""

    @pytest.mark.asyncio
    async def test_export_graphml_creates_file(
        self,
        kg_service: KnowledgeGraphService,
        tmp_path: Path,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """Test that export_graph creates a GraphML file."""
        # Create project with KB
        project = await kg_service.create_project("Export Test")
        project.domain_profile = sample_domain_profile
        await kg_service._save_project(project)

        # Create and save a KB with some data
        kb = KnowledgeBase(
            name="Export KB",
            domain_profile=sample_domain_profile,
        )
        kb.add_node(Node(label="Node A", entity_type="Person"))
        kb.add_node(Node(label="Node B", entity_type="Organization"))
        kb.add_relationship("Node A", "Node B", "works_for", "source1")
        save_knowledge_base(kb, kg_service.kb_path)

        project.kb_id = kb.id
        await kg_service._save_project(project)

        # Export the graph
        output_path = await kg_service.export_graph(project.id, format="graphml")

        assert output_path is not None
        assert output_path.exists()
        assert output_path.suffix == ".graphml"

        # Verify file has content (basic check)
        content = output_path.read_text()
        assert "graphml" in content
        assert "Node A" in content
        assert "Node B" in content

    @pytest.mark.asyncio
    async def test_export_json_creates_file(
        self,
        kg_service: KnowledgeGraphService,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """Test that export_graph creates a JSON file when format=json."""
        project = await kg_service.create_project("JSON Export Test")
        project.domain_profile = sample_domain_profile
        await kg_service._save_project(project)

        # Create and save a KB
        kb = KnowledgeBase(name="JSON Export KB", domain_profile=sample_domain_profile)
        kb.add_node(Node(label="Test Node", entity_type="Person"))
        save_knowledge_base(kb, kg_service.kb_path)

        project.kb_id = kb.id
        await kg_service._save_project(project)

        output_path = await kg_service.export_graph(project.id, format="json")

        assert output_path is not None
        assert output_path.exists()
        assert output_path.suffix == ".json"

        # Verify JSON structure
        data = json.loads(output_path.read_text())
        assert "nodes" in data
        assert "edges" in data
        assert "sources" in data
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["label"] == "Test Node"

    @pytest.mark.asyncio
    async def test_export_returns_none_for_missing_project(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that export_graph returns None for non-existent project."""
        result = await kg_service.export_graph("nonexistent12")
        assert result is None

    @pytest.mark.asyncio
    async def test_export_returns_none_when_no_kb(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that export_graph returns None when project has no kb_id."""
        project = await kg_service.create_project("No KB Project")
        # Project has no kb_id

        result = await kg_service.export_graph(project.id)
        assert result is None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET GRAPH STATS TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestGetGraphStats:
    """Tests for get_graph_stats method."""

    @pytest.mark.asyncio
    async def test_get_stats_returns_correct_counts(
        self,
        kg_service: KnowledgeGraphService,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """Test that get_graph_stats returns correct node/edge/source counts."""
        project = await kg_service.create_project("Stats Test")
        project.domain_profile = sample_domain_profile
        await kg_service._save_project(project)

        # Create KB with known data
        kb = KnowledgeBase(name="Stats KB", domain_profile=sample_domain_profile)
        kb.add_node(Node(label="Person 1", entity_type="Person"))
        kb.add_node(Node(label="Person 2", entity_type="Person"))
        kb.add_node(Node(label="Org 1", entity_type="Organization"))
        kb.add_source(Source(id="src1", title="Source 1"))
        kb.add_source(Source(id="src2", title="Source 2"))
        kb.add_relationship("Person 1", "Org 1", "works_for", "src1")
        kb.add_relationship("Person 2", "Org 1", "works_for", "src2")
        save_knowledge_base(kb, kg_service.kb_path)

        project.kb_id = kb.id
        await kg_service._save_project(project)

        stats = await kg_service.get_graph_stats(project.id)

        assert stats is not None
        assert stats["node_count"] == 3
        assert stats["edge_count"] == 2
        assert stats["source_count"] == 2

    @pytest.mark.asyncio
    async def test_get_stats_returns_entity_type_breakdown(
        self,
        kg_service: KnowledgeGraphService,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """Test that get_graph_stats includes entity type breakdown."""
        project = await kg_service.create_project("Type Breakdown Test")
        project.domain_profile = sample_domain_profile
        await kg_service._save_project(project)

        kb = KnowledgeBase(name="Type KB", domain_profile=sample_domain_profile)
        kb.add_node(Node(label="Alice", entity_type="Person"))
        kb.add_node(Node(label="Bob", entity_type="Person"))
        kb.add_node(Node(label="Corp", entity_type="Organization"))
        save_knowledge_base(kb, kg_service.kb_path)

        project.kb_id = kb.id
        await kg_service._save_project(project)

        stats = await kg_service.get_graph_stats(project.id)

        assert stats is not None
        assert "entity_types" in stats
        assert stats["entity_types"]["Person"] == 2
        assert stats["entity_types"]["Organization"] == 1

    @pytest.mark.asyncio
    async def test_get_stats_returns_relationship_type_breakdown(
        self,
        kg_service: KnowledgeGraphService,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """Test that get_graph_stats includes relationship type breakdown."""
        project = await kg_service.create_project("Rel Breakdown Test")
        project.domain_profile = sample_domain_profile
        await kg_service._save_project(project)

        kb = KnowledgeBase(name="Rel KB", domain_profile=sample_domain_profile)
        kb.add_node(Node(label="Alice", entity_type="Person"))
        kb.add_node(Node(label="Bob", entity_type="Person"))
        kb.add_node(Node(label="Corp", entity_type="Organization"))
        kb.add_relationship("Alice", "Corp", "works_for", "src1")
        kb.add_relationship("Bob", "Corp", "works_for", "src1")
        kb.add_relationship("Alice", "Bob", "collaborated_with", "src1")
        save_knowledge_base(kb, kg_service.kb_path)

        project.kb_id = kb.id
        await kg_service._save_project(project)

        stats = await kg_service.get_graph_stats(project.id)

        assert stats is not None
        assert "relationship_types" in stats
        assert stats["relationship_types"]["works_for"] == 2
        assert stats["relationship_types"]["collaborated_with"] == 1

    @pytest.mark.asyncio
    async def test_get_stats_returns_none_for_missing_project(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that get_graph_stats returns None for non-existent project."""
        result = await kg_service.get_graph_stats("nonexistent12")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_stats_returns_none_when_no_kb(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that get_graph_stats returns None when project has no kb_id."""
        project = await kg_service.create_project("No KB Stats")

        result = await kg_service.get_graph_stats(project.id)
        assert result is None
