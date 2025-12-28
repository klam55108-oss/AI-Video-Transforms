"""
Tests for Knowledge Graph Entity Resolution.

Tests cover:
- String similarity functions (Jaro-Winkler, Levenshtein)
- Alias overlap scoring
- Blocking strategy
- EntityMatcher similarity computation
- KnowledgeBase merge operations
- Resolution candidate finding
"""

from __future__ import annotations

import pytest

from app.kg.knowledge_base import KnowledgeBase
from app.kg.models import Edge, Node, RelationshipDetail, Source, SourceType
from app.kg.resolution import (
    EntityMatcher,
    MergeHistory,
    ResolutionCandidate,
    ResolutionConfig,
    _block_by_first_char,
    alias_overlap_score,
    jaro_winkler_similarity,
    levenshtein_similarity,
)


# ============================================================================
# String Similarity Function Tests
# ============================================================================


class TestJaroWinklerSimilarity:
    """Tests for Jaro-Winkler string similarity."""

    def test_identical_strings(self) -> None:
        """Identical strings should return 1.0."""
        assert jaro_winkler_similarity("hello", "hello") == 1.0
        assert jaro_winkler_similarity("Elon Musk", "Elon Musk") == 1.0

    def test_completely_different(self) -> None:
        """Completely different strings should return low score."""
        score = jaro_winkler_similarity("abc", "xyz")
        assert score < 0.5

    def test_similar_strings(self) -> None:
        """Similar strings should return high score."""
        # Transposed characters
        score = jaro_winkler_similarity("MARTHA", "MARHTA")
        assert score > 0.9

        # Name variations
        score = jaro_winkler_similarity("Elon Musk", "Elon R. Musk")
        assert score > 0.8

    def test_empty_strings(self) -> None:
        """Empty strings should be handled gracefully."""
        assert jaro_winkler_similarity("", "") == 1.0
        assert jaro_winkler_similarity("hello", "") == 0.0
        assert jaro_winkler_similarity("", "hello") == 0.0

    def test_case_insensitive(self) -> None:
        """Comparison should be case-insensitive."""
        score_upper = jaro_winkler_similarity("HELLO", "HELLO")
        score_mixed = jaro_winkler_similarity("Hello", "hello")
        assert score_upper == score_mixed == 1.0

    def test_whitespace_handling(self) -> None:
        """Whitespace should be stripped."""
        assert jaro_winkler_similarity("  hello  ", "hello") == 1.0

    def test_unicode_characters(self) -> None:
        """Unicode characters should work correctly."""
        assert jaro_winkler_similarity("cafe", "cafe") == 1.0
        # Accented characters as different
        score = jaro_winkler_similarity("cafe", "cafe")
        assert score > 0.9

    def test_common_prefix_boost(self) -> None:
        """Common prefix should boost the score (Winkler modification)."""
        # Same Jaro, but different prefix lengths
        score_prefix = jaro_winkler_similarity("DIXON", "DICKSONX")
        score_no_prefix = jaro_winkler_similarity("XDIXON", "DICKSON")
        # Winkler boost should make first score higher
        assert score_prefix > score_no_prefix


class TestLevenshteinSimilarity:
    """Tests for Levenshtein string similarity."""

    def test_identical_strings(self) -> None:
        """Identical strings should return 1.0."""
        assert levenshtein_similarity("hello", "hello") == 1.0
        assert levenshtein_similarity("test", "test") == 1.0

    def test_completely_different(self) -> None:
        """Completely different strings of same length should return 0.0."""
        assert levenshtein_similarity("abc", "xyz") == 0.0

    def test_one_edit_away(self) -> None:
        """Strings one edit apart should have high similarity."""
        # One insertion
        score = levenshtein_similarity("cat", "cats")
        assert 0.7 < score < 1.0

        # One substitution
        score = levenshtein_similarity("cat", "bat")
        assert 0.6 < score < 1.0

    def test_empty_strings(self) -> None:
        """Empty strings should be handled gracefully."""
        assert levenshtein_similarity("", "") == 1.0
        assert levenshtein_similarity("hello", "") == 0.0
        assert levenshtein_similarity("", "hello") == 0.0

    def test_case_insensitive(self) -> None:
        """Comparison should be case-insensitive."""
        assert levenshtein_similarity("HELLO", "hello") == 1.0

    def test_known_example(self) -> None:
        """Test known example: kitten vs sitting."""
        # Edit distance is 3 (k->s, e->i, insert g)
        # Length is 7, so similarity = 1 - 3/7 = 0.571...
        score = levenshtein_similarity("kitten", "sitting")
        assert 0.5 < score < 0.6


class TestAliasOverlapScore:
    """Tests for alias overlap (Jaccard similarity)."""

    def test_identical_sets(self) -> None:
        """Identical sets should return 1.0."""
        aliases = ["John", "J. Smith", "Johnny"]
        assert alias_overlap_score(aliases, aliases) == 1.0

    def test_completely_different(self) -> None:
        """Completely different sets should return 0.0."""
        a = ["John", "Smith"]
        b = ["Jane", "Doe"]
        assert alias_overlap_score(a, b) == 0.0

    def test_partial_overlap(self) -> None:
        """Partial overlap should return fraction."""
        a = ["Dr. Smith", "John"]
        b = ["John", "J. Smith"]
        # Intersection: {"john"}, Union: {"dr. smith", "john", "j. smith"}
        score = alias_overlap_score(a, b)
        assert 0.3 < score < 0.4  # 1/3 = 0.333...

    def test_empty_sets(self) -> None:
        """Empty sets should return 0.0."""
        assert alias_overlap_score([], []) == 0.0
        assert alias_overlap_score(["John"], []) == 0.0
        assert alias_overlap_score([], ["John"]) == 0.0

    def test_case_insensitive(self) -> None:
        """Comparison should be case-insensitive."""
        a = ["JOHN", "Smith"]
        b = ["john", "SMITH"]
        assert alias_overlap_score(a, b) == 1.0

    def test_handles_empty_strings(self) -> None:
        """Empty strings in lists should be handled."""
        a = ["John", ""]
        b = ["John"]
        score = alias_overlap_score(a, b)
        assert score == 1.0  # Empty string is filtered out


# ============================================================================
# Blocking Strategy Tests
# ============================================================================


class TestBlockByFirstChar:
    """Tests for the blocking strategy."""

    def test_groups_by_first_character(self) -> None:
        """Nodes should be grouped by first character of label."""
        nodes = [
            Node(id="n1", label="Alice", entity_type="Person"),
            Node(id="n2", label="Adam", entity_type="Person"),
            Node(id="n3", label="Bob", entity_type="Person"),
        ]

        blocks = _block_by_first_char(nodes)

        assert "a" in blocks
        assert "b" in blocks
        assert len(blocks["a"]) == 2
        assert len(blocks["b"]) == 1

    def test_case_insensitive(self) -> None:
        """Blocking should be case-insensitive."""
        nodes = [
            Node(id="n1", label="Alice", entity_type="Person"),
            Node(id="n2", label="alice", entity_type="Person"),
            Node(id="n3", label="ALICE", entity_type="Person"),
        ]

        blocks = _block_by_first_char(nodes)

        assert len(blocks) == 1
        assert "a" in blocks
        assert len(blocks["a"]) == 3

    def test_empty_label_handling(self) -> None:
        """Empty labels should go to underscore block."""
        nodes = [
            Node(id="n1", label="", entity_type="Person"),
            Node(id="n2", label="Alice", entity_type="Person"),
        ]

        blocks = _block_by_first_char(nodes)

        assert "_" in blocks
        assert len(blocks["_"]) == 1

    def test_empty_list(self) -> None:
        """Empty node list should return empty dict."""
        blocks = _block_by_first_char([])
        assert blocks == {}


# ============================================================================
# EntityMatcher Tests
# ============================================================================


class TestEntityMatcher:
    """Tests for EntityMatcher similarity computation."""

    @pytest.fixture
    def matcher(self) -> EntityMatcher:
        """Create an EntityMatcher with default config."""
        return EntityMatcher()

    @pytest.fixture
    def custom_matcher(self) -> EntityMatcher:
        """Create an EntityMatcher with custom config."""
        config = ResolutionConfig(
            string_weight=0.5,
            alias_weight=0.2,
            type_weight=0.2,
            graph_weight=0.1,
            semantic_weight=0.0,
        )
        return EntityMatcher(config)

    def test_identical_nodes_high_confidence(self, matcher: EntityMatcher) -> None:
        """Identical nodes should have high confidence."""
        node_a = Node(id="n1", label="John Smith", entity_type="Person")
        node_b = Node(id="n2", label="John Smith", entity_type="Person")

        confidence, signals = matcher.compute_similarity(node_a, node_b)

        # With default weights (string=0.4, alias=0.25, type=0.2, graph=0.15, semantic=0):
        # string=1.0*0.4 + alias=1.0*0.25 + type=1.0*0.2 + graph=0.0*0.15 = 0.85
        # Note: alias_sim includes labels, so identical labels mean alias overlap = 1.0
        assert confidence > 0.8
        assert signals["string_sim"] == 1.0
        assert signals["type_sim"] == 1.0

    def test_different_type_low_score(self, matcher: EntityMatcher) -> None:
        """Different entity types should lower the score."""
        node_a = Node(id="n1", label="Apple", entity_type="Company")
        node_b = Node(id="n2", label="Apple", entity_type="Fruit")

        confidence, signals = matcher.compute_similarity(node_a, node_b)

        # String match is perfect but type mismatch
        assert signals["string_sim"] == 1.0
        assert signals["type_sim"] == 0.0
        # Overall should be lower due to type mismatch
        assert confidence < 0.9

    def test_alias_overlap_boost(self, matcher: EntityMatcher) -> None:
        """Shared aliases should boost confidence."""
        node_a = Node(
            id="n1",
            label="Elon Musk",
            entity_type="Person",
            aliases=["@elonmusk", "Tesla CEO"],
        )
        node_b = Node(
            id="n2",
            label="E. Musk",
            entity_type="Person",
            aliases=["@elonmusk", "SpaceX CEO"],
        )

        confidence, signals = matcher.compute_similarity(node_a, node_b)

        # Should have alias overlap (@elonmusk is shared)
        assert signals["alias_sim"] > 0
        # With semantic_weight=0.0, reasonable confidence should be achievable
        assert confidence > 0.5

    def test_graph_context_with_kb(self) -> None:
        """Graph context should consider shared neighbors."""
        kb = KnowledgeBase(name="Test KB")

        # Create nodes
        node_a = Node(id="n1", label="John", entity_type="Person")
        node_b = Node(id="n2", label="Jon", entity_type="Person")
        shared_neighbor = Node(id="n3", label="Acme Corp", entity_type="Organization")

        kb.add_node(node_a)
        kb.add_node(node_b)
        kb.add_node(shared_neighbor)

        # Create edges to shared neighbor
        edge1 = Edge(id="e1", source_node_id="n1", target_node_id="n3")
        edge1.add_relationship(
            RelationshipDetail(relationship_type="works_for", source_id="src1")
        )
        edge2 = Edge(id="e2", source_node_id="n2", target_node_id="n3")
        edge2.add_relationship(
            RelationshipDetail(relationship_type="works_for", source_id="src1")
        )

        kb.add_edge(edge1)
        kb.add_edge(edge2)

        matcher = EntityMatcher()
        confidence, signals = matcher.compute_similarity(node_a, node_b, kb)

        # Should have positive graph similarity due to shared neighbor
        assert signals["graph_sim"] > 0

    def test_find_candidates_basic(self, matcher: EntityMatcher) -> None:
        """find_candidates should find similar nodes."""
        nodes = [
            Node(id="n1", label="John Smith", entity_type="Person"),
            Node(id="n2", label="Jon Smith", entity_type="Person"),
            Node(id="n3", label="Alice Jones", entity_type="Person"),
        ]

        # With default weights, similar names should score above 0.5
        candidates = matcher.find_candidates(nodes, min_confidence=0.5)

        # John Smith and Jon Smith should be candidates (both start with 'j')
        assert len(candidates) >= 1
        # Check that the pair is found
        ids = [(c.node_a_id, c.node_b_id) for c in candidates]
        assert ("n1", "n2") in ids or ("n2", "n1") in ids

    def test_find_candidates_respects_threshold(self, matcher: EntityMatcher) -> None:
        """find_candidates should respect min_confidence threshold."""
        nodes = [
            Node(id="n1", label="John", entity_type="Person"),
            Node(id="n2", label="Jane", entity_type="Person"),
        ]

        # High threshold should find nothing
        candidates = matcher.find_candidates(nodes, min_confidence=0.95)
        assert len(candidates) == 0

    def test_find_candidates_sorted_by_confidence(self, matcher: EntityMatcher) -> None:
        """Candidates should be sorted by confidence descending."""
        nodes = [
            Node(id="n1", label="John Smith", entity_type="Person"),
            Node(id="n2", label="John Smithe", entity_type="Person"),
            Node(id="n3", label="Jon Smith", entity_type="Person"),
        ]

        candidates = matcher.find_candidates(nodes, min_confidence=0.5)

        if len(candidates) > 1:
            for i in range(len(candidates) - 1):
                assert candidates[i].confidence >= candidates[i + 1].confidence


# ============================================================================
# Resolution Models Tests
# ============================================================================


class TestResolutionModels:
    """Tests for resolution model creation and validation."""

    def test_resolution_candidate_creation(self) -> None:
        """ResolutionCandidate should initialize with defaults."""
        candidate = ResolutionCandidate(
            node_a_id="node1",
            node_b_id="node2",
            confidence=0.85,
        )

        assert len(candidate.id) == 8
        assert candidate.status == "pending"
        assert candidate.signals == {}
        assert candidate.created_at is not None

    def test_merge_history_creation(self) -> None:
        """MergeHistory should initialize with defaults."""
        history = MergeHistory(
            survivor_id="survivor",
            merged_id="merged",
            merged_label="Old Label",
            confidence=0.95,
        )

        assert len(history.id) == 8
        assert history.merge_type == "user"
        assert history.merged_by is None
        assert history.merged_aliases == []

    def test_resolution_config_defaults(self) -> None:
        """ResolutionConfig should have sensible defaults."""
        config = ResolutionConfig()

        assert config.auto_merge_threshold == 0.9
        assert config.review_threshold == 0.7
        # Non-semantic weights should sum to 1.0 (semantic defaults to 0)
        active_weight = (
            config.string_weight
            + config.alias_weight
            + config.type_weight
            + config.graph_weight
        )
        assert 0.99 <= active_weight <= 1.01
        assert config.semantic_weight == 0.0  # Default until embeddings added

    def test_resolution_config_validation(self) -> None:
        """ResolutionConfig should validate bounds."""
        # Should raise for out-of-bounds values
        with pytest.raises(ValueError):
            ResolutionConfig(auto_merge_threshold=1.5)

        with pytest.raises(ValueError):
            ResolutionConfig(review_threshold=-0.1)


# ============================================================================
# KnowledgeBase Merge Operations Tests
# ============================================================================


class TestKnowledgeBaseMerge:
    """Tests for KnowledgeBase merge operations."""

    @pytest.fixture
    def kb_with_nodes(self) -> KnowledgeBase:
        """Create a KnowledgeBase with test nodes."""
        kb = KnowledgeBase(name="Test KB")

        node1 = Node(
            id="survivor",
            label="John Smith",
            entity_type="Person",
            aliases=["J. Smith"],
            properties={"age": 30},
            source_ids=["src1"],
        )
        node2 = Node(
            id="merged",
            label="Jon Smith",
            entity_type="Person",
            aliases=["Johnny"],
            properties={"age": 31, "city": "NYC"},
            source_ids=["src2"],
        )
        node3 = Node(
            id="other",
            label="Acme Corp",
            entity_type="Organization",
        )

        kb.add_node(node1)
        kb.add_node(node2)
        kb.add_node(node3)

        return kb

    @pytest.fixture
    def kb_with_edges(self, kb_with_nodes: KnowledgeBase) -> KnowledgeBase:
        """Add edges to the test KB."""
        kb = kb_with_nodes

        # Add source for edges
        source = Source(id="src1", title="Test", source_type=SourceType.VIDEO)
        kb.add_source(source)

        # survivor -> other
        edge1 = Edge(id="e1", source_node_id="survivor", target_node_id="other")
        edge1.add_relationship(
            RelationshipDetail(relationship_type="works_for", source_id="src1")
        )
        kb.add_edge(edge1)

        # merged -> other
        edge2 = Edge(id="e2", source_node_id="merged", target_node_id="other")
        edge2.add_relationship(
            RelationshipDetail(relationship_type="ceo_of", source_id="src1")
        )
        kb.add_edge(edge2)

        return kb

    def test_merge_transfers_aliases(self, kb_with_nodes: KnowledgeBase) -> None:
        """Merge should transfer aliases including merged node's label."""
        history = kb_with_nodes.merge_nodes("survivor", "merged")

        survivor = kb_with_nodes.get_node("survivor")
        assert survivor is not None

        # Merged label should become an alias
        assert "Jon Smith" in survivor.aliases
        # Original merged aliases should transfer
        assert "Johnny" in survivor.aliases
        # Original survivor aliases preserved
        assert "J. Smith" in survivor.aliases

        # Check history
        assert history.merged_label == "Jon Smith"
        assert "Jon Smith" in history.merged_aliases

    def test_merge_redirects_edges(self, kb_with_edges: KnowledgeBase) -> None:
        """Merge should redirect edges to survivor."""
        # Before merge: 2 edges to "other"
        assert len(kb_with_edges._edges) == 2

        kb_with_edges.merge_nodes("survivor", "merged")

        # After merge: 1 edge (merged into existing)
        edge = kb_with_edges.get_edge_between("survivor", "other")
        assert edge is not None

        # Both relationship types should be on the edge
        rel_types = edge.get_relationship_types()
        assert "works_for" in rel_types
        assert "ceo_of" in rel_types

    def test_merge_combines_properties(self, kb_with_nodes: KnowledgeBase) -> None:
        """Merge should combine properties with survivor priority."""
        kb_with_nodes.merge_nodes("survivor", "merged")

        survivor = kb_with_nodes.get_node("survivor")
        assert survivor is not None

        # Survivor's value wins on conflict
        assert survivor.properties["age"] == 30
        # Non-conflicting properties transferred
        assert survivor.properties["city"] == "NYC"

    def test_merge_combines_source_ids(self, kb_with_nodes: KnowledgeBase) -> None:
        """Merge should combine source_ids."""
        kb_with_nodes.merge_nodes("survivor", "merged")

        survivor = kb_with_nodes.get_node("survivor")
        assert survivor is not None

        assert "src1" in survivor.source_ids
        assert "src2" in survivor.source_ids

    def test_merge_updates_indices(self, kb_with_nodes: KnowledgeBase) -> None:
        """Merge should update label/alias indices."""
        kb_with_nodes.merge_nodes("survivor", "merged")

        # Merged node's label should now resolve to survivor
        node = kb_with_nodes.get_node_by_label("Jon Smith")
        assert node is not None
        assert node.id == "survivor"

        # Merged node's alias should resolve to survivor
        node = kb_with_nodes.get_node_by_label("Johnny")
        assert node is not None
        assert node.id == "survivor"

    def test_merge_removes_merged_node(self, kb_with_nodes: KnowledgeBase) -> None:
        """Merge should remove the merged node."""
        kb_with_nodes.merge_nodes("survivor", "merged")

        # Merged node should be gone
        assert kb_with_nodes.get_node("merged") is None
        assert "merged" not in kb_with_nodes._nodes

    def test_merge_returns_history(self, kb_with_nodes: KnowledgeBase) -> None:
        """Merge should return a MergeHistory record."""
        history = kb_with_nodes.merge_nodes(
            survivor_id="survivor",
            merged_id="merged",
            merge_type="user",
            merged_by="session123",
        )

        assert isinstance(history, MergeHistory)
        assert history.survivor_id == "survivor"
        assert history.merged_id == "merged"
        assert history.merged_label == "Jon Smith"
        assert history.merge_type == "user"
        assert history.merged_by == "session123"

    def test_merge_nonexistent_survivor_raises(
        self, kb_with_nodes: KnowledgeBase
    ) -> None:
        """Merge with nonexistent survivor should raise ValueError."""
        with pytest.raises(ValueError, match="Survivor node not found"):
            kb_with_nodes.merge_nodes("nonexistent", "merged")

    def test_merge_nonexistent_merged_raises(
        self, kb_with_nodes: KnowledgeBase
    ) -> None:
        """Merge with nonexistent merged node should raise ValueError."""
        with pytest.raises(ValueError, match="Merged node not found"):
            kb_with_nodes.merge_nodes("survivor", "nonexistent")

    def test_merge_handles_self_loops(self, kb_with_edges: KnowledgeBase) -> None:
        """Merge should handle edges that would become self-loops."""
        # Add edge between the two nodes being merged
        edge = Edge(id="e_between", source_node_id="survivor", target_node_id="merged")
        edge.add_relationship(
            RelationshipDetail(relationship_type="knows", source_id="src1")
        )
        kb_with_edges.add_edge(edge)

        # Merge should succeed without creating self-loop
        kb_with_edges.merge_nodes("survivor", "merged")

        # Survivor should not have edge to itself
        self_edge = kb_with_edges.get_edge_between("survivor", "survivor")
        assert self_edge is None


class TestKnowledgeBaseAutoResolve:
    """Tests for auto-resolution of candidates."""

    @pytest.fixture
    def kb_with_duplicates(self) -> KnowledgeBase:
        """Create KB with potential duplicates."""
        kb = KnowledgeBase(name="Test KB")

        # Clear duplicates
        node1 = Node(id="n1", label="John Smith", entity_type="Person")
        node2 = Node(id="n2", label="Jon Smith", entity_type="Person")
        node3 = Node(id="n3", label="Alice Jones", entity_type="Person")

        kb.add_node(node1)
        kb.add_node(node2)
        kb.add_node(node3)

        return kb

    def test_auto_resolve_above_threshold(
        self, kb_with_duplicates: KnowledgeBase
    ) -> None:
        """auto_resolve should merge candidates above threshold."""
        # Create a high-confidence candidate
        candidate = ResolutionCandidate(
            node_a_id="n1",
            node_b_id="n2",
            confidence=0.95,
        )

        history = kb_with_duplicates.auto_resolve_candidates([candidate], threshold=0.9)

        assert len(history) == 1
        assert history[0].survivor_id == "n1"
        assert history[0].merged_id == "n2"
        assert history[0].merge_type == "auto"

    def test_auto_resolve_below_threshold(
        self, kb_with_duplicates: KnowledgeBase
    ) -> None:
        """auto_resolve should skip candidates below threshold."""
        candidate = ResolutionCandidate(
            node_a_id="n1",
            node_b_id="n2",
            confidence=0.85,
        )

        history = kb_with_duplicates.auto_resolve_candidates([candidate], threshold=0.9)

        assert len(history) == 0
        # Both nodes should still exist
        assert kb_with_duplicates.get_node("n1") is not None
        assert kb_with_duplicates.get_node("n2") is not None

    def test_auto_resolve_skips_already_merged(
        self, kb_with_duplicates: KnowledgeBase
    ) -> None:
        """auto_resolve should skip candidates where node was already merged."""
        # Add another potential duplicate
        kb_with_duplicates.add_node(
            Node(id="n4", label="J. Smith", entity_type="Person")
        )

        candidates = [
            ResolutionCandidate(node_a_id="n1", node_b_id="n2", confidence=0.95),
            ResolutionCandidate(node_a_id="n2", node_b_id="n4", confidence=0.92),
        ]

        history = kb_with_duplicates.auto_resolve_candidates(candidates, threshold=0.9)

        # First merge should happen
        assert len(history) >= 1
        # Second should be skipped because n2 was merged
        assert all(h.merged_id != "n4" or h.survivor_id != "n2" for h in history)


class TestKnowledgeBaseFindCandidates:
    """Tests for finding resolution candidates."""

    @pytest.fixture
    def kb_with_similar_nodes(self) -> KnowledgeBase:
        """Create KB with similar nodes."""
        kb = KnowledgeBase(name="Test KB")

        kb.add_node(Node(id="n1", label="Apple Inc", entity_type="Company"))
        kb.add_node(Node(id="n2", label="Apple Inc.", entity_type="Company"))
        kb.add_node(Node(id="n3", label="Microsoft", entity_type="Company"))

        return kb

    def test_find_resolution_candidates(
        self, kb_with_similar_nodes: KnowledgeBase
    ) -> None:
        """find_resolution_candidates should find similar nodes."""
        # Lower threshold since "Apple Inc" and "Apple Inc." differ by a period
        # which affects Jaccard alias overlap but string_sim is still ~0.98
        config = ResolutionConfig(review_threshold=0.5)
        candidates = kb_with_similar_nodes.find_resolution_candidates(config)

        # Apple Inc and Apple Inc. should be candidates
        assert len(candidates) >= 1

        # Find the Apple pair
        apple_pair = next(
            (
                c
                for c in candidates
                if (c.node_a_id in ("n1", "n2") and c.node_b_id in ("n1", "n2"))
            ),
            None,
        )
        assert apple_pair is not None
        assert apple_pair.confidence > 0.5

    def test_find_candidates_for_node(
        self, kb_with_similar_nodes: KnowledgeBase
    ) -> None:
        """find_candidates_for_node should find matches for a single node."""
        new_node = Node(id="n_new", label="Apple", entity_type="Company")

        # Lower threshold - "Apple" vs "Apple Inc" has moderate string similarity
        config = ResolutionConfig(review_threshold=0.5)
        candidates = kb_with_similar_nodes.find_candidates_for_node(new_node, config)

        # Should find Apple Inc and Apple Inc. as candidates
        assert len(candidates) >= 1
        ids = [c.node_b_id for c in candidates]
        assert "n1" in ids or "n2" in ids

    def test_find_candidates_for_node_respects_config(
        self, kb_with_similar_nodes: KnowledgeBase
    ) -> None:
        """find_candidates_for_node should use provided config."""
        new_node = Node(id="n_new", label="Apple", entity_type="Company")

        # Very high threshold
        config = ResolutionConfig(review_threshold=0.99)
        candidates = kb_with_similar_nodes.find_candidates_for_node(new_node, config)

        # Should find few or no candidates
        assert len(candidates) == 0


# ============================================================================
# KGProject Resolution Fields Tests
# ============================================================================


class TestKGProjectResolutionFields:
    """Tests for resolution fields on KGProject."""

    def test_project_has_resolution_fields(self) -> None:
        """KGProject should have resolution-related fields."""
        from app.kg.domain import KGProject

        project = KGProject(name="Test Project")

        assert hasattr(project, "pending_merges")
        assert hasattr(project, "merge_history")
        assert hasattr(project, "resolution_config")

        assert isinstance(project.pending_merges, list)
        assert isinstance(project.merge_history, list)
        assert isinstance(project.resolution_config, ResolutionConfig)

    def test_project_resolution_defaults(self) -> None:
        """KGProject resolution fields should have sensible defaults."""
        from app.kg.domain import KGProject

        project = KGProject(name="Test")

        assert project.pending_merges == []
        assert project.merge_history == []
        assert project.resolution_config.auto_merge_threshold == 0.9

    def test_project_stores_candidates(self) -> None:
        """KGProject should be able to store resolution candidates."""
        from app.kg.domain import KGProject

        project = KGProject(name="Test")
        candidate = ResolutionCandidate(
            node_a_id="n1", node_b_id="n2", confidence=0.85
        )
        project.pending_merges.append(candidate)

        assert len(project.pending_merges) == 1
        assert project.pending_merges[0].confidence == 0.85

    def test_project_stores_history(self) -> None:
        """KGProject should be able to store merge history."""
        from app.kg.domain import KGProject

        project = KGProject(name="Test")
        history = MergeHistory(
            survivor_id="s1",
            merged_id="m1",
            merged_label="Old",
            confidence=0.95,
        )
        project.merge_history.append(history)

        assert len(project.merge_history) == 1
        assert project.merge_history[0].merged_label == "Old"
