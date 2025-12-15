"""
Extraction schemas — what Claude returns from extraction.

These Pydantic models define the structure of extraction results returned
by the Claude agent. They serve as an intermediate representation between
the LLM's structured output and the final Node/Edge storage models.

Key distinction from models.py:
- schemas.py: Extraction output (label-based references, no IDs)
- models.py: Storage models (ID-based, with timestamps and source tracking)
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    """
    An entity extracted from content.

    Represents a single entity (person, organization, concept, etc.)
    identified by the extraction agent. Uses labels for identification
    since IDs are assigned during storage.

    Attributes:
        label: Primary name for the entity (e.g., "Sidney Gottlieb")
        entity_type: Type from DomainProfile (e.g., "Person", "Organization")
        aliases: Alternative names (e.g., ["Dr. Gottlieb", "Joseph Scheider"])
        description: Brief description of the entity
        properties: Additional key-value metadata
    """

    label: str
    entity_type: str
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    properties: dict[str, str] = Field(default_factory=dict)


class ExtractedRelationship(BaseModel):
    """
    A relationship extracted from content.

    Represents a connection between two entities, identified by their
    labels. The extraction agent provides confidence scores and evidence
    to support the relationship.

    Attributes:
        source_label: Label of the source entity
        target_label: Label of the target entity
        relationship_type: Type from DomainProfile (e.g., "worked_for", "directed")
        confidence: Confidence score from 0.0 to 1.0
        evidence: Supporting quote or context from the source
        properties: Additional key-value metadata
    """

    source_label: str
    target_label: str
    relationship_type: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: str | None = None
    properties: dict[str, str] = Field(default_factory=dict)


class ExtractedDiscovery(BaseModel):
    """
    A new type discovered during extraction.

    When the extraction agent encounters entities or relationships that
    don't fit the existing DomainProfile, it reports them as discoveries
    for human review. This enables incremental schema evolution.

    Attributes:
        discovery_type: Either "thing_type" or "connection_type"
        name: Internal identifier (e.g., "research_program")
        display_name: Human-readable name (e.g., "Research Program")
        description: Why this type seems important
        examples: Concrete examples found in the content
    """

    discovery_type: str  # "thing_type" or "connection_type"
    name: str
    display_name: str
    description: str
    examples: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """
    Complete extraction result from a transcript.

    Aggregates all entities, relationships, and discoveries extracted
    from a single content source. This is the primary output of the
    extraction agent.

    Attributes:
        entities: List of extracted entities
        relationships: List of extracted relationships
        discoveries: List of new types to consider adding to the profile
        summary: Brief summary of key information extracted
    """

    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
    discoveries: list[ExtractedDiscovery] = Field(default_factory=list)
    summary: str | None = None
