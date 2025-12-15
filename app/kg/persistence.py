"""
Knowledge base persistence: save, load, list, export.

Handles serialization of KnowledgeBase objects to disk using a multi-file
directory structure. Each knowledge base gets its own directory with:
- meta.json: Basic metadata (id, name, timestamps, counts)
- nodes.json: All Node objects
- edges.json: All Edge objects
- sources.json: All Source objects
- domain_profile.json: Associated DomainProfile (if present)
- graph.graphml: NetworkX-compatible graph export

Design Decisions:
- Atomic writes using tempfile + os.replace to prevent corruption
- JSON for data files (human-readable, easy debugging)
- GraphML for interoperability (Gephi, Neo4j, yEd, etc.)
- Sorted list_knowledge_bases by updated_at for recency ordering
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import networkx as nx  # type: ignore[import-untyped]

from app.kg.domain import DomainProfile
from app.kg.knowledge_base import KnowledgeBase
from app.kg.models import Edge, Node, Source


def _atomic_write(path: Path, content: str) -> None:
    """
    Atomically write content to a file.

    Uses the write-to-temp-then-rename pattern for thread safety.
    File renames are atomic on POSIX systems, preventing partial writes
    even if the process is interrupted mid-write.

    Args:
        path: Target file path
        content: String content to write

    Raises:
        OSError: If write or rename fails
    """
    # Create temp file in same directory to ensure same filesystem for atomic rename
    fd, temp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        # Atomic rename - guaranteed atomic on POSIX, nearly atomic on Windows
        os.replace(temp_path, path)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def save_knowledge_base(kb: KnowledgeBase, base_path: Path) -> None:
    """
    Save a knowledge base to disk.

    Creates a directory structure under base_path/{kb.id}/ with separate
    JSON files for each data type plus a GraphML export.

    Directory structure created:
        base_path/{kb.id}/
            meta.json           - ID, name, timestamps, counts
            nodes.json          - All Node objects
            edges.json          - All Edge objects
            sources.json        - All Source objects
            domain_profile.json - DomainProfile (if present)
            graph.graphml       - NetworkX graph export

    Args:
        kb: KnowledgeBase to save
        base_path: Parent directory for knowledge base storage
    """
    kb_path = base_path / kb.id
    kb_path.mkdir(parents=True, exist_ok=True)

    # Meta file with summary info
    meta = {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "created_at": kb.created_at.isoformat(),
        "updated_at": kb.updated_at.isoformat(),
        "node_count": len(kb._nodes),
        "edge_count": len(kb._edges),
        "source_count": len(kb._sources),
    }
    _atomic_write(kb_path / "meta.json", json.dumps(meta, indent=2))

    # Nodes - serialize with datetime handling
    nodes_data = [n.model_dump() for n in kb._nodes.values()]
    _atomic_write(kb_path / "nodes.json", json.dumps(nodes_data, indent=2, default=str))

    # Edges - serialize with datetime handling
    edges_data = [e.model_dump() for e in kb._edges.values()]
    _atomic_write(kb_path / "edges.json", json.dumps(edges_data, indent=2, default=str))

    # Sources - serialize with datetime handling
    sources_data = [s.model_dump() for s in kb._sources.values()]
    _atomic_write(
        kb_path / "sources.json", json.dumps(sources_data, indent=2, default=str)
    )

    # Domain profile (if present)
    if kb.domain_profile:
        _atomic_write(
            kb_path / "domain_profile.json",
            kb.domain_profile.model_dump_json(indent=2),
        )

    # GraphML export for visualization tools
    export_graphml(kb, kb_path / "graph.graphml")


def load_knowledge_base(kb_path: Path) -> KnowledgeBase | None:
    """
    Load a knowledge base from disk.

    Reads the multi-file directory structure and reconstructs a
    KnowledgeBase object with all its nodes, edges, and sources.

    Args:
        kb_path: Path to the knowledge base directory

    Returns:
        Reconstructed KnowledgeBase, or None if path doesn't exist
        or is missing required files (meta.json)
    """
    if not kb_path.exists():
        return None

    # Meta is required
    meta_file = kb_path / "meta.json"
    if not meta_file.exists():
        return None

    meta = json.loads(meta_file.read_text())

    # Load domain profile if present
    domain_profile: DomainProfile | None = None
    dp_file = kb_path / "domain_profile.json"
    if dp_file.exists():
        domain_profile = DomainProfile.model_validate_json(dp_file.read_text())

    # Create KnowledgeBase with metadata
    kb = KnowledgeBase(
        id=meta["id"],
        name=meta["name"],
        description=meta.get("description"),
        domain_profile=domain_profile,
    )
    kb.created_at = datetime.fromisoformat(meta["created_at"])
    kb.updated_at = datetime.fromisoformat(meta["updated_at"])

    # Load nodes
    nodes_file = kb_path / "nodes.json"
    if nodes_file.exists():
        nodes_data = json.loads(nodes_file.read_text())
        for nd in nodes_data:
            node = Node.model_validate(nd)
            kb.add_node(node)

    # Load edges
    edges_file = kb_path / "edges.json"
    if edges_file.exists():
        edges_data = json.loads(edges_file.read_text())
        for ed in edges_data:
            edge = Edge.model_validate(ed)
            kb.add_edge(edge)

    # Load sources
    sources_file = kb_path / "sources.json"
    if sources_file.exists():
        sources_data = json.loads(sources_file.read_text())
        for sd in sources_data:
            source = Source.model_validate(sd)
            kb.add_source(source)

    return kb


def list_knowledge_bases(base_path: Path) -> list[dict[str, Any]]:
    """
    List all knowledge bases in a directory.

    Scans subdirectories for valid knowledge bases (those with meta.json)
    and returns their metadata sorted by most recently updated first.

    Args:
        base_path: Parent directory containing knowledge base directories

    Returns:
        List of metadata dicts, sorted by updated_at descending.
        Each dict contains: id, name, description, created_at, updated_at,
        node_count, edge_count, source_count.
    """
    results: list[dict[str, Any]] = []

    if not base_path.exists():
        return results

    for kb_dir in base_path.iterdir():
        if not kb_dir.is_dir():
            continue

        meta_file = kb_dir / "meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
                results.append(meta)
            except (json.JSONDecodeError, OSError):
                # Skip corrupted or unreadable files
                continue

    # Sort by updated_at descending (most recent first)
    return sorted(results, key=lambda x: x.get("updated_at", ""), reverse=True)


def export_graphml(kb: KnowledgeBase, output_path: Path) -> None:
    """
    Export a knowledge base to GraphML format.

    Creates a NetworkX-compatible GraphML file suitable for import into
    graph visualization tools like Gephi, yEd, or Cytoscape.

    Node attributes exported:
        - label: Primary entity name
        - entity_type: Category (Person, Organization, etc.)
        - aliases: Comma-separated list of alternative names
        - description: Entity description

    Edge attributes exported:
        - relationship_types: Comma-separated list of relationship types
        - count: Number of relationships on this edge

    Args:
        kb: KnowledgeBase to export
        output_path: File path for the GraphML output
    """
    # Build a clean graph specifically for export
    # (separate from kb._graph to control attribute serialization)
    G: nx.DiGraph = nx.DiGraph()

    # Add nodes with GraphML-compatible attributes
    for node in kb._nodes.values():
        G.add_node(
            node.id,
            label=node.label,
            entity_type=node.entity_type,
            # GraphML doesn't support lists - join as comma-separated string
            aliases=",".join(node.aliases) if node.aliases else "",
            description=node.description or "",
        )

    # Add edges with relationship info
    for edge in kb._edges.values():
        rel_types = edge.get_relationship_types()
        G.add_edge(
            edge.source_node_id,
            edge.target_node_id,
            # Comma-separated relationship types for GraphML compatibility
            relationship_types=",".join(rel_types) if rel_types else "",
            count=len(edge.relationships),
        )

    # Write GraphML file
    nx.write_graphml(G, str(output_path))
