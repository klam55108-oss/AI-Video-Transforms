"""
Tests for Knowledge Graph persistence: save, load, list, export.

Tests cover:
- save_knowledge_base: Creates proper directory structure with files
- load_knowledge_base: Success case and nonexistent path handling
- save/load roundtrip: Data integrity across serialization
- list_knowledge_bases: Enumerating stored knowledge bases
- export_graphml: GraphML format export for visualization tools
- _atomic_write: Write-to-temp-then-rename pattern

Uses tmp_path fixture for isolated filesystem tests.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import networkx as nx  # type: ignore[import-untyped]
import pytest

from app.kg.domain import ConnectionType, DomainProfile, SeedEntity, ThingType
from app.kg.knowledge_base import KnowledgeBase
from app.kg.models import Edge, Node, RelationshipDetail, Source, SourceType
from app.kg.persistence import (
    _atomic_write,
    export_graphml,
    list_knowledge_bases,
    load_knowledge_base,
    save_knowledge_base,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_knowledge_base() -> KnowledgeBase:
    """Create a sample knowledge base with nodes, edges, and sources."""
    kb = KnowledgeBase(
        id="test_kb_001",
        name="Test Knowledge Base",
        description="A test KB for persistence tests",
    )

    # Add sources
    source1 = Source(
        id="src_001",
        title="Test Video 1",
        source_type=SourceType.VIDEO,
        url="/videos/test1.mp4",
    )
    source2 = Source(
        id="src_002",
        title="Test Video 2",
        source_type=SourceType.AUDIO,
        url="/videos/test2.mp3",
    )
    kb.add_source(source1)
    kb.add_source(source2)

    # Add nodes
    node1 = Node(
        id="node_001",
        label="John Doe",
        entity_type="Person",
        aliases=["JD", "Johnny"],
        description="A test person entity",
        source_ids=["src_001"],
    )
    node2 = Node(
        id="node_002",
        label="Acme Corp",
        entity_type="Organization",
        aliases=["Acme", "Acme Inc"],
        description="A test organization",
        source_ids=["src_001", "src_002"],
    )
    node3 = Node(
        id="node_003",
        label="Project X",
        entity_type="Project",
        description="A secret project",
        source_ids=["src_002"],
    )
    kb.add_node(node1)
    kb.add_node(node2)
    kb.add_node(node3)

    # Add edges with relationships
    edge1 = Edge(
        id="edge_001",
        source_node_id="node_001",
        target_node_id="node_002",
        relationships=[
            RelationshipDetail(
                relationship_type="worked_for",
                source_id="src_001",
                confidence=0.95,
                evidence="John worked at Acme Corp",
            )
        ],
    )
    edge2 = Edge(
        id="edge_002",
        source_node_id="node_002",
        target_node_id="node_003",
        relationships=[
            RelationshipDetail(
                relationship_type="funded",
                source_id="src_002",
                confidence=0.8,
                evidence="Acme funded Project X",
            ),
            RelationshipDetail(
                relationship_type="managed",
                source_id="src_002",
                confidence=0.9,
                evidence="Acme managed the project",
            ),
        ],
    )
    kb.add_edge(edge1)
    kb.add_edge(edge2)

    return kb


@pytest.fixture
def sample_domain_profile() -> DomainProfile:
    """Create a sample domain profile for testing."""
    return DomainProfile(
        id="profile_001",
        name="Research Domain",
        description="A test domain profile for research projects",
        thing_types=[
            ThingType(
                name="Person",
                description="An individual",
                examples=["John", "Jane"],
                priority=1,
                icon="👤",
            ),
            ThingType(
                name="Organization",
                description="A company or institution",
                examples=["Acme", "Widget Co"],
                priority=1,
                icon="🏢",
            ),
        ],
        connection_types=[
            ConnectionType(
                name="worked_for",
                display_name="worked for",
                description="Employment relationship",
                examples=[("John", "Acme")],
                directional=True,
            )
        ],
        seed_entities=[
            SeedEntity(
                label="Test Corp",
                thing_type="Organization",
                aliases=["TC"],
            )
        ],
        extraction_context="Test extraction context",
        bootstrap_confidence=0.85,
    )


# =============================================================================
# Test: save_knowledge_base creates files
# =============================================================================


def test_save_creates_files(
    tmp_path: Path, sample_knowledge_base: KnowledgeBase
) -> None:
    """Test that save_knowledge_base creates the expected directory structure."""
    save_knowledge_base(sample_knowledge_base, tmp_path)

    kb_dir = tmp_path / sample_knowledge_base.id

    # Verify directory was created
    assert kb_dir.exists()
    assert kb_dir.is_dir()

    # Verify all expected files exist
    expected_files = [
        "meta.json",
        "nodes.json",
        "edges.json",
        "sources.json",
        "graph.graphml",
    ]
    for filename in expected_files:
        filepath = kb_dir / filename
        assert filepath.exists(), f"Missing expected file: {filename}"

    # Verify meta.json contains correct data
    meta = json.loads((kb_dir / "meta.json").read_text())
    assert meta["id"] == sample_knowledge_base.id
    assert meta["name"] == sample_knowledge_base.name
    assert meta["description"] == sample_knowledge_base.description
    assert meta["node_count"] == 3
    assert meta["edge_count"] == 2
    assert meta["source_count"] == 2

    # Verify nodes.json contains correct count
    nodes = json.loads((kb_dir / "nodes.json").read_text())
    assert len(nodes) == 3

    # Verify edges.json contains correct count
    edges = json.loads((kb_dir / "edges.json").read_text())
    assert len(edges) == 2

    # Verify sources.json contains correct count
    sources = json.loads((kb_dir / "sources.json").read_text())
    assert len(sources) == 2


def test_save_creates_domain_profile_file(
    tmp_path: Path,
    sample_knowledge_base: KnowledgeBase,
    sample_domain_profile: DomainProfile,
) -> None:
    """Test that domain_profile.json is created when domain_profile is present."""
    sample_knowledge_base.domain_profile = sample_domain_profile
    save_knowledge_base(sample_knowledge_base, tmp_path)

    kb_dir = tmp_path / sample_knowledge_base.id
    dp_file = kb_dir / "domain_profile.json"

    assert dp_file.exists()
    dp_data = json.loads(dp_file.read_text())
    assert dp_data["id"] == sample_domain_profile.id
    assert dp_data["name"] == sample_domain_profile.name
    assert len(dp_data["thing_types"]) == 2
    assert len(dp_data["connection_types"]) == 1


# =============================================================================
# Test: load_knowledge_base success
# =============================================================================


def test_load_success(tmp_path: Path, sample_knowledge_base: KnowledgeBase) -> None:
    """Test that load_knowledge_base successfully loads a saved knowledge base."""
    save_knowledge_base(sample_knowledge_base, tmp_path)

    kb_dir = tmp_path / sample_knowledge_base.id
    loaded_kb = load_knowledge_base(kb_dir)

    assert loaded_kb is not None
    assert loaded_kb.id == sample_knowledge_base.id
    assert loaded_kb.name == sample_knowledge_base.name
    assert loaded_kb.description == sample_knowledge_base.description

    # Verify node count
    assert len(loaded_kb._nodes) == 3

    # Verify edge count
    assert len(loaded_kb._edges) == 2

    # Verify source count
    assert len(loaded_kb._sources) == 2


def test_load_with_domain_profile(
    tmp_path: Path,
    sample_knowledge_base: KnowledgeBase,
    sample_domain_profile: DomainProfile,
) -> None:
    """Test that domain profile is correctly loaded."""
    sample_knowledge_base.domain_profile = sample_domain_profile
    save_knowledge_base(sample_knowledge_base, tmp_path)

    kb_dir = tmp_path / sample_knowledge_base.id
    loaded_kb = load_knowledge_base(kb_dir)

    assert loaded_kb is not None
    assert loaded_kb.domain_profile is not None
    assert loaded_kb.domain_profile.id == sample_domain_profile.id
    assert loaded_kb.domain_profile.name == sample_domain_profile.name
    assert len(loaded_kb.domain_profile.thing_types) == 2
    assert len(loaded_kb.domain_profile.connection_types) == 1


# =============================================================================
# Test: load_knowledge_base nonexistent
# =============================================================================


def test_load_nonexistent(tmp_path: Path) -> None:
    """Test that load_knowledge_base returns None for nonexistent path."""
    nonexistent_path = tmp_path / "does_not_exist"
    result = load_knowledge_base(nonexistent_path)
    assert result is None


def test_load_missing_meta_file(tmp_path: Path) -> None:
    """Test that load returns None when meta.json is missing."""
    # Create directory without meta.json
    kb_dir = tmp_path / "incomplete_kb"
    kb_dir.mkdir()
    (kb_dir / "nodes.json").write_text("[]")

    result = load_knowledge_base(kb_dir)
    assert result is None


# =============================================================================
# Test: save/load roundtrip
# =============================================================================


def test_save_load_roundtrip(
    tmp_path: Path, sample_knowledge_base: KnowledgeBase
) -> None:
    """Test that save followed by load preserves all data."""
    # Set explicit timestamps for comparison
    now = datetime.utcnow()
    sample_knowledge_base.created_at = now
    sample_knowledge_base.updated_at = now

    save_knowledge_base(sample_knowledge_base, tmp_path)
    kb_dir = tmp_path / sample_knowledge_base.id
    loaded_kb = load_knowledge_base(kb_dir)

    assert loaded_kb is not None

    # Verify metadata
    assert loaded_kb.id == sample_knowledge_base.id
    assert loaded_kb.name == sample_knowledge_base.name
    assert loaded_kb.description == sample_knowledge_base.description

    # Verify nodes match
    original_node_ids = set(sample_knowledge_base._nodes.keys())
    loaded_node_ids = set(loaded_kb._nodes.keys())
    assert original_node_ids == loaded_node_ids

    # Verify specific node data
    original_node = sample_knowledge_base._nodes["node_001"]
    loaded_node = loaded_kb._nodes["node_001"]
    assert loaded_node.label == original_node.label
    assert loaded_node.entity_type == original_node.entity_type
    assert loaded_node.aliases == original_node.aliases
    assert loaded_node.description == original_node.description

    # Verify edges match
    original_edge_ids = set(sample_knowledge_base._edges.keys())
    loaded_edge_ids = set(loaded_kb._edges.keys())
    assert original_edge_ids == loaded_edge_ids

    # Verify specific edge data
    original_edge = sample_knowledge_base._edges["edge_002"]
    loaded_edge = loaded_kb._edges["edge_002"]
    assert loaded_edge.source_node_id == original_edge.source_node_id
    assert loaded_edge.target_node_id == original_edge.target_node_id
    assert len(loaded_edge.relationships) == len(original_edge.relationships)
    assert loaded_edge.relationships[0].relationship_type == "funded"
    assert loaded_edge.relationships[1].relationship_type == "managed"

    # Verify sources match
    original_source_ids = set(sample_knowledge_base._sources.keys())
    loaded_source_ids = set(loaded_kb._sources.keys())
    assert original_source_ids == loaded_source_ids


def test_save_load_roundtrip_with_domain_profile(
    tmp_path: Path,
    sample_knowledge_base: KnowledgeBase,
    sample_domain_profile: DomainProfile,
) -> None:
    """Test roundtrip preserves domain profile data."""
    sample_knowledge_base.domain_profile = sample_domain_profile

    save_knowledge_base(sample_knowledge_base, tmp_path)
    kb_dir = tmp_path / sample_knowledge_base.id
    loaded_kb = load_knowledge_base(kb_dir)

    assert loaded_kb is not None
    assert loaded_kb.domain_profile is not None

    # Verify domain profile details
    loaded_dp = loaded_kb.domain_profile
    assert loaded_dp.name == sample_domain_profile.name
    assert loaded_dp.description == sample_domain_profile.description
    assert loaded_dp.bootstrap_confidence == sample_domain_profile.bootstrap_confidence

    # Verify thing types
    assert len(loaded_dp.thing_types) == len(sample_domain_profile.thing_types)
    loaded_person_type = next(t for t in loaded_dp.thing_types if t.name == "Person")
    assert loaded_person_type.description == "An individual"
    assert loaded_person_type.icon == "👤"

    # Verify connection types
    assert len(loaded_dp.connection_types) == len(
        sample_domain_profile.connection_types
    )
    loaded_conn_type = loaded_dp.connection_types[0]
    assert loaded_conn_type.name == "worked_for"
    assert loaded_conn_type.directional is True

    # Verify seed entities
    assert len(loaded_dp.seed_entities) == len(sample_domain_profile.seed_entities)


# =============================================================================
# Test: list_knowledge_bases
# =============================================================================


def test_list_knowledge_bases(tmp_path: Path) -> None:
    """Test listing multiple knowledge bases sorted by updated_at."""
    # Create multiple knowledge bases
    kb1 = KnowledgeBase(id="kb_alpha", name="Alpha KB")
    kb2 = KnowledgeBase(id="kb_beta", name="Beta KB")
    kb3 = KnowledgeBase(id="kb_gamma", name="Gamma KB")

    # Set different timestamps to verify sorting (most recent first)
    kb1.updated_at = datetime(2024, 1, 1, 10, 0, 0)
    kb2.updated_at = datetime(2024, 1, 3, 10, 0, 0)  # Most recent
    kb3.updated_at = datetime(2024, 1, 2, 10, 0, 0)

    save_knowledge_base(kb1, tmp_path)
    save_knowledge_base(kb2, tmp_path)
    save_knowledge_base(kb3, tmp_path)

    results = list_knowledge_bases(tmp_path)

    assert len(results) == 3
    # Verify sorted by updated_at descending (most recent first)
    assert results[0]["id"] == "kb_beta"
    assert results[1]["id"] == "kb_gamma"
    assert results[2]["id"] == "kb_alpha"


def test_list_knowledge_bases_empty_directory(tmp_path: Path) -> None:
    """Test listing returns empty list for empty directory."""
    results = list_knowledge_bases(tmp_path)
    assert results == []


def test_list_knowledge_bases_nonexistent_directory(tmp_path: Path) -> None:
    """Test listing returns empty list for nonexistent directory."""
    nonexistent = tmp_path / "nonexistent"
    results = list_knowledge_bases(nonexistent)
    assert results == []


def test_list_knowledge_bases_skips_invalid(tmp_path: Path) -> None:
    """Test that list skips directories without valid meta.json."""
    # Create a valid KB
    kb = KnowledgeBase(id="valid_kb", name="Valid KB")
    save_knowledge_base(kb, tmp_path)

    # Create an invalid directory (no meta.json)
    invalid_dir = tmp_path / "invalid_kb"
    invalid_dir.mkdir()
    (invalid_dir / "nodes.json").write_text("[]")

    # Create a directory with corrupt meta.json
    corrupt_dir = tmp_path / "corrupt_kb"
    corrupt_dir.mkdir()
    (corrupt_dir / "meta.json").write_text("invalid json {{{")

    results = list_knowledge_bases(tmp_path)

    # Should only return the valid KB
    assert len(results) == 1
    assert results[0]["id"] == "valid_kb"


# =============================================================================
# Test: export_graphml
# =============================================================================


def test_export_graphml(tmp_path: Path, sample_knowledge_base: KnowledgeBase) -> None:
    """Test GraphML export creates valid file readable by NetworkX."""
    output_path = tmp_path / "test_graph.graphml"
    export_graphml(sample_knowledge_base, output_path)

    # Verify file was created
    assert output_path.exists()
    assert output_path.stat().st_size > 0

    # Verify it's a valid GraphML file by reading it back
    G = nx.read_graphml(str(output_path))

    # Verify node count
    assert G.number_of_nodes() == 3

    # Verify edge count
    assert G.number_of_edges() == 2

    # Verify node attributes
    john_data = G.nodes["node_001"]
    assert john_data["label"] == "John Doe"
    assert john_data["entity_type"] == "Person"
    assert "JD" in john_data["aliases"]

    # Verify edge attributes
    edge_data = G.edges[("node_002", "node_003")]
    assert "funded" in edge_data["relationship_types"]
    assert "managed" in edge_data["relationship_types"]
    assert edge_data["count"] == 2


def test_export_graphml_empty_kb(tmp_path: Path) -> None:
    """Test GraphML export handles empty knowledge base."""
    kb = KnowledgeBase(id="empty_kb", name="Empty KB")
    output_path = tmp_path / "empty_graph.graphml"

    export_graphml(kb, output_path)

    assert output_path.exists()
    G = nx.read_graphml(str(output_path))
    assert G.number_of_nodes() == 0
    assert G.number_of_edges() == 0


# =============================================================================
# Test: _atomic_write
# =============================================================================


def test_atomic_write(tmp_path: Path) -> None:
    """Test that atomic write creates file with correct content."""
    output_path = tmp_path / "atomic_test.txt"
    content = "Hello, atomic world!"

    _atomic_write(output_path, content)

    assert output_path.exists()
    assert output_path.read_text() == content


def test_atomic_write_overwrites(tmp_path: Path) -> None:
    """Test that atomic write overwrites existing file."""
    output_path = tmp_path / "overwrite_test.txt"

    # Write initial content
    _atomic_write(output_path, "initial content")
    assert output_path.read_text() == "initial content"

    # Overwrite with new content
    _atomic_write(output_path, "new content")
    assert output_path.read_text() == "new content"


def test_atomic_write_no_temp_files_left(tmp_path: Path) -> None:
    """Test that atomic write doesn't leave temp files behind."""
    output_path = tmp_path / "clean_test.txt"
    _atomic_write(output_path, "test content")

    # List all files in directory
    files = list(tmp_path.iterdir())

    # Should only have the target file, no .tmp files
    assert len(files) == 1
    assert files[0].name == "clean_test.txt"


def test_atomic_write_unicode(tmp_path: Path) -> None:
    """Test that atomic write handles Unicode content."""
    output_path = tmp_path / "unicode_test.txt"
    content = "Unicode test: 日本語 中文 한국어 🎬📝"

    _atomic_write(output_path, content)

    assert output_path.exists()
    assert output_path.read_text() == content


def test_atomic_write_failure_cleanup(tmp_path: Path) -> None:
    """Test that atomic write cleans up temp file on failure."""
    # Use a directory path as target (which will fail on write)
    dir_path = tmp_path / "test_dir"
    dir_path.mkdir()

    # Count files before
    files_before = len(list(tmp_path.iterdir()))

    # Attempt write (should fail because it's a directory)
    with pytest.raises(OSError):
        _atomic_write(dir_path, "content")

    # Verify no temp files were left behind
    files_after = len(list(tmp_path.iterdir()))
    assert files_after == files_before


# =============================================================================
# Test: Edge cases
# =============================================================================


def test_save_creates_parent_directories(tmp_path: Path) -> None:
    """Test that save creates nested parent directories."""
    kb = KnowledgeBase(id="nested_kb", name="Nested KB")
    nested_path = tmp_path / "level1" / "level2" / "storage"

    save_knowledge_base(kb, nested_path)

    assert (nested_path / "nested_kb" / "meta.json").exists()


def test_roundtrip_preserves_timestamps(tmp_path: Path) -> None:
    """Test that save/load preserves created_at and updated_at."""
    kb = KnowledgeBase(id="timestamp_kb", name="Timestamp KB")
    # Set specific timestamps
    kb.created_at = datetime(2024, 6, 15, 12, 30, 45)
    kb.updated_at = datetime(2024, 6, 16, 14, 20, 30)

    save_knowledge_base(kb, tmp_path)
    loaded_kb = load_knowledge_base(tmp_path / "timestamp_kb")

    assert loaded_kb is not None
    assert loaded_kb.created_at == kb.created_at
    assert loaded_kb.updated_at == kb.updated_at
