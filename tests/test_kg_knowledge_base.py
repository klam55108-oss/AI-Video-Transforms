"""
Tests for KnowledgeBase graph operations.

Tests cover the core KnowledgeBase functionality:
- Creation and initialization
- Node operations: add, get by ID, get by label/alias, find, get_or_create
- Edge operations: add, get between nodes, add_relationship
- Graph queries: neighbors, path finding
- Statistics
"""

import pytest

from app.kg.knowledge_base import KnowledgeBase
from app.kg.models import Edge, Node, RelationshipDetail, Source, SourceType
from app.kg.domain import DomainProfile


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Fixtures
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.fixture
def empty_kb() -> KnowledgeBase:
    """Create an empty KnowledgeBase for testing."""
    return KnowledgeBase(name="Test KB", description="Test knowledge base")


@pytest.fixture
def kb_with_nodes() -> KnowledgeBase:
    """Create a KnowledgeBase with pre-populated nodes."""
    kb = KnowledgeBase(name="Test KB with Nodes")

    # Add some test nodes
    node1 = Node(
        id="node_person_1",
        label="Sidney Gottlieb",
        entity_type="Person",
        aliases=["Dr. Gottlieb", "Joseph Scheider"],
    )
    node2 = Node(
        id="node_org_1",
        label="CIA",
        entity_type="Organization",
        aliases=["Central Intelligence Agency"],
    )
    node3 = Node(
        id="node_project_1",
        label="MKUltra",
        entity_type="Project",
        aliases=["MK-Ultra", "Project MKUltra"],
    )

    kb.add_node(node1)
    kb.add_node(node2)
    kb.add_node(node3)

    return kb


@pytest.fixture
def kb_with_edges(kb_with_nodes: KnowledgeBase) -> KnowledgeBase:
    """Create a KnowledgeBase with nodes and edges."""
    kb = kb_with_nodes

    # Add a source for provenance tracking
    source = Source(
        id="source_video_1",
        title="MKUltra Documentary",
        source_type=SourceType.VIDEO,
    )
    kb.add_source(source)

    # Create edges between nodes
    edge1 = Edge(
        id="edge_1",
        source_node_id="node_person_1",  # Sidney Gottlieb
        target_node_id="node_org_1",      # CIA
    )
    edge1.add_relationship(RelationshipDetail(
        relationship_type="worked_for",
        source_id="source_video_1",
        confidence=1.0,
    ))

    edge2 = Edge(
        id="edge_2",
        source_node_id="node_person_1",  # Sidney Gottlieb
        target_node_id="node_project_1",  # MKUltra
    )
    edge2.add_relationship(RelationshipDetail(
        relationship_type="directed",
        source_id="source_video_1",
        confidence=0.95,
    ))

    edge3 = Edge(
        id="edge_3",
        source_node_id="node_org_1",      # CIA
        target_node_id="node_project_1",  # MKUltra
    )
    edge3.add_relationship(RelationshipDetail(
        relationship_type="funded",
        source_id="source_video_1",
        confidence=1.0,
    ))

    kb.add_edge(edge1)
    kb.add_edge(edge2)
    kb.add_edge(edge3)

    return kb


@pytest.fixture
def sample_domain_profile() -> DomainProfile:
    """Create a sample DomainProfile for testing."""
    return DomainProfile(
        name="CIA Research Domain",
        description="Domain profile for CIA research analysis",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# KnowledgeBase Creation Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_kb_creation() -> None:
    """KnowledgeBase should initialize with default values and auto-generated ID."""
    kb = KnowledgeBase(name="Research KB", description="A test KB")

    # Verify basic attributes
    assert kb.name == "Research KB"
    assert kb.description == "A test KB"
    assert len(kb.id) == 12  # UUID4 hex[:12]

    # Verify empty internal storage
    assert len(kb._nodes) == 0
    assert len(kb._edges) == 0
    assert len(kb._sources) == 0

    # Verify timestamps exist
    assert kb.created_at is not None
    assert kb.updated_at is not None


def test_kb_creation_with_custom_id() -> None:
    """KnowledgeBase should accept a custom ID."""
    kb = KnowledgeBase(id="custom_kb_id", name="Custom ID KB")

    assert kb.id == "custom_kb_id"
    assert kb.name == "Custom ID KB"


def test_kb_creation_with_domain_profile(sample_domain_profile: DomainProfile) -> None:
    """KnowledgeBase should accept an optional DomainProfile."""
    kb = KnowledgeBase(
        name="Domain KB",
        domain_profile=sample_domain_profile,
    )

    assert kb.domain_profile is not None
    assert kb.domain_profile.name == "CIA Research Domain"


def test_kb_creation_defaults() -> None:
    """KnowledgeBase should use 'Untitled' as default name."""
    kb = KnowledgeBase()

    assert kb.name == "Untitled"
    assert kb.description is None
    assert kb.domain_profile is None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Node Operations Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_add_node(empty_kb: KnowledgeBase) -> None:
    """add_node should add node to internal storage and indexes."""
    node = Node(
        id="test_node_1",
        label="Test Entity",
        entity_type="Person",
        aliases=["Test Alias"],
    )

    result = empty_kb.add_node(node)

    # Should return the same node
    assert result is node

    # Should be in internal storage
    assert "test_node_1" in empty_kb._nodes
    assert empty_kb._nodes["test_node_1"] is node

    # Should be indexed by label (case-insensitive)
    assert "test entity" in empty_kb._label_to_id
    assert empty_kb._label_to_id["test entity"] == "test_node_1"

    # Should be indexed by alias (case-insensitive)
    assert "test alias" in empty_kb._alias_to_id
    assert empty_kb._alias_to_id["test alias"] == "test_node_1"

    # Should be in NetworkX graph
    assert "test_node_1" in empty_kb._graph.nodes


def test_add_node_multiple_aliases(empty_kb: KnowledgeBase) -> None:
    """add_node should index all aliases."""
    node = Node(
        label="CIA",
        entity_type="Organization",
        aliases=["Central Intelligence Agency", "The Company", "Langley"],
    )

    empty_kb.add_node(node)

    # All aliases should be indexed
    assert "central intelligence agency" in empty_kb._alias_to_id
    assert "the company" in empty_kb._alias_to_id
    assert "langley" in empty_kb._alias_to_id


def test_get_node_by_label(kb_with_nodes: KnowledgeBase) -> None:
    """get_node_by_label should find nodes by primary label (case-insensitive)."""
    # Exact match
    node = kb_with_nodes.get_node_by_label("Sidney Gottlieb")
    assert node is not None
    assert node.label == "Sidney Gottlieb"

    # Case-insensitive match
    node_lower = kb_with_nodes.get_node_by_label("sidney gottlieb")
    assert node_lower is not None
    assert node_lower.id == node.id

    # Upper case
    node_upper = kb_with_nodes.get_node_by_label("SIDNEY GOTTLIEB")
    assert node_upper is not None
    assert node_upper.id == node.id

    # Non-existent label
    not_found = kb_with_nodes.get_node_by_label("Unknown Entity")
    assert not_found is None


def test_get_node_by_alias(kb_with_nodes: KnowledgeBase) -> None:
    """get_node_by_label should also find nodes by alias (case-insensitive)."""
    # Find Sidney Gottlieb by alias
    node = kb_with_nodes.get_node_by_label("Dr. Gottlieb")
    assert node is not None
    assert node.label == "Sidney Gottlieb"

    # Find by another alias
    node_alias2 = kb_with_nodes.get_node_by_label("Joseph Scheider")
    assert node_alias2 is not None
    assert node_alias2.label == "Sidney Gottlieb"

    # Case-insensitive alias lookup
    node_lower = kb_with_nodes.get_node_by_label("central intelligence agency")
    assert node_lower is not None
    assert node_lower.label == "CIA"


def test_get_node_prefers_label_over_alias(empty_kb: KnowledgeBase) -> None:
    """get_node_by_label should prefer primary label over alias."""
    # Create node where label of one node is alias of another
    node1 = Node(label="Alpha", entity_type="Entity", aliases=["Beta"])
    node2 = Node(label="Beta", entity_type="Entity", aliases=["Gamma"])

    empty_kb.add_node(node1)
    empty_kb.add_node(node2)

    # "Beta" should return node2 (primary label) not node1 (alias)
    result = empty_kb.get_node_by_label("Beta")
    assert result is not None
    assert result.label == "Beta"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# get_or_create_node Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_get_or_create_node_new(empty_kb: KnowledgeBase) -> None:
    """get_or_create_node should create new node when label doesn't exist."""
    node, created = empty_kb.get_or_create_node(
        label="New Entity",
        entity_type="Person",
        description="A new test entity",
    )

    assert created is True
    assert node.label == "New Entity"
    assert node.entity_type == "Person"
    assert node.description == "A new test entity"

    # Should be retrievable
    retrieved = empty_kb.get_node_by_label("New Entity")
    assert retrieved is not None
    assert retrieved.id == node.id


def test_get_or_create_node_existing(kb_with_nodes: KnowledgeBase) -> None:
    """get_or_create_node should return existing node when label exists."""
    original = kb_with_nodes.get_node_by_label("CIA")
    assert original is not None
    original_id = original.id

    # Try to "create" with same label
    node, created = kb_with_nodes.get_or_create_node(
        label="CIA",
        entity_type="Organization",
    )

    assert created is False
    assert node.id == original_id

    # Case-insensitive match
    node_lower, created_lower = kb_with_nodes.get_or_create_node(
        label="cia",
        entity_type="Organization",
    )

    assert created_lower is False
    assert node_lower.id == original_id


def test_get_or_create_node_with_kwargs(empty_kb: KnowledgeBase) -> None:
    """get_or_create_node should pass kwargs to Node constructor."""
    node, created = empty_kb.get_or_create_node(
        label="Rich Node",
        entity_type="Person",
        aliases=["Alias One", "Alias Two"],
        description="Detailed description",
        properties={"key": "value"},
    )

    assert created is True
    assert node.aliases == ["Alias One", "Alias Two"]
    assert node.description == "Detailed description"
    assert node.properties == {"key": "value"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# find_nodes Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_find_nodes(kb_with_nodes: KnowledgeBase) -> None:
    """find_nodes should filter by partial label match."""
    # Partial label match
    results = kb_with_nodes.find_nodes(label="Gott")
    assert len(results) == 1
    assert results[0].label == "Sidney Gottlieb"

    # Case-insensitive partial match
    results_lower = kb_with_nodes.find_nodes(label="gott")
    assert len(results_lower) == 1


def test_find_nodes_by_entity_type(kb_with_nodes: KnowledgeBase) -> None:
    """find_nodes should filter by exact entity type."""
    # Filter by entity type
    persons = kb_with_nodes.find_nodes(entity_type="Person")
    assert len(persons) == 1
    assert persons[0].label == "Sidney Gottlieb"

    orgs = kb_with_nodes.find_nodes(entity_type="Organization")
    assert len(orgs) == 1
    assert orgs[0].label == "CIA"


def test_find_nodes_combined_filters(kb_with_nodes: KnowledgeBase) -> None:
    """find_nodes should combine label and entity_type filters."""
    # Combined filter - should match
    results = kb_with_nodes.find_nodes(label="CIA", entity_type="Organization")
    assert len(results) == 1

    # Combined filter - should not match (wrong type)
    results_no_match = kb_with_nodes.find_nodes(label="CIA", entity_type="Person")
    assert len(results_no_match) == 0


def test_find_nodes_no_filters(kb_with_nodes: KnowledgeBase) -> None:
    """find_nodes with no filters should return all nodes."""
    results = kb_with_nodes.find_nodes()
    assert len(results) == 3


def test_find_nodes_empty_kb(empty_kb: KnowledgeBase) -> None:
    """find_nodes on empty KB should return empty list."""
    results = empty_kb.find_nodes(label="anything")
    assert results == []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Edge Operations Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_add_edge(kb_with_nodes: KnowledgeBase) -> None:
    """add_edge should add edge to internal storage and NetworkX graph."""
    edge = Edge(
        id="test_edge",
        source_node_id="node_person_1",
        target_node_id="node_org_1",
    )
    edge.add_relationship(RelationshipDetail(
        relationship_type="worked_for",
        source_id="src_1",
    ))

    result = kb_with_nodes.add_edge(edge)

    # Should return same edge
    assert result is edge

    # Should be in internal storage
    assert "test_edge" in kb_with_nodes._edges

    # Should be in NetworkX graph
    assert kb_with_nodes._graph.has_edge("node_person_1", "node_org_1")


def test_get_edge_between(kb_with_edges: KnowledgeBase) -> None:
    """get_edge_between should find edge by source and target node IDs."""
    # Find existing edge
    edge = kb_with_edges.get_edge_between("node_person_1", "node_org_1")
    assert edge is not None
    assert edge.source_node_id == "node_person_1"
    assert edge.target_node_id == "node_org_1"

    # Edge is directional - reverse should return None
    reverse_edge = kb_with_edges.get_edge_between("node_org_1", "node_person_1")
    assert reverse_edge is None

    # Non-existent edge
    no_edge = kb_with_edges.get_edge_between("node_person_1", "nonexistent")
    assert no_edge is None


def test_get_or_create_edge_new(kb_with_nodes: KnowledgeBase) -> None:
    """get_or_create_edge should create new edge when it doesn't exist."""
    edge, created = kb_with_nodes.get_or_create_edge(
        "node_person_1",
        "node_org_1",
    )

    assert created is True
    assert edge.source_node_id == "node_person_1"
    assert edge.target_node_id == "node_org_1"
    assert edge.relationships == []


def test_get_or_create_edge_existing(kb_with_edges: KnowledgeBase) -> None:
    """get_or_create_edge should return existing edge."""
    original = kb_with_edges.get_edge_between("node_person_1", "node_org_1")
    assert original is not None
    original_id = original.id

    edge, created = kb_with_edges.get_or_create_edge(
        "node_person_1",
        "node_org_1",
    )

    assert created is False
    assert edge.id == original_id


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# add_relationship Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_add_relationship(kb_with_nodes: KnowledgeBase) -> None:
    """add_relationship should create edge with relationship between nodes by label."""
    # Add a source first
    source = Source(id="src_test", title="Test Source", source_type=SourceType.VIDEO)
    kb_with_nodes.add_source(source)

    edge = kb_with_nodes.add_relationship(
        source_label="Sidney Gottlieb",
        target_label="CIA",
        relationship_type="worked_for",
        source_id="src_test",
        confidence=0.9,
        evidence="Gottlieb worked for the CIA",
    )

    assert edge is not None
    assert edge.source_node_id == "node_person_1"
    assert edge.target_node_id == "node_org_1"
    assert len(edge.relationships) == 1
    assert edge.relationships[0].relationship_type == "worked_for"
    assert edge.relationships[0].confidence == 0.9


def test_add_relationship_by_alias(kb_with_nodes: KnowledgeBase) -> None:
    """add_relationship should work with aliases."""
    source = Source(id="src_alias", title="Alias Source", source_type=SourceType.VIDEO)
    kb_with_nodes.add_source(source)

    # Use aliases instead of primary labels
    edge = kb_with_nodes.add_relationship(
        source_label="Dr. Gottlieb",  # alias
        target_label="Central Intelligence Agency",  # alias
        relationship_type="employed_by",
        source_id="src_alias",
    )

    assert edge is not None
    # Should resolve to the actual nodes
    assert edge.source_node_id == "node_person_1"
    assert edge.target_node_id == "node_org_1"


def test_add_relationship_node_not_found(kb_with_nodes: KnowledgeBase) -> None:
    """add_relationship should return None if either node doesn't exist."""
    # Source node doesn't exist
    edge = kb_with_nodes.add_relationship(
        source_label="Unknown Person",
        target_label="CIA",
        relationship_type="worked_for",
        source_id="src",
    )
    assert edge is None

    # Target node doesn't exist
    edge = kb_with_nodes.add_relationship(
        source_label="Sidney Gottlieb",
        target_label="Unknown Org",
        relationship_type="worked_for",
        source_id="src",
    )
    assert edge is None


def test_add_relationship_to_existing_edge(kb_with_edges: KnowledgeBase) -> None:
    """add_relationship should add to existing edge between same nodes."""
    # Get count of relationships before
    edge_before = kb_with_edges.get_edge_between("node_person_1", "node_org_1")
    assert edge_before is not None
    rel_count_before = len(edge_before.relationships)

    # Add another relationship to same edge
    edge = kb_with_edges.add_relationship(
        source_label="Sidney Gottlieb",
        target_label="CIA",
        relationship_type="reported_to",
        source_id="source_video_1",
    )

    assert edge is not None
    assert len(edge.relationships) == rel_count_before + 1

    # Both relationship types should exist
    types = edge.get_relationship_types()
    assert "worked_for" in types
    assert "reported_to" in types


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Graph Query Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_get_neighbors(kb_with_edges: KnowledgeBase) -> None:
    """get_neighbors should return all connected nodes (predecessors + successors)."""
    # Sidney Gottlieb -> CIA, MKUltra
    neighbors = kb_with_edges.get_neighbors("node_person_1")

    assert len(neighbors) == 2
    neighbor_ids = {n.id for n in neighbors}
    assert "node_org_1" in neighbor_ids  # CIA
    assert "node_project_1" in neighbor_ids  # MKUltra


def test_get_neighbors_includes_predecessors(kb_with_edges: KnowledgeBase) -> None:
    """get_neighbors should include nodes pointing TO this node."""
    # MKUltra has incoming edges from Sidney Gottlieb and CIA
    neighbors = kb_with_edges.get_neighbors("node_project_1")

    assert len(neighbors) == 2
    neighbor_ids = {n.id for n in neighbors}
    assert "node_person_1" in neighbor_ids  # Sidney Gottlieb
    assert "node_org_1" in neighbor_ids  # CIA


def test_get_neighbors_node_not_in_graph(kb_with_edges: KnowledgeBase) -> None:
    """get_neighbors should return empty list for non-existent node."""
    neighbors = kb_with_edges.get_neighbors("nonexistent_node")
    assert neighbors == []


def test_get_neighbors_isolated_node(empty_kb: KnowledgeBase) -> None:
    """get_neighbors should return empty list for isolated node."""
    node = Node(id="isolated", label="Isolated Node", entity_type="Test")
    empty_kb.add_node(node)

    neighbors = empty_kb.get_neighbors("isolated")
    assert neighbors == []


def test_find_paths(kb_with_edges: KnowledgeBase) -> None:
    """find_paths should return paths between two nodes."""
    # Path from Sidney Gottlieb to MKUltra
    paths = kb_with_edges.find_paths("node_person_1", "node_project_1")

    # Should find direct path: Gottlieb -> MKUltra
    assert len(paths) >= 1

    # Check that a direct path exists
    direct_path = ["node_person_1", "node_project_1"]
    assert direct_path in paths


def test_find_paths_multiple_routes(kb_with_edges: KnowledgeBase) -> None:
    """find_paths should find multiple routes if they exist."""
    # From CIA to MKUltra: direct path exists
    paths = kb_with_edges.find_paths("node_org_1", "node_project_1")

    assert len(paths) >= 1
    # Direct path: CIA -> MKUltra
    assert ["node_org_1", "node_project_1"] in paths


def test_find_paths_no_path(kb_with_edges: KnowledgeBase) -> None:
    """find_paths should return empty list when no path exists."""
    # Add an isolated node
    isolated = Node(id="isolated", label="Isolated", entity_type="Test")
    kb_with_edges.add_node(isolated)

    paths = kb_with_edges.find_paths("node_person_1", "isolated")
    assert paths == []


def test_find_paths_node_not_found(kb_with_edges: KnowledgeBase) -> None:
    """find_paths should return empty list for non-existent nodes."""
    paths = kb_with_edges.find_paths("nonexistent", "node_person_1")
    assert paths == []

    paths = kb_with_edges.find_paths("node_person_1", "nonexistent")
    assert paths == []


def test_find_paths_max_length(kb_with_edges: KnowledgeBase) -> None:
    """find_paths should respect max_length parameter."""
    # With max_length=1, only direct connections
    paths = kb_with_edges.find_paths(
        "node_person_1",
        "node_project_1",
        max_length=1,
    )

    # Direct path length is 1 (2 nodes, 1 edge)
    for path in paths:
        assert len(path) <= 2  # path length is node count


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Statistics Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_stats(kb_with_edges: KnowledgeBase) -> None:
    """stats should return comprehensive graph statistics."""
    stats = kb_with_edges.stats()

    # Basic counts
    assert stats["node_count"] == 3
    assert stats["edge_count"] == 3
    assert stats["source_count"] == 1

    # Entity type breakdown
    assert "entity_types" in stats
    assert stats["entity_types"]["Person"] == 1
    assert stats["entity_types"]["Organization"] == 1
    assert stats["entity_types"]["Project"] == 1

    # Relationship type breakdown
    assert "relationship_types" in stats
    assert stats["relationship_types"]["worked_for"] == 1
    assert stats["relationship_types"]["directed"] == 1
    assert stats["relationship_types"]["funded"] == 1


def test_stats_empty_kb(empty_kb: KnowledgeBase) -> None:
    """stats should handle empty KB gracefully."""
    stats = empty_kb.stats()

    assert stats["node_count"] == 0
    assert stats["edge_count"] == 0
    assert stats["source_count"] == 0
    assert stats["entity_types"] == {}
    assert stats["relationship_types"] == {}


def test_stats_multiple_relationships_per_edge(kb_with_edges: KnowledgeBase) -> None:
    """stats should count all relationships across all edges."""
    # Add another relationship to an existing edge
    kb_with_edges.add_relationship(
        source_label="Sidney Gottlieb",
        target_label="CIA",
        relationship_type="reported_to",
        source_id="source_video_1",
    )

    stats = kb_with_edges.stats()

    # Edge count should remain the same (same node pair)
    assert stats["edge_count"] == 3

    # Relationship count should increase
    assert stats["relationship_types"]["reported_to"] == 1
    assert stats["relationship_types"]["worked_for"] == 1  # Original


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Source Operations Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_add_and_get_source(empty_kb: KnowledgeBase) -> None:
    """add_source and get_source should manage source provenance."""
    source = Source(
        id="test_source",
        title="Test Video",
        source_type=SourceType.VIDEO,
        url="https://example.com/video",
    )

    result = empty_kb.add_source(source)

    assert result is source
    assert "test_source" in empty_kb._sources

    # Retrieve source
    retrieved = empty_kb.get_source("test_source")
    assert retrieved is not None
    assert retrieved.title == "Test Video"

    # Non-existent source
    not_found = empty_kb.get_source("nonexistent")
    assert not_found is None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Updated Timestamp Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_updated_at_changes_on_add(empty_kb: KnowledgeBase) -> None:
    """updated_at should change when nodes/edges/sources are added."""
    import time

    initial_updated = empty_kb.updated_at
    time.sleep(0.01)  # Ensure time difference

    # Add node
    empty_kb.add_node(Node(label="Test", entity_type="Entity"))

    assert empty_kb.updated_at > initial_updated
