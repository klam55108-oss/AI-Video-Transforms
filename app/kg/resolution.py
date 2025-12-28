"""
Entity Resolution models and algorithms for Knowledge Graph duplicate detection.

This module provides:
- Models: ResolutionCandidate, MergeHistory, ResolutionConfig
- String similarity functions: Jaro-Winkler, Levenshtein, alias overlap (via rapidfuzz)
- N-gram blocking strategy for efficient candidate generation
- EntityMatcher class for computing similarity scores

The resolution system uses a multi-signal approach:
1. String similarity (label matching)
2. Alias overlap (shared alternative names)
3. Type matching (same entity type bonus)
4. Graph context (shared neighbors)
5. Semantic similarity (placeholder for future embedding support)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field
from rapidfuzz.distance import JaroWinkler, Levenshtein

from app.kg.normalization import generate_ngrams, normalize_entity_name

if TYPE_CHECKING:
    from app.kg.knowledge_base import KnowledgeBase
    from app.kg.models import Node


def _generate_short_id() -> str:
    """Generate an 8-character hex ID from UUID4."""
    return uuid4().hex[:8]


def _utc_now() -> datetime:
    """Get current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


# ============================================================================
# Resolution Models
# ============================================================================


class ResolutionCandidate(BaseModel):
    """
    A potential duplicate pair detected by entity resolution.

    Represents two nodes that may refer to the same real-world entity.
    Users or auto-resolution can approve/reject these candidates.

    Attributes:
        id: Unique 8-character identifier
        node_a_id: ID of the first node in the pair
        node_b_id: ID of the second node in the pair
        confidence: Overall confidence score (0.0-1.0)
        signals: Individual signal scores that contributed to confidence
        status: Resolution status (pending, approved, rejected)
        created_at: When this candidate was detected
    """

    id: str = Field(default_factory=_generate_short_id)
    node_a_id: str
    node_b_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    signals: dict[str, float] = Field(default_factory=dict)
    status: Literal["pending", "approved", "rejected"] = "pending"
    created_at: datetime = Field(default_factory=_utc_now)


class MergeHistory(BaseModel):
    """
    Audit trail record with rollback capability for a completed node merge.

    Tracks what was merged into what, with provenance for undo
    or debugging purposes. Includes safety fields for idempotency
    and rollback support.

    Attributes:
        id: Unique 8-character identifier
        survivor_id: ID of the node that remains after merge
        merged_id: ID of the node that was merged (no longer exists)
        merged_label: Original label of the merged node (for display)
        merged_aliases: Aliases that were added from merged node
        confidence: Confidence score at time of merge
        merge_type: How the merge was triggered (auto, user, agent)
        merged_at: When the merge occurred
        merged_by: Session ID for agent-triggered merges
        request_id: Idempotency key for duplicate request detection
        pre_merge_state: Snapshot of nodes/edges before merge (for rollback)
        survivor_label_before: Survivor's label before merge
        survivor_aliases_before: Survivor's aliases before merge
        edges_redirected: Number of edges redirected during merge
    """

    id: str = Field(default_factory=_generate_short_id)
    survivor_id: str
    merged_id: str
    merged_label: str
    merged_aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    merge_type: Literal["auto", "user", "agent"] = "user"
    merged_at: datetime = Field(default_factory=_utc_now)
    merged_by: str | None = None

    # Safety fields for idempotency and rollback
    request_id: str | None = None
    pre_merge_state: dict[str, Any] | None = None
    survivor_label_before: str | None = None
    survivor_aliases_before: list[str] = Field(default_factory=list)
    edges_redirected: int = 0


class ResolutionConfig(BaseModel):
    """
    Configuration for entity resolution algorithm.

    Defines thresholds and weights for different similarity signals.
    Weights should sum to approximately 1.0 for interpretable scores.

    Note: semantic_weight defaults to 0.0 until embedding support is added.
    The other weights sum to 1.0 for full score range without embeddings.

    Attributes:
        auto_merge_threshold: Minimum confidence for automatic merging
        review_threshold: Minimum confidence to surface as candidate
        string_weight: Weight for label string similarity (Jaro-Winkler)
        alias_weight: Weight for alias overlap (Jaccard)
        type_weight: Weight for entity type matching
        graph_weight: Weight for shared neighbors
        semantic_weight: Weight for semantic similarity (future, default 0)
    """

    auto_merge_threshold: float = Field(default=0.9, ge=0.0, le=1.0)
    review_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    string_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    alias_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    type_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    graph_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    semantic_weight: float = Field(default=0.0, ge=0.0, le=1.0)


# ============================================================================
# String Similarity Functions (using rapidfuzz for performance)
# ============================================================================


def jaro_winkler_similarity(s1: str, s2: str) -> float:
    """
    Compute Jaro-Winkler similarity between two strings.

    Uses rapidfuzz for optimized C implementation.
    Jaro-Winkler is particularly effective for name matching because
    it gives higher scores when strings share a common prefix.

    Args:
        s1: First string to compare.
        s2: Second string to compare.

    Returns:
        Similarity score between 0.0 and 1.0.

    Examples:
        >>> jaro_winkler_similarity("MARTHA", "MARHTA")
        0.961...
        >>> jaro_winkler_similarity("Elon Musk", "Elon Musk")
        1.0
    """
    # Handle empty strings
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    # Normalize using our domain-agnostic normalization
    s1_norm = normalize_entity_name(s1)
    s2_norm = normalize_entity_name(s2)

    if not s1_norm or not s2_norm:
        return 0.0
    if s1_norm == s2_norm:
        return 1.0

    # rapidfuzz.distance.JaroWinkler.normalized_similarity returns 0.0-1.0
    return JaroWinkler.normalized_similarity(s1_norm, s2_norm)


def levenshtein_similarity(s1: str, s2: str) -> float:
    """
    Compute normalized Levenshtein similarity between two strings.

    Uses rapidfuzz for optimized C implementation.
    Result is normalized to 0.0-1.0 range.

    Args:
        s1: First string to compare.
        s2: Second string to compare.

    Returns:
        Similarity score between 0.0 and 1.0.

    Examples:
        >>> levenshtein_similarity("kitten", "sitting")
        0.571...
        >>> levenshtein_similarity("hello", "hello")
        1.0
    """
    # Handle empty strings
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    # Normalize using our domain-agnostic normalization
    s1_norm = normalize_entity_name(s1)
    s2_norm = normalize_entity_name(s2)

    if not s1_norm or not s2_norm:
        return 0.0
    if s1_norm == s2_norm:
        return 1.0

    # rapidfuzz.distance.Levenshtein.normalized_similarity returns 0.0-1.0
    return Levenshtein.normalized_similarity(s1_norm, s2_norm)


def alias_overlap_score(aliases_a: list[str], aliases_b: list[str]) -> float:
    """
    Compute Jaccard similarity between two sets of aliases.

    Jaccard = |A intersection B| / |A union B|

    Both sets are normalized using domain-agnostic normalization.

    Args:
        aliases_a: First list of aliases.
        aliases_b: Second list of aliases.

    Returns:
        Jaccard similarity between 0.0 and 1.0.

    Examples:
        >>> alias_overlap_score(["Dr. Smith", "John"], ["John", "J. Smith"])
        0.333...
        >>> alias_overlap_score([], [])
        0.0
    """
    if not aliases_a and not aliases_b:
        return 0.0

    # Normalize using our domain-agnostic normalization
    set_a = {normalize_entity_name(a) for a in aliases_a if a}
    set_b = {normalize_entity_name(b) for b in aliases_b if b}

    # Remove empty strings that may result from normalization
    set_a.discard("")
    set_b.discard("")

    if not set_a and not set_b:
        return 0.0

    union = set_a | set_b
    if not union:
        return 0.0

    intersection = set_a & set_b
    return len(intersection) / len(union)


# ============================================================================
# Blocking Strategy (N-gram based)
# ============================================================================


def _block_by_ngrams(
    nodes: list[Node],
    n: int = 3,
    min_shared_ngrams: int = 2,
) -> list[tuple[int, int]]:
    """
    Find candidate pairs using n-gram blocking.

    Builds an inverted index of ngram -> node indices, then finds pairs
    that share at least min_shared_ngrams. This is more effective than
    first-character blocking for catching typos and variations.

    Args:
        nodes: List of Node objects to find candidates among.
        n: Size of n-grams to generate (default: 3 for trigrams).
        min_shared_ngrams: Minimum shared n-grams to consider a pair (default: 2).

    Returns:
        List of (index_a, index_b) tuples where index_a < index_b.
    """
    if len(nodes) < 2:
        return []

    # Build inverted index: ngram -> set of node indices
    ngram_to_indices: dict[str, set[int]] = defaultdict(set)

    for idx, node in enumerate(nodes):
        label = node.label if node.label else ""
        ngrams = generate_ngrams(label, n)

        # Also include ngrams from aliases for better recall
        for alias in node.aliases:
            ngrams.update(generate_ngrams(alias, n))

        for ngram in ngrams:
            ngram_to_indices[ngram].add(idx)

    # Count shared ngrams between pairs
    pair_counts: dict[tuple[int, int], int] = defaultdict(int)

    for indices in ngram_to_indices.values():
        indices_list = sorted(indices)
        for i, idx_a in enumerate(indices_list):
            for idx_b in indices_list[i + 1 :]:
                pair_counts[(idx_a, idx_b)] += 1

    # Filter pairs by minimum shared ngrams
    candidate_pairs = [
        pair for pair, count in pair_counts.items() if count >= min_shared_ngrams
    ]

    return candidate_pairs


def _block_by_first_char(nodes: list[Node]) -> dict[str, list[Node]]:
    """
    Group nodes by first character of their label for blocking.

    DEPRECATED: Use _block_by_ngrams instead for better accuracy.

    Blocking reduces the O(n^2) comparison space by only comparing
    nodes within the same block. Nodes with empty labels go to "_" block.

    Args:
        nodes: List of Node objects to group.

    Returns:
        Dictionary mapping first character to list of nodes.
    """
    blocks: dict[str, list[Node]] = {}

    for node in nodes:
        label = normalize_entity_name(node.label) if node.label else ""
        key = label[0] if label else "_"

        if key not in blocks:
            blocks[key] = []
        blocks[key].append(node)

    return blocks


# ============================================================================
# Entity Matcher
# ============================================================================


class EntityMatcher:
    """
    Computes similarity between entity nodes for resolution.

    Uses multiple signals weighted by ResolutionConfig:
    - String similarity (Jaro-Winkler on labels)
    - Alias overlap (Jaccard on alias sets)
    - Type matching (same entity type bonus)
    - Graph context (shared neighbors in KnowledgeBase)
    - Semantic similarity (placeholder, returns 0.0)

    Example:
        matcher = EntityMatcher()
        score, signals = matcher.compute_similarity(node_a, node_b, kb)
        candidates = matcher.find_candidates(nodes, kb, min_confidence=0.7)
    """

    def __init__(self, config: ResolutionConfig | None = None) -> None:
        """
        Initialize the EntityMatcher with configuration.

        Args:
            config: Optional ResolutionConfig. Uses defaults if not provided.
        """
        self.config = config or ResolutionConfig()

    def compute_similarity(
        self,
        node_a: Node,
        node_b: Node,
        kb: KnowledgeBase | None = None,
    ) -> tuple[float, dict[str, float]]:
        """
        Compute similarity score between two nodes.

        Combines multiple signals using configured weights:
        - string_sim: Jaro-Winkler similarity on labels
        - alias_sim: Jaccard overlap on alias sets
        - type_sim: 1.0 if same type, 0.0 otherwise
        - graph_sim: Jaccard overlap on neighbor sets
        - semantic_sim: Placeholder (always 0.0)

        Args:
            node_a: First node to compare
            node_b: Second node to compare
            kb: Optional KnowledgeBase for graph context

        Returns:
            Tuple of (overall_confidence, signal_dict)
        """
        signals: dict[str, float] = {}
        config = self.config

        # 1. String similarity on labels
        string_sim = jaro_winkler_similarity(node_a.label, node_b.label)
        signals["string_sim"] = string_sim

        # 2. Alias overlap
        # Include labels in alias sets for cross-matching
        aliases_a = list(node_a.aliases) + [node_a.label]
        aliases_b = list(node_b.aliases) + [node_b.label]
        alias_sim = alias_overlap_score(aliases_a, aliases_b)
        signals["alias_sim"] = alias_sim

        # 3. Type matching
        type_sim = 1.0 if node_a.entity_type == node_b.entity_type else 0.0
        signals["type_sim"] = type_sim

        # 4. Graph context (shared neighbors)
        graph_sim = 0.0
        if kb is not None:
            neighbors_a = {n.id for n in kb.get_neighbors(node_a.id)}
            neighbors_b = {n.id for n in kb.get_neighbors(node_b.id)}

            if neighbors_a or neighbors_b:
                union = neighbors_a | neighbors_b
                intersection = neighbors_a & neighbors_b
                if union:
                    graph_sim = len(intersection) / len(union)
        signals["graph_sim"] = graph_sim

        # 5. Semantic similarity (placeholder for embeddings)
        semantic_sim = 0.0
        signals["semantic_sim"] = semantic_sim

        # Compute weighted average
        confidence = (
            config.string_weight * string_sim
            + config.alias_weight * alias_sim
            + config.type_weight * type_sim
            + config.graph_weight * graph_sim
            + config.semantic_weight * semantic_sim
        )

        return confidence, signals

    def find_candidates(
        self,
        nodes: list[Node],
        kb: KnowledgeBase | None = None,
        min_confidence: float = 0.5,
        use_ngram_blocking: bool = True,
        min_shared_ngrams: int = 2,
    ) -> list[ResolutionCandidate]:
        """
        Find potential duplicate pairs among a set of nodes.

        Uses n-gram blocking (default) or first-character blocking to reduce
        the O(n^2) comparison space, then scores candidate pairs.

        Args:
            nodes: List of nodes to search for duplicates.
            kb: Optional KnowledgeBase for graph context.
            min_confidence: Minimum confidence to include as candidate.
            use_ngram_blocking: If True, use n-gram blocking (default).
                If False, use first-character blocking (legacy).
            min_shared_ngrams: Minimum shared n-grams for blocking (default: 2).

        Returns:
            List of ResolutionCandidate objects sorted by confidence (desc).
        """
        candidates: list[ResolutionCandidate] = []

        if use_ngram_blocking:
            # Use n-gram blocking for better accuracy
            candidate_pairs = _block_by_ngrams(
                nodes, n=3, min_shared_ngrams=min_shared_ngrams
            )

            for idx_a, idx_b in candidate_pairs:
                node_a = nodes[idx_a]
                node_b = nodes[idx_b]
                confidence, signals = self.compute_similarity(node_a, node_b, kb)

                if confidence >= min_confidence:
                    candidate = ResolutionCandidate(
                        node_a_id=node_a.id,
                        node_b_id=node_b.id,
                        confidence=confidence,
                        signals=signals,
                    )
                    candidates.append(candidate)
        else:
            # Legacy: Block nodes by first character
            blocks = _block_by_first_char(nodes)

            # Compare within each block
            for block_nodes in blocks.values():
                for i, node_a in enumerate(block_nodes):
                    for node_b in block_nodes[i + 1 :]:
                        confidence, signals = self.compute_similarity(
                            node_a, node_b, kb
                        )

                        if confidence >= min_confidence:
                            candidate = ResolutionCandidate(
                                node_a_id=node_a.id,
                                node_b_id=node_b.id,
                                confidence=confidence,
                                signals=signals,
                            )
                            candidates.append(candidate)

        # Sort by confidence descending
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates
