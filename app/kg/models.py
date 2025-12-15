"""
Knowledge graph data models: Node, Edge, Source, RelationshipDetail.

These store the ACTUAL graph data (not just schema/profile).

This module is separate from domain.py which contains:
- Domain inference models (ThingType, ConnectionType, DomainProfile)
- Project management models (KGProject, Discovery)
- Extraction schemas (ExtractedEntity, ExtractedRelationship)

These models are used by KnowledgeBase to store extracted entities
and their relationships.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _generate_id() -> str:
    """Generate a 12-character hex ID from UUID4."""
    return uuid4().hex[:12]


def _utc_now() -> datetime:
    """Get current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


class SourceType(str, Enum):
    """Type of content source for knowledge extraction."""

    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    WEBPAGE = "webpage"
    OTHER = "other"


class Source(BaseModel):
    """
    A content source that entities were extracted from.

    Tracks provenance for extracted entities and relationships,
    enabling traceability back to original source material.

    Attributes:
        id: Unique 12-character identifier
        title: Human-readable title of the source
        source_type: Category of source (video, audio, document, etc.)
        url: Optional URL or file path to the source
        metadata: Flexible key-value storage for source-specific data
        processed_at: When this source was processed for extraction
    """

    id: str = Field(default_factory=_generate_id)
    title: str
    source_type: SourceType = SourceType.VIDEO
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    processed_at: datetime = Field(default_factory=_utc_now)


class RelationshipDetail(BaseModel):
    """
    A single relationship instance between two nodes.

    Multiple RelationshipDetails can exist on one Edge
    (e.g., same two people connected via "worked_with" AND "friends_with").

    Attributes:
        relationship_type: Type of relationship (e.g., "worked_for", "directed")
        source_id: ID of the Source this relationship was extracted from
        confidence: Confidence score 0.0-1.0 (default 1.0)
        evidence: Supporting quote or context from the source
        properties: Additional metadata for this relationship instance
        extracted_at: When this relationship was extracted
    """

    relationship_type: str
    source_id: str
    confidence: float = 1.0
    evidence: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    extracted_at: datetime = Field(default_factory=_utc_now)


class Node(BaseModel):
    """
    An entity in the knowledge graph.

    Represents any identifiable concept: Person, Organization,
    Event, Symbol, Theme, etc.

    Attributes:
        id: Unique 12-character identifier
        label: Primary display name (e.g., "Sidney Gottlieb")
        entity_type: Category (e.g., "Person", "Organization")
        aliases: Alternative names (e.g., ["Dr. Gottlieb", "Joseph Scheider"])
        description: Brief description of the entity
        properties: Flexible storage for entity-specific attributes
        source_ids: IDs of sources where this entity was mentioned
        created_at: When this node was first created
        updated_at: When this node was last modified
    """

    id: str = Field(default_factory=_generate_id)
    label: str
    entity_type: str
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    source_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    def add_source(self, source_id: str) -> None:
        """
        Track that this node was mentioned in a source.

        Adds the source_id to source_ids if not already present
        and updates the updated_at timestamp.

        Args:
            source_id: ID of the Source where this entity was found
        """
        if source_id not in self.source_ids:
            self.source_ids.append(source_id)
            self.updated_at = _utc_now()

    def add_alias(self, alias: str) -> None:
        """
        Add an alternative name for this entity.

        Adds the alias if not already present and not equal to the label.
        Updates the updated_at timestamp.

        Args:
            alias: Alternative name to add
        """
        if alias not in self.aliases and alias != self.label:
            self.aliases.append(alias)
            self.updated_at = _utc_now()


class Edge(BaseModel):
    """
    A connection between two nodes.

    Can contain multiple relationships (e.g., A "worked_for" B AND "reported_to" B).
    This design uses a single Edge per node pair rather than separate edges
    per relationship type.

    Attributes:
        id: Unique 12-character identifier
        source_node_id: ID of the source node (relationship origin)
        target_node_id: ID of the target node (relationship destination)
        relationships: List of RelationshipDetail objects on this edge
        created_at: When this edge was first created
        updated_at: When this edge was last modified
    """

    id: str = Field(default_factory=_generate_id)
    source_node_id: str
    target_node_id: str
    relationships: list[RelationshipDetail] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    def add_relationship(self, detail: RelationshipDetail) -> None:
        """
        Add a relationship to this edge.

        Appends the RelationshipDetail and updates the updated_at timestamp.

        Args:
            detail: The RelationshipDetail to add
        """
        self.relationships.append(detail)
        self.updated_at = _utc_now()

    def has_relationship(self, relationship_type: str) -> bool:
        """
        Check if this edge has a specific relationship type.

        Args:
            relationship_type: The relationship type to check for

        Returns:
            True if a relationship with this type exists on the edge
        """
        return any(r.relationship_type == relationship_type for r in self.relationships)

    def get_relationship_types(self) -> list[str]:
        """
        Get all unique relationship types on this edge.

        Returns:
            List of unique relationship type strings
        """
        return list({r.relationship_type for r in self.relationships})
