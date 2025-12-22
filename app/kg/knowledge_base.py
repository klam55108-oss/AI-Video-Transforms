"""
KnowledgeBase — the actual graph data structure.

Manages nodes, edges, and sources. Uses NetworkX internally
for graph operations (neighbors, paths, etc.).

This class is the runtime representation of extracted knowledge.
It holds the actual entities and relationships, separate from
the DomainProfile which defines the schema/types to extract.

Design Decisions:
- In-memory storage with dict-based lookups for performance
- NetworkX DiGraph for graph algorithms (paths, neighbors)
- Dual index for label/alias lookup (case-insensitive)
- Single Edge per node pair with multiple RelationshipDetails
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import networkx as nx  # type: ignore[import-untyped]

from app.kg.domain import DomainProfile
from app.kg.models import Edge, Node, RelationshipDetail, Source


def _generate_id() -> str:
    """Generate a 12-character hex ID from UUID4."""
    return uuid4().hex[:12]


def _utc_now() -> datetime:
    """Get current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


class KnowledgeBase:
    """
    In-memory knowledge graph with NetworkX backend.

    Manages the actual graph data: nodes (entities), edges (relationships),
    and sources (provenance). Uses NetworkX internally for graph algorithms
    like path finding and neighbor discovery.

    The KnowledgeBase is associated with a DomainProfile that defines
    what types of entities and relationships should be extracted.

    Usage:
        kb = KnowledgeBase(name="MK-Ultra Research", domain_profile=profile)
        kb.add_node(Node(label="CIA", entity_type="Organization"))
        kb.add_relationship("Sidney Gottlieb", "CIA", "worked_for", source_id)

    Attributes:
        id: Unique 12-character identifier
        name: Human-readable name for this knowledge base
        description: Optional description of the knowledge base's purpose
        domain_profile: DomainProfile defining extraction schema (optional)
        created_at: When this knowledge base was created
        updated_at: When this knowledge base was last modified
    """

    def __init__(
        self,
        id: str | None = None,
        name: str = "Untitled",
        description: str | None = None,
        domain_profile: DomainProfile | None = None,
    ) -> None:
        """
        Initialize a new KnowledgeBase.

        Args:
            id: Optional ID (auto-generated if not provided)
            name: Human-readable name for the knowledge base
            description: Optional description of the KB's purpose
            domain_profile: Optional DomainProfile for extraction guidance
        """
        self.id = id or _generate_id()
        self.name = name
        self.description = description
        self.domain_profile = domain_profile

        # Internal storage: id -> model
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, Edge] = {}
        self._sources: dict[str, Source] = {}

        # Label indexes for fast lookup (case-insensitive)
        self._label_to_id: dict[str, str] = {}  # label.lower() -> node_id
        self._alias_to_id: dict[str, str] = {}  # alias.lower() -> node_id

        # NetworkX graph for algorithms
        self._graph: nx.DiGraph = nx.DiGraph()

        self.created_at = _utc_now()
        self.updated_at = _utc_now()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # NODE OPERATIONS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def add_node(self, node: Node) -> Node:
        """
        Add a node to the knowledge graph.

        Adds the node to internal storage, indexes its label and aliases
        for fast lookup, and adds it to the NetworkX graph.

        Args:
            node: The Node to add

        Returns:
            The added Node (same object)
        """
        self._nodes[node.id] = node
        self._label_to_id[node.label.lower()] = node.id

        # Index all aliases
        for alias in node.aliases:
            self._alias_to_id[alias.lower()] = node.id

        # Add to NetworkX graph with node data (including segment_ids)
        self._graph.add_node(node.id, **node.model_dump())
        self.updated_at = _utc_now()

        return node

    def get_node(self, node_id: str) -> Node | None:
        """
        Get a node by its ID.

        Args:
            node_id: The unique ID of the node

        Returns:
            The Node if found, None otherwise
        """
        return self._nodes.get(node_id)

    def get_node_by_label(self, label: str) -> Node | None:
        """
        Get a node by label or alias (case-insensitive).

        Searches first by primary label, then by aliases.
        This enables flexible entity reference by any known name.

        Args:
            label: The label or alias to search for

        Returns:
            The Node if found, None otherwise
        """
        label_lower = label.lower()

        # Try primary label first
        node_id = self._label_to_id.get(label_lower)
        if node_id:
            return self._nodes.get(node_id)

        # Try aliases
        node_id = self._alias_to_id.get(label_lower)
        if node_id:
            return self._nodes.get(node_id)

        return None

    def get_or_create_node(
        self,
        label: str,
        entity_type: str,
        **kwargs: Any,
    ) -> tuple[Node, bool]:
        """
        Get an existing node by label or create a new one.

        Attempts to find a node by label (case-insensitive).
        If not found, creates a new node with the given parameters.

        Args:
            label: Primary label for the entity
            entity_type: Type of entity (e.g., "Person", "Organization")
            **kwargs: Additional Node fields (aliases, description, etc.)

        Returns:
            Tuple of (Node, created: bool) where created is True if new
        """
        existing = self.get_node_by_label(label)
        if existing:
            return existing, False

        node = Node(label=label, entity_type=entity_type, **kwargs)
        self.add_node(node)
        return node, True

    def find_nodes(
        self,
        label: str | None = None,
        entity_type: str | None = None,
    ) -> list[Node]:
        """
        Find nodes matching the given criteria.

        Supports filtering by partial label match (case-insensitive)
        and/or exact entity type match.

        Args:
            label: Optional partial label to match (case-insensitive)
            entity_type: Optional exact entity type to match

        Returns:
            List of matching Nodes
        """
        results = []

        for node in self._nodes.values():
            # Filter by label substring if provided
            if label and label.lower() not in node.label.lower():
                continue
            # Filter by exact entity type if provided
            if entity_type and node.entity_type != entity_type:
                continue
            results.append(node)

        return results

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EDGE OPERATIONS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def add_edge(self, edge: Edge) -> Edge:
        """
        Add an edge to the knowledge graph.

        Adds the edge to internal storage and creates the corresponding
        edge in the NetworkX graph with relationship type metadata.

        Args:
            edge: The Edge to add

        Returns:
            The added Edge (same object)
        """
        self._edges[edge.id] = edge

        # Add to NetworkX with relationship types as edge data
        self._graph.add_edge(
            edge.source_node_id,
            edge.target_node_id,
            edge_id=edge.id,
            relationships=[r.relationship_type for r in edge.relationships],
        )

        self.updated_at = _utc_now()
        return edge

    def get_edge(self, edge_id: str) -> Edge | None:
        """
        Get an edge by its ID.

        Args:
            edge_id: The unique ID of the edge

        Returns:
            The Edge if found, None otherwise
        """
        return self._edges.get(edge_id)

    def get_edge_between(self, source_id: str, target_id: str) -> Edge | None:
        """
        Get the edge between two nodes by their IDs.

        Args:
            source_id: ID of the source node
            target_id: ID of the target node

        Returns:
            The Edge if found, None otherwise
        """
        for edge in self._edges.values():
            if edge.source_node_id == source_id and edge.target_node_id == target_id:
                return edge
        return None

    def get_or_create_edge(self, source_id: str, target_id: str) -> tuple[Edge, bool]:
        """
        Get an existing edge or create a new one.

        Attempts to find an edge between the two nodes.
        If not found, creates a new empty edge.

        Args:
            source_id: ID of the source node
            target_id: ID of the target node

        Returns:
            Tuple of (Edge, created: bool) where created is True if new
        """
        existing = self.get_edge_between(source_id, target_id)
        if existing:
            return existing, False

        edge = Edge(source_node_id=source_id, target_node_id=target_id)
        self.add_edge(edge)
        return edge, True

    def add_relationship(
        self,
        source_label: str,
        target_label: str,
        relationship_type: str,
        source_id: str,
        confidence: float = 1.0,
        evidence: str | None = None,
    ) -> Edge | None:
        """
        Add a relationship between two nodes by label.

        Looks up nodes by label, creates or gets the edge between them,
        and adds a new RelationshipDetail. Returns None if either node
        is not found.

        Args:
            source_label: Label of the source entity
            target_label: Label of the target entity
            relationship_type: Type of relationship (e.g., "worked_for")
            source_id: ID of the Source this relationship came from
            confidence: Confidence score 0.0-1.0 (default 1.0)
            evidence: Optional supporting quote or context

        Returns:
            The Edge with the new relationship, or None if nodes not found
        """
        source_node = self.get_node_by_label(source_label)
        target_node = self.get_node_by_label(target_label)

        if not source_node or not target_node:
            return None

        edge, _ = self.get_or_create_edge(source_node.id, target_node.id)

        detail = RelationshipDetail(
            relationship_type=relationship_type,
            source_id=source_id,
            confidence=confidence,
            evidence=evidence,
        )
        edge.add_relationship(detail)

        # Update NetworkX edge data with new relationship types
        self._graph[source_node.id][target_node.id]["relationships"] = (
            edge.get_relationship_types()
        )

        return edge

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SOURCE OPERATIONS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def add_source(self, source: Source) -> Source:
        """
        Add a content source to the knowledge base.

        Sources track provenance for extracted entities and relationships.

        Args:
            source: The Source to add

        Returns:
            The added Source (same object)
        """
        self._sources[source.id] = source
        self.updated_at = _utc_now()
        return source

    def get_source(self, source_id: str) -> Source | None:
        """
        Get a source by its ID.

        Args:
            source_id: The unique ID of the source

        Returns:
            The Source if found, None otherwise
        """
        return self._sources.get(source_id)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # GRAPH QUERIES
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_neighbors(self, node_id: str) -> list[Node]:
        """
        Get all nodes connected to a given node.

        Returns both predecessors (nodes pointing TO this node) and
        successors (nodes this node points TO) in the directed graph.

        Args:
            node_id: ID of the node to find neighbors for

        Returns:
            List of neighboring Nodes (empty if node not found)
        """
        if node_id not in self._graph:
            return []

        # Combine successors (outgoing) and predecessors (incoming)
        neighbor_ids = set(self._graph.successors(node_id)) | set(
            self._graph.predecessors(node_id)
        )
        return [self._nodes[nid] for nid in neighbor_ids if nid in self._nodes]

    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_length: int = 5,
    ) -> list[list[str]]:
        """
        Find all simple paths between two nodes.

        Uses NetworkX's all_simple_paths algorithm with a cutoff
        to limit path length. Returns up to 10 paths to prevent
        explosion on highly connected graphs.

        Args:
            source_id: ID of the starting node
            target_id: ID of the ending node
            max_length: Maximum path length (default 5)

        Returns:
            List of paths, where each path is a list of node IDs
        """
        if source_id not in self._graph or target_id not in self._graph:
            return []

        try:
            paths = list(
                nx.all_simple_paths(
                    self._graph,
                    source_id,
                    target_id,
                    cutoff=max_length,
                )
            )
            return paths[:10]  # Limit results to prevent explosion
        except nx.NetworkXNoPath:
            return []

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STATISTICS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def stats(self) -> dict[str, Any]:
        """
        Get statistics about the knowledge graph.

        Returns counts of nodes, edges, and sources, plus breakdowns
        by entity type and relationship type.

        Returns:
            Dictionary with:
            - node_count: Total number of nodes
            - edge_count: Total number of edges
            - source_count: Total number of sources
            - entity_types: Dict mapping entity type -> count
            - relationship_types: Dict mapping relationship type -> count
        """
        # Count nodes by entity type
        entity_types: dict[str, int] = {}
        for node in self._nodes.values():
            entity_types[node.entity_type] = entity_types.get(node.entity_type, 0) + 1

        # Count relationships by type (across all edges)
        relationship_types: dict[str, int] = {}
        for edge in self._edges.values():
            for rel in edge.relationships:
                relationship_types[rel.relationship_type] = (
                    relationship_types.get(rel.relationship_type, 0) + 1
                )

        return {
            "node_count": len(self._nodes),
            "edge_count": len(self._edges),
            "source_count": len(self._sources),
            "entity_types": entity_types,
            "relationship_types": relationship_types,
        }
