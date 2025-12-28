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

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # INSIGHTS QUERIES
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _find_node_by_label(self, label: str) -> Node | None:
        """
        Find a node by label (case-insensitive).

        Helper method for insights queries that need to resolve
        user-provided entity names to node IDs.

        Args:
            label: The label to search for (case-insensitive)

        Returns:
            The Node if found, None otherwise
        """
        return self.get_node_by_label(label)

    def get_key_entities(
        self,
        limit: int = 10,
        method: str = "connections",
        entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Find the most important entities in the graph.

        Supports three ranking methods:
        - "connections": Degree centrality (most relationships)
        - "influence": PageRank (connected to important entities)
        - "bridging": Betweenness centrality (connects groups)

        Args:
            limit: Maximum number of entities to return (default 10)
            method: Ranking method - "connections", "influence", or "bridging"
            entity_type: Optional filter by entity type

        Returns:
            List of dicts with {node_id, label, entity_type, score, why}
        """
        if len(self._nodes) == 0:
            return []

        # Get the undirected view for centrality calculations
        undirected = self._graph.to_undirected()

        # Calculate centrality based on method
        if method == "influence":
            try:
                centrality = nx.pagerank(self._graph)
            except nx.NetworkXError:
                # PageRank can fail on empty graphs
                centrality = {node_id: 0.0 for node_id in self._nodes}
            why_template = "Influences {score:.0%} of the network through connections"
        elif method == "bridging":
            try:
                centrality = nx.betweenness_centrality(undirected)
            except nx.NetworkXError:
                centrality = {node_id: 0.0 for node_id in self._nodes}
            why_template = "Bridges {pct:.0%} of shortest paths between entities"
        else:  # Default: connections (degree centrality)
            centrality = dict(undirected.degree())
            why_template = "Connected to {count} other entities"

        # Build results with optional entity_type filter
        results: list[dict[str, Any]] = []
        for node_id, score in centrality.items():
            node = self._nodes.get(node_id)
            if not node:
                continue

            # Apply entity_type filter if specified
            if entity_type and node.entity_type != entity_type:
                continue

            # Generate human-readable "why" explanation
            if method == "connections":
                why = why_template.format(count=int(score))
            elif method == "bridging":
                why = why_template.format(pct=score)
            else:
                why = why_template.format(score=score)

            results.append({
                "node_id": node_id,
                "label": node.label,
                "entity_type": node.entity_type,
                "score": float(score),
                "why": why,
            })

        # Sort by score descending and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def find_connection(
        self,
        entity_1: str,
        entity_2: str,
    ) -> dict[str, Any]:
        """
        Show how two entities connect via shortest path.

        Uses NetworkX shortest_path on undirected graph to find
        the most direct connection between two entities.

        Args:
            entity_1: Label of the first entity
            entity_2: Label of the second entity

        Returns:
            Dict with {connected, steps, path, explanation}
            Path items contain {entity, relationship, direction}
        """
        # Resolve labels to nodes
        node1 = self._find_node_by_label(entity_1)
        node2 = self._find_node_by_label(entity_2)

        if not node1:
            return {
                "connected": False,
                "steps": 0,
                "path": [],
                "explanation": f"Entity '{entity_1}' not found in graph",
            }

        if not node2:
            return {
                "connected": False,
                "steps": 0,
                "path": [],
                "explanation": f"Entity '{entity_2}' not found in graph",
            }

        if node1.id == node2.id:
            return {
                "connected": True,
                "steps": 0,
                "path": [{"entity": node1.label, "relationship": None, "direction": None}],
                "explanation": "Same entity",
            }

        # Find shortest path on undirected graph
        undirected = self._graph.to_undirected()
        try:
            path_ids = nx.shortest_path(undirected, node1.id, node2.id)
        except nx.NetworkXNoPath:
            return {
                "connected": False,
                "steps": 0,
                "path": [],
                "explanation": f"No connection found between '{entity_1}' and '{entity_2}'",
            }

        # Build detailed path with relationships
        path_details: list[dict[str, Any]] = []
        for i, node_id in enumerate(path_ids):
            node = self._nodes.get(node_id)
            if not node:
                continue

            path_item: dict[str, Any] = {
                "entity": node.label,
                "relationship": None,
                "direction": None,
            }

            # Add relationship info for edges (not the last node)
            if i < len(path_ids) - 1:
                next_id = path_ids[i + 1]
                # Check forward edge
                edge = self.get_edge_between(node_id, next_id)
                if edge:
                    rel_types = edge.get_relationship_types()
                    path_item["relationship"] = rel_types[0] if rel_types else "connected"
                    path_item["direction"] = "outgoing"
                else:
                    # Check reverse edge
                    edge = self.get_edge_between(next_id, node_id)
                    if edge:
                        rel_types = edge.get_relationship_types()
                        path_item["relationship"] = rel_types[0] if rel_types else "connected"
                        path_item["direction"] = "incoming"

            path_details.append(path_item)

        steps = len(path_ids) - 1
        explanation = f"Connected through {steps} step{'s' if steps != 1 else ''}"

        return {
            "connected": True,
            "steps": steps,
            "path": path_details,
            "explanation": explanation,
        }

    def find_common_ground(
        self,
        entity_1: str,
        entity_2: str,
    ) -> list[dict[str, Any]]:
        """
        Find shared neighbors between two entities.

        Identifies entities that both entity_1 and entity_2
        are directly connected to.

        Args:
            entity_1: Label of the first entity
            entity_2: Label of the second entity

        Returns:
            List of shared connections with explanation
        """
        node1 = self._find_node_by_label(entity_1)
        node2 = self._find_node_by_label(entity_2)

        if not node1 or not node2:
            return []

        # Get neighbors of both nodes
        neighbors1 = set(n.id for n in self.get_neighbors(node1.id))
        neighbors2 = set(n.id for n in self.get_neighbors(node2.id))

        # Find intersection
        common_ids = neighbors1 & neighbors2

        results: list[dict[str, Any]] = []
        for common_id in common_ids:
            common_node = self._nodes.get(common_id)
            if not common_node:
                continue

            # Describe the relationships
            rel1 = self._describe_relationship(node1.id, common_id)
            rel2 = self._describe_relationship(node2.id, common_id)

            results.append({
                "entity": common_node.label,
                "entity_type": common_node.entity_type,
                "connection_to_first": rel1,
                "connection_to_second": rel2,
                "explanation": f"Both {entity_1} and {entity_2} are connected to {common_node.label}",
            })

        return results

    def _describe_relationship(self, from_id: str, to_id: str) -> str:
        """
        Get a text description of the relationship between two nodes.

        Args:
            from_id: Source node ID
            to_id: Target node ID

        Returns:
            Description string like "worked_for (outgoing)" or "unknown"
        """
        # Check forward edge
        edge = self.get_edge_between(from_id, to_id)
        if edge:
            types = edge.get_relationship_types()
            return f"{types[0]} (outgoing)" if types else "connected (outgoing)"

        # Check reverse edge
        edge = self.get_edge_between(to_id, from_id)
        if edge:
            types = edge.get_relationship_types()
            return f"{types[0]} (incoming)" if types else "connected (incoming)"

        return "connected"

    def discover_groups(self) -> list[dict[str, Any]]:
        """
        Discover clusters of related entities using community detection.

        Uses Louvain community detection algorithm on the undirected
        graph to find groups of closely connected entities.

        Returns:
            List of groups with {name, entities, size, sample}
            Name is derived from the most connected entity in each group
        """
        if len(self._nodes) == 0:
            return []

        undirected = self._graph.to_undirected()

        # Handle disconnected graphs by only analyzing largest component
        if not nx.is_connected(undirected):
            # Get all connected components
            components = list(nx.connected_components(undirected))
            if not components:
                return []
            # Use largest component for community detection
            largest = max(components, key=len)
            undirected = undirected.subgraph(largest).copy()

        if len(undirected.nodes()) < 2:
            # Single node or empty - return as one group
            if len(undirected.nodes()) == 1:
                node_id = list(undirected.nodes())[0]
                node = self._nodes.get(node_id)
                if node:
                    return [{
                        "name": f"{node.label} group",
                        "entities": [node.label],
                        "size": 1,
                        "sample": [node.label],
                    }]
            return []

        try:
            communities = nx.community.louvain_communities(undirected, seed=42)
        except Exception:
            # Fallback if Louvain fails
            return []

        results: list[dict[str, Any]] = []
        for community in communities:
            # Get node labels for this community
            entities = []
            best_node = None
            best_degree = -1

            for node_id in community:
                node = self._nodes.get(node_id)
                if node:
                    entities.append(node.label)
                    degree = undirected.degree(node_id)
                    if degree > best_degree:
                        best_degree = degree
                        best_node = node

            if not entities:
                continue

            # Name group after most connected entity
            group_name = f"{best_node.label} group" if best_node else "Unknown group"

            results.append({
                "name": group_name,
                "entities": entities,
                "size": len(entities),
                "sample": entities[:5],  # First 5 as sample
            })

        # Sort by size descending
        results.sort(key=lambda x: x["size"], reverse=True)
        return results

    def find_isolated_topics(self) -> list[dict[str, Any]]:
        """
        Find isolated groups with no connection to the main graph.

        Uses connected_components on undirected view to identify
        disconnected subgraphs that might represent separate topics.

        Returns:
            List of isolated groups (all components except the largest)
        """
        if len(self._nodes) == 0:
            return []

        undirected = self._graph.to_undirected()
        components = list(nx.connected_components(undirected))

        if len(components) <= 1:
            return []  # No isolated groups

        # Sort by size, largest first
        components.sort(key=len, reverse=True)

        # Skip the main (largest) component, return the rest as "isolated"
        results: list[dict[str, Any]] = []
        for component in components[1:]:  # Skip first (main) component
            entities = []
            for node_id in component:
                node = self._nodes.get(node_id)
                if node:
                    entities.append(node.label)

            if entities:
                results.append({
                    "entities": entities,
                    "size": len(entities),
                    "sample": entities[:5],
                    "explanation": f"Group of {len(entities)} entities disconnected from main graph",
                })

        return results

    def get_mentions(self, entity: str) -> list[dict[str, Any]]:
        """
        Find where an entity appears in sources.

        Looks at the node's source_ids and cross-references with
        stored Source objects to provide provenance information.

        Args:
            entity: Label of the entity to look up

        Returns:
            List of {source_title, source_type, mention_count}
        """
        node = self._find_node_by_label(entity)
        if not node:
            return []

        results: list[dict[str, Any]] = []
        for source_id in node.source_ids:
            source = self._sources.get(source_id)
            if source:
                results.append({
                    "source_id": source.id,
                    "source_title": source.title,
                    "source_type": source.source_type.value,
                    "mention_count": 1,  # Each source_id represents one mention
                })
            else:
                # Source not found but ID is tracked
                results.append({
                    "source_id": source_id,
                    "source_title": f"Source {source_id}",
                    "source_type": "unknown",
                    "mention_count": 1,
                })

        return results

    def get_evidence(
        self,
        entity_1: str,
        entity_2: str,
    ) -> list[dict[str, Any]]:
        """
        Get actual quotes/evidence for relationships between entities.

        Retrieves the evidence field from RelationshipDetails on
        edges connecting the two entities.

        Args:
            entity_1: Label of the first entity
            entity_2: Label of the second entity

        Returns:
            List of {relationship_type, quote, source_title, confidence}
        """
        node1 = self._find_node_by_label(entity_1)
        node2 = self._find_node_by_label(entity_2)

        if not node1 or not node2:
            return []

        results: list[dict[str, Any]] = []

        # Check edge in both directions
        for source_id, target_id in [(node1.id, node2.id), (node2.id, node1.id)]:
            edge = self.get_edge_between(source_id, target_id)
            if not edge:
                continue

            for rel in edge.relationships:
                source = self._sources.get(rel.source_id)
                source_title = source.title if source else f"Source {rel.source_id}"

                results.append({
                    "relationship_type": rel.relationship_type,
                    "quote": rel.evidence,
                    "source_title": source_title,
                    "source_id": rel.source_id,
                    "confidence": rel.confidence,
                })

        return results

    def get_smart_suggestions(self) -> list[dict[str, Any]]:
        """
        Analyze the graph and suggest what to explore next.

        This is the "Power Query" that generates intelligent
        exploration suggestions based on graph structure.

        Checks:
        - Graph size and density
        - Most connected entities
        - Isolated groups
        - Entity type distribution
        - Underexplored relationships

        Returns:
            List of {question, why, action, priority} suggestions
        """
        suggestions: list[dict[str, Any]] = []
        stats = self.stats()

        node_count = stats["node_count"]
        edge_count = stats["edge_count"]
        entity_types = stats["entity_types"]

        # Check if graph is empty
        if node_count == 0:
            suggestions.append({
                "question": "What content should we analyze first?",
                "why": "Your knowledge graph is empty",
                "action": "bootstrap",
                "priority": "high",
            })
            return suggestions

        # Find key entities to suggest exploration
        key_entities = self.get_key_entities(limit=3, method="connections")
        if key_entities:
            top_entity = key_entities[0]
            suggestions.append({
                "question": f"Who or what is connected to {top_entity['label']}?",
                "why": f"{top_entity['label']} is the most connected entity ({top_entity['why']})",
                "action": "explore_entity",
                "action_params": {"entity": top_entity["label"]},
                "priority": "high",
            })

        # Check for isolated topics
        isolated = self.find_isolated_topics()
        if isolated:
            first_isolated = isolated[0]
            sample = first_isolated["sample"][0] if first_isolated["sample"] else "unknown"
            suggestions.append({
                "question": f"How does {sample} connect to the main graph?",
                "why": f"Found {len(isolated)} isolated group(s) disconnected from the main network",
                "action": "find_connection",
                "action_params": {"isolated_group": first_isolated["entities"]},
                "priority": "medium",
            })

        # Check entity type distribution for imbalances
        if entity_types:
            type_counts = list(entity_types.items())
            type_counts.sort(key=lambda x: x[1], reverse=True)
            most_common = type_counts[0]
            if len(type_counts) > 1:
                least_common = type_counts[-1]
                if most_common[1] > 3 * least_common[1]:
                    suggestions.append({
                        "question": f"Are there more {least_common[0]} entities to discover?",
                        "why": f"Only {least_common[1]} {least_common[0]} vs {most_common[1]} {most_common[0]}",
                        "action": "explore_type",
                        "action_params": {"entity_type": least_common[0]},
                        "priority": "low",
                    })

        # Suggest exploring relationships if graph is sparse
        if node_count > 5 and edge_count < node_count:
            suggestions.append({
                "question": "What relationships are we missing?",
                "why": f"Only {edge_count} connections between {node_count} entities (sparse graph)",
                "action": "discover_relationships",
                "priority": "medium",
            })

        # Suggest community analysis for larger graphs
        if node_count >= 10:
            suggestions.append({
                "question": "What groups or clusters exist in this data?",
                "why": f"Graph has {node_count} entities - community detection may reveal structure",
                "action": "discover_groups",
                "priority": "low",
            })

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda x: priority_order.get(x["priority"], 3))

        return suggestions
