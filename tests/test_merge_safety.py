"""
Tests for Phase 2C: Merge Safety Controls.

Tests cover:
- MergeHistory safety fields populated correctly
- Idempotent merge (same request_id returns same result)
- Pre-merge state captured correctly
- Concurrent merge protection (lock)
- Conflict detection
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from app.kg.domain import DomainProfile, KGProject, ProjectState, ThingType
from app.kg.knowledge_base import KnowledgeBase
from app.kg.models import Edge, Node, RelationshipDetail
from app.kg.persistence import save_knowledge_base
from app.kg.resolution import MergeHistory, ResolutionCandidate
from app.services.kg_service import KnowledgeGraphService


@pytest.fixture
def kg_service(tmp_path: Path) -> KnowledgeGraphService:
    """Create a KnowledgeGraphService with temporary storage."""
    return KnowledgeGraphService(tmp_path)


@pytest.fixture
def sample_domain_profile() -> DomainProfile:
    """Create a sample domain profile for testing."""
    return DomainProfile(
        name="Test Domain",
        description="A test domain for entity resolution",
        thing_types=[
            ThingType(name="Person", description="A human being"),
            ThingType(name="Organization", description="A company or institution"),
        ],
    )


@pytest.fixture
async def project_with_kb(
    kg_service: KnowledgeGraphService, sample_domain_profile: DomainProfile
) -> KGProject:
    """Create a project with a knowledge base containing test nodes."""
    project = await kg_service.create_project("Test Project")
    project.domain_profile = sample_domain_profile
    project.state = ProjectState.ACTIVE

    # Create a knowledge base with test nodes
    kb = KnowledgeBase(
        name="Test KB",
        description="Test knowledge base",
        domain_profile=sample_domain_profile,
    )

    # Add test nodes
    node_a = Node(id="node_a", label="John Smith", entity_type="Person")
    node_b = Node(id="node_b", label="J. Smith", entity_type="Person", aliases=["Johnny"])
    node_c = Node(id="node_c", label="Acme Corp", entity_type="Organization")

    kb.add_node(node_a)
    kb.add_node(node_b)
    kb.add_node(node_c)

    # Add some relationships
    edge = Edge(source_node_id="node_a", target_node_id="node_c")
    edge.add_relationship(
        RelationshipDetail(
            relationship_type="works_for",
            source_id="source1",
            evidence="John works at Acme",
        )
    )
    kb.add_edge(edge)

    edge2 = Edge(source_node_id="node_b", target_node_id="node_c")
    edge2.add_relationship(
        RelationshipDetail(
            relationship_type="founded",
            source_id="source1",
            evidence="J. Smith founded Acme",
        )
    )
    kb.add_edge(edge2)

    # Save KB
    save_knowledge_base(kb, kg_service.kb_path)

    # Link project to KB
    project.kb_id = kb.id
    await kg_service._save_project(project)

    return project


class TestMergeHistorySafetyFields:
    """Test MergeHistory model safety fields."""

    def test_merge_history_has_new_safety_fields(self) -> None:
        """MergeHistory should have all new safety fields."""
        history = MergeHistory(
            survivor_id="node_a",
            merged_id="node_b",
            merged_label="J. Smith",
            confidence=0.95,
        )

        # Check new fields exist with defaults
        assert history.request_id is None
        assert history.pre_merge_state is None
        assert history.survivor_label_before is None
        assert history.survivor_aliases_before == []
        assert history.edges_redirected == 0

    def test_merge_history_with_safety_data(self) -> None:
        """MergeHistory should accept all safety fields."""
        pre_merge = {
            "survivor": {"id": "node_a", "label": "John Smith"},
            "merged": {"id": "node_b", "label": "J. Smith"},
            "edges": [{"id": "edge1", "source_node_id": "node_b"}],
        }

        history = MergeHistory(
            survivor_id="node_a",
            merged_id="node_b",
            merged_label="J. Smith",
            confidence=0.95,
            request_id="req_12345",
            pre_merge_state=pre_merge,
            survivor_label_before="John Smith",
            survivor_aliases_before=["Johnny", "J"],
            edges_redirected=3,
        )

        assert history.request_id == "req_12345"
        assert history.pre_merge_state == pre_merge
        assert history.survivor_label_before == "John Smith"
        assert history.survivor_aliases_before == ["Johnny", "J"]
        assert history.edges_redirected == 3

    def test_merge_history_serialization(self) -> None:
        """MergeHistory should serialize and deserialize correctly."""
        history = MergeHistory(
            survivor_id="node_a",
            merged_id="node_b",
            merged_label="J. Smith",
            confidence=0.95,
            request_id="req_test",
            pre_merge_state={"test": "data"},
            edges_redirected=5,
        )

        # Serialize
        data = history.model_dump()
        assert data["request_id"] == "req_test"
        assert data["pre_merge_state"] == {"test": "data"}
        assert data["edges_redirected"] == 5

        # Deserialize
        restored = MergeHistory.model_validate(data)
        assert restored.request_id == "req_test"
        assert restored.pre_merge_state == {"test": "data"}


class TestIdempotentMerge:
    """Test idempotent merge behavior."""

    @pytest.mark.asyncio
    async def test_idempotent_merge_returns_existing(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """Same request_id should return existing merge result."""
        project = project_with_kb
        request_id = "idempotent_request_123"

        # First merge
        history1 = await kg_service.merge_entities(
            project_id=project.id,
            survivor_id="node_a",
            merged_id="node_b",
            request_id=request_id,
        )

        assert history1.request_id == request_id
        initial_merge_id = history1.id

        # Second merge with same request_id should return same result
        history2 = await kg_service.merge_entities(
            project_id=project.id,
            survivor_id="node_a",
            merged_id="node_b",
            request_id=request_id,
        )

        assert history2.id == initial_merge_id
        assert history2.request_id == request_id

    @pytest.mark.asyncio
    async def test_different_request_id_creates_new_merge(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """Different request_ids should create separate merges."""
        project = project_with_kb

        # First merge
        history1 = await kg_service.merge_entities(
            project_id=project.id,
            survivor_id="node_a",
            merged_id="node_b",
            request_id="request_1",
        )

        # Add another node to merge
        from app.kg.persistence import load_knowledge_base

        kb = load_knowledge_base(kg_service.kb_path / project.kb_id)
        assert kb is not None
        new_node = Node(id="node_d", label="Another Person", entity_type="Person")
        kb.add_node(new_node)
        save_knowledge_base(kb, kg_service.kb_path)

        # Second merge with different request_id
        history2 = await kg_service.merge_entities(
            project_id=project.id,
            survivor_id="node_a",
            merged_id="node_d",
            request_id="request_2",
        )

        assert history1.id != history2.id
        assert history1.request_id != history2.request_id

    @pytest.mark.asyncio
    async def test_merge_without_request_id(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """Merge without request_id should still work."""
        project = project_with_kb

        history = await kg_service.merge_entities(
            project_id=project.id,
            survivor_id="node_a",
            merged_id="node_b",
        )

        assert history.request_id is None
        assert history.survivor_id == "node_a"
        assert history.merged_id == "node_b"


class TestPreMergeStateCapture:
    """Test pre-merge state capture for rollback."""

    @pytest.mark.asyncio
    async def test_pre_merge_state_captured(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """Pre-merge state should include survivor, merged, and edges."""
        project = project_with_kb

        history = await kg_service.merge_entities(
            project_id=project.id,
            survivor_id="node_a",
            merged_id="node_b",
            request_id="capture_test",
        )

        assert history.pre_merge_state is not None
        assert "survivor" in history.pre_merge_state
        assert "merged" in history.pre_merge_state
        assert "edges" in history.pre_merge_state

    @pytest.mark.asyncio
    async def test_survivor_state_captured_correctly(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """Survivor node state should be captured before merge."""
        project = project_with_kb

        history = await kg_service.merge_entities(
            project_id=project.id,
            survivor_id="node_a",
            merged_id="node_b",
        )

        assert history.survivor_label_before == "John Smith"
        assert history.survivor_aliases_before == []

        # Check pre_merge_state has survivor data
        survivor_data = history.pre_merge_state["survivor"]
        assert survivor_data["label"] == "John Smith"

    @pytest.mark.asyncio
    async def test_merged_node_state_captured(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """Merged node state should be captured for rollback."""
        project = project_with_kb

        history = await kg_service.merge_entities(
            project_id=project.id,
            survivor_id="node_a",
            merged_id="node_b",
        )

        merged_data = history.pre_merge_state["merged"]
        assert merged_data["label"] == "J. Smith"
        assert "Johnny" in merged_data["aliases"]

    @pytest.mark.asyncio
    async def test_edges_count_captured(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """Number of redirected edges should be captured."""
        project = project_with_kb

        history = await kg_service.merge_entities(
            project_id=project.id,
            survivor_id="node_a",
            merged_id="node_b",
        )

        # node_b had one edge (to node_c)
        assert history.edges_redirected == 1
        assert len(history.pre_merge_state["edges"]) == 1


class TestConcurrentMergeProtection:
    """Test concurrent merge protection via locks."""

    @pytest.mark.asyncio
    async def test_concurrent_merges_serialized(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """Concurrent merges on same nodes should be serialized."""
        project = project_with_kb

        # Track merge order
        merge_order: list[str] = []

        async def do_merge(req_id: str) -> None:
            try:
                await kg_service.merge_entities(
                    project_id=project.id,
                    survivor_id="node_a",
                    merged_id="node_b",
                    request_id=req_id,
                )
                merge_order.append(req_id)
            except ValueError:
                # Second merge will fail because node_b is already merged
                merge_order.append(f"{req_id}_failed")

        # Launch concurrent merges
        await asyncio.gather(
            do_merge("merge_1"),
            do_merge("merge_2"),
        )

        # One should succeed, one should fail or return idempotent result
        assert len(merge_order) == 2

    @pytest.mark.asyncio
    async def test_lock_cleanup_after_merge(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """Lock should be cleaned up after successful merge."""
        project = project_with_kb
        lock_key = f"{project.id}:node_a:node_b"

        # Lock should not exist before merge
        assert lock_key not in kg_service._pending_merges

        await kg_service.merge_entities(
            project_id=project.id,
            survivor_id="node_a",
            merged_id="node_b",
        )

        # Lock should be cleaned up after merge
        assert lock_key not in kg_service._pending_merges


class TestConflictDetection:
    """Test merge conflict detection."""

    @pytest.mark.asyncio
    async def test_conflict_project_not_found(
        self,
        kg_service: KnowledgeGraphService,
    ) -> None:
        """Conflict check should detect missing project."""
        result = await kg_service.check_merge_conflicts(
            project_id="nonexistent",
            candidate_id="any",
        )

        assert result["conflict"] is True
        assert "Project not found" in result["reason"]

    @pytest.mark.asyncio
    async def test_conflict_candidate_not_found(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """Conflict check should detect missing candidate."""
        project = project_with_kb

        result = await kg_service.check_merge_conflicts(
            project_id=project.id,
            candidate_id="nonexistent_candidate",
        )

        assert result["conflict"] is True
        assert "Candidate not found" in result["reason"]

    @pytest.mark.asyncio
    async def test_conflict_node_already_merged(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """Conflict check should detect already merged nodes."""
        project = project_with_kb

        # Add a pending candidate
        candidate = ResolutionCandidate(
            id="test_candidate",
            node_a_id="node_a",
            node_b_id="node_b",
            confidence=0.85,
        )
        project.pending_merges.append(candidate)
        await kg_service._save_project(project)

        # Merge the nodes first
        await kg_service.merge_entities(
            project_id=project.id,
            survivor_id="node_a",
            merged_id="node_b",
        )

        # Re-add candidate to test (since merge removes it)
        project = await kg_service.get_project(project.id)
        assert project is not None
        project.pending_merges.append(candidate)
        await kg_service._save_project(project)

        # Check conflicts - node_b no longer exists
        result = await kg_service.check_merge_conflicts(
            project_id=project.id,
            candidate_id="test_candidate",
        )

        assert result["conflict"] is True
        assert "already merged" in result["reason"]

    @pytest.mark.asyncio
    async def test_warning_high_impact_merge(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """High-impact merges should generate warnings."""
        project = project_with_kb
        from app.kg.persistence import load_knowledge_base

        kb = load_knowledge_base(kg_service.kb_path / project.kb_id)
        assert kb is not None

        # Add many edges to node_a to make it high-impact
        for i in range(10):
            new_node = Node(id=f"extra_{i}", label=f"Extra {i}", entity_type="Person")
            kb.add_node(new_node)
            edge = Edge(source_node_id="node_a", target_node_id=f"extra_{i}")
            edge.add_relationship(
                RelationshipDetail(
                    relationship_type="knows",
                    source_id="source1",
                )
            )
            kb.add_edge(edge)

        save_knowledge_base(kb, kg_service.kb_path)

        # Add a pending candidate
        candidate = ResolutionCandidate(
            id="high_impact_candidate",
            node_a_id="node_a",
            node_b_id="node_b",
            confidence=0.85,
        )
        project.pending_merges.append(candidate)
        await kg_service._save_project(project)

        # Check conflicts
        result = await kg_service.check_merge_conflicts(
            project_id=project.id,
            candidate_id="high_impact_candidate",
        )

        assert result["conflict"] is False
        assert result["warning"] is True
        assert "High-impact" in result["reason"]
        assert "relationships affected" in result["reason"]

    @pytest.mark.asyncio
    async def test_no_conflict_low_impact_merge(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """Low-impact merges should not have conflicts or warnings."""
        project = project_with_kb

        # Add a pending candidate
        candidate = ResolutionCandidate(
            id="low_impact_candidate",
            node_a_id="node_a",
            node_b_id="node_b",
            confidence=0.85,
        )
        project.pending_merges.append(candidate)
        await kg_service._save_project(project)

        # Check conflicts
        result = await kg_service.check_merge_conflicts(
            project_id=project.id,
            candidate_id="low_impact_candidate",
        )

        assert result["conflict"] is False
        assert result.get("warning", False) is False


class TestFindMergeByRequestId:
    """Test the _find_merge_by_request_id helper."""

    @pytest.mark.asyncio
    async def test_find_existing_merge(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """Should find merge by request_id."""
        project = project_with_kb
        request_id = "find_test_123"

        # Create a merge
        await kg_service.merge_entities(
            project_id=project.id,
            survivor_id="node_a",
            merged_id="node_b",
            request_id=request_id,
        )

        # Find it
        found = await kg_service._find_merge_by_request_id(project.id, request_id)

        assert found is not None
        assert found.request_id == request_id

    @pytest.mark.asyncio
    async def test_not_find_nonexistent_merge(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """Should return None for nonexistent request_id."""
        project = project_with_kb

        found = await kg_service._find_merge_by_request_id(
            project.id, "nonexistent_request"
        )

        assert found is None

    @pytest.mark.asyncio
    async def test_not_find_in_nonexistent_project(
        self,
        kg_service: KnowledgeGraphService,
    ) -> None:
        """Should return None for nonexistent project."""
        found = await kg_service._find_merge_by_request_id(
            "nonexistent_project", "any_request"
        )

        assert found is None


class TestCaptureEdgesState:
    """Test the _capture_edges_state helper."""

    @pytest.mark.asyncio
    async def test_capture_edges_for_node(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """Should capture all edges for a node."""
        project = project_with_kb

        edges = kg_service._capture_edges_state(project, "node_b")

        # node_b has one edge (to node_c)
        assert len(edges) == 1
        assert edges[0]["source_node_id"] == "node_b"
        assert edges[0]["target_node_id"] == "node_c"

    @pytest.mark.asyncio
    async def test_capture_edges_no_kb(
        self,
        kg_service: KnowledgeGraphService,
    ) -> None:
        """Should return empty list if no KB."""
        project = KGProject(name="No KB Project", state=ProjectState.CREATED)

        edges = kg_service._capture_edges_state(project, "any_node")

        assert edges == []

    @pytest.mark.asyncio
    async def test_capture_edges_node_with_no_edges(
        self,
        kg_service: KnowledgeGraphService,
        project_with_kb: KGProject,
    ) -> None:
        """Should return empty list for node with no edges."""
        project = project_with_kb
        from app.kg.persistence import load_knowledge_base

        # Add an isolated node
        kb = load_knowledge_base(kg_service.kb_path / project.kb_id)
        assert kb is not None
        isolated = Node(id="isolated", label="Isolated Node", entity_type="Person")
        kb.add_node(isolated)
        save_knowledge_base(kb, kg_service.kb_path)

        edges = kg_service._capture_edges_state(project, "isolated")

        assert edges == []
