"""
Tests for Knowledge Graph extraction schemas.

These tests cover the Pydantic models used for Claude's structured extraction output:
- ExtractedEntity: Entity data before ID assignment
- ExtractedRelationship: Relationship with confidence validation
- ExtractedDiscovery: New type discovery for schema evolution
- ExtractionResult: Aggregated extraction output
"""

import pytest

from app.kg.schemas import (
    ExtractedEntity,
    ExtractedRelationship,
    ExtractedDiscovery,
    ExtractionResult,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ExtractedEntity Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_extracted_entity_minimal() -> None:
    """ExtractedEntity should create with only required fields."""
    entity = ExtractedEntity(
        label="Sidney Gottlieb",
        entity_type="Person",
    )

    assert entity.label == "Sidney Gottlieb"
    assert entity.entity_type == "Person"
    assert entity.aliases == []
    assert entity.description is None
    assert entity.properties == {}


def test_extracted_entity_full() -> None:
    """ExtractedEntity should accept all optional fields."""
    entity = ExtractedEntity(
        label="CIA",
        entity_type="Organization",
        aliases=["Central Intelligence Agency", "The Agency", "Langley"],
        description="U.S. foreign intelligence service",
        properties={"founded": "1947", "headquarters": "Langley, Virginia"},
    )

    assert entity.label == "CIA"
    assert entity.entity_type == "Organization"
    assert len(entity.aliases) == 3
    assert "The Agency" in entity.aliases
    assert entity.description == "U.S. foreign intelligence service"
    assert entity.properties["founded"] == "1947"


def test_extracted_entity_serialization() -> None:
    """ExtractedEntity should serialize to dict correctly."""
    entity = ExtractedEntity(
        label="MKUltra",
        entity_type="Project",
        aliases=["Project MKUltra"],
        description="CIA mind control program",
    )

    data = entity.model_dump()
    assert data["label"] == "MKUltra"
    assert data["entity_type"] == "Project"
    assert data["aliases"] == ["Project MKUltra"]
    assert data["properties"] == {}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ExtractedRelationship Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_extracted_relationship_minimal() -> None:
    """ExtractedRelationship should create with required fields and defaults."""
    rel = ExtractedRelationship(
        source_label="Sidney Gottlieb",
        target_label="CIA",
        relationship_type="worked_for",
    )

    assert rel.source_label == "Sidney Gottlieb"
    assert rel.target_label == "CIA"
    assert rel.relationship_type == "worked_for"
    assert rel.confidence == 1.0  # Default
    assert rel.evidence is None
    assert rel.properties == {}


def test_extracted_relationship_full() -> None:
    """ExtractedRelationship should accept all optional fields."""
    rel = ExtractedRelationship(
        source_label="CIA",
        target_label="MKUltra",
        relationship_type="funded",
        confidence=0.95,
        evidence="The CIA funded MKUltra from 1953 to 1973",
        properties={"start_year": "1953", "end_year": "1973"},
    )

    assert rel.source_label == "CIA"
    assert rel.target_label == "MKUltra"
    assert rel.relationship_type == "funded"
    assert rel.confidence == 0.95
    assert rel.evidence is not None
    assert "funded MKUltra" in rel.evidence
    assert rel.properties["start_year"] == "1953"


def test_extracted_relationship_confidence_bounds() -> None:
    """ExtractedRelationship confidence must be between 0.0 and 1.0."""
    # Valid boundary values
    rel_zero = ExtractedRelationship(
        source_label="A",
        target_label="B",
        relationship_type="test",
        confidence=0.0,
    )
    assert rel_zero.confidence == 0.0

    rel_one = ExtractedRelationship(
        source_label="A",
        target_label="B",
        relationship_type="test",
        confidence=1.0,
    )
    assert rel_one.confidence == 1.0

    # Invalid: too high
    with pytest.raises(ValueError, match="less than or equal to 1"):
        ExtractedRelationship(
            source_label="A",
            target_label="B",
            relationship_type="test",
            confidence=1.5,
        )

    # Invalid: negative
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        ExtractedRelationship(
            source_label="A",
            target_label="B",
            relationship_type="test",
            confidence=-0.1,
        )


def test_extracted_relationship_serialization() -> None:
    """ExtractedRelationship should serialize to dict correctly."""
    rel = ExtractedRelationship(
        source_label="Person A",
        target_label="Organization B",
        relationship_type="member_of",
        confidence=0.8,
    )

    data = rel.model_dump()
    assert data["source_label"] == "Person A"
    assert data["target_label"] == "Organization B"
    assert data["relationship_type"] == "member_of"
    assert data["confidence"] == 0.8


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ExtractedDiscovery Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_extracted_discovery_thing_type() -> None:
    """ExtractedDiscovery should capture new entity type discoveries."""
    discovery = ExtractedDiscovery(
        discovery_type="thing_type",
        name="Subproject",
        display_name="Research Subproject",
        description="Individual research project under a larger program",
        examples=["Subproject 68", "Subproject 119"],
    )

    assert discovery.discovery_type == "thing_type"
    assert discovery.name == "Subproject"
    assert discovery.display_name == "Research Subproject"
    assert "research project" in discovery.description.lower()
    assert len(discovery.examples) == 2
    assert "Subproject 68" in discovery.examples


def test_extracted_discovery_connection_type() -> None:
    """ExtractedDiscovery should capture new relationship type discoveries."""
    discovery = ExtractedDiscovery(
        discovery_type="connection_type",
        name="supervised_by",
        display_name="supervised by",
        description="Person who oversaw another's work or research",
    )

    assert discovery.discovery_type == "connection_type"
    assert discovery.name == "supervised_by"
    assert discovery.display_name == "supervised by"
    assert discovery.examples == []  # Optional, defaults empty


def test_extracted_discovery_serialization() -> None:
    """ExtractedDiscovery should serialize with all fields."""
    discovery = ExtractedDiscovery(
        discovery_type="thing_type",
        name="Document",
        display_name="Official Document",
        description="Declassified or official government document",
        examples=["MKULTRA memo", "Senate hearing transcript"],
    )

    data = discovery.model_dump()
    assert data["discovery_type"] == "thing_type"
    assert data["name"] == "Document"
    assert len(data["examples"]) == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ExtractionResult Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_extraction_result_empty() -> None:
    """ExtractionResult should create with empty defaults."""
    result = ExtractionResult()

    assert result.entities == []
    assert result.relationships == []
    assert result.discoveries == []
    assert result.summary is None


def test_extraction_result_with_entities() -> None:
    """ExtractionResult should hold multiple entities."""
    entities = [
        ExtractedEntity(label="Person A", entity_type="Person"),
        ExtractedEntity(label="Organization B", entity_type="Organization"),
    ]

    result = ExtractionResult(entities=entities)

    assert len(result.entities) == 2
    assert result.entities[0].label == "Person A"
    assert result.entities[1].entity_type == "Organization"


def test_extraction_result_with_relationships() -> None:
    """ExtractionResult should hold relationships between entities."""
    relationships = [
        ExtractedRelationship(
            source_label="Person A",
            target_label="Organization B",
            relationship_type="member_of",
            confidence=0.9,
        ),
        ExtractedRelationship(
            source_label="Organization B",
            target_label="Project C",
            relationship_type="funded",
            confidence=0.85,
        ),
    ]

    result = ExtractionResult(relationships=relationships)

    assert len(result.relationships) == 2
    assert result.relationships[0].relationship_type == "member_of"
    assert result.relationships[1].confidence == 0.85


def test_extraction_result_full() -> None:
    """ExtractionResult should aggregate all extraction components."""
    result = ExtractionResult(
        entities=[
            ExtractedEntity(label="Sidney Gottlieb", entity_type="Person"),
            ExtractedEntity(label="CIA", entity_type="Organization"),
            ExtractedEntity(label="MKUltra", entity_type="Project"),
        ],
        relationships=[
            ExtractedRelationship(
                source_label="Sidney Gottlieb",
                target_label="CIA",
                relationship_type="worked_for",
            ),
            ExtractedRelationship(
                source_label="CIA",
                target_label="MKUltra",
                relationship_type="funded",
            ),
        ],
        discoveries=[
            ExtractedDiscovery(
                discovery_type="thing_type",
                name="Subproject",
                display_name="Research Subproject",
                description="Individual research project",
            ),
        ],
        summary="Extracted key figures and relationships from MKUltra documentary",
    )

    # Verify all components
    assert len(result.entities) == 3
    assert len(result.relationships) == 2
    assert len(result.discoveries) == 1
    assert result.summary is not None
    assert "MKUltra" in result.summary

    # Verify entity types
    entity_types = {e.entity_type for e in result.entities}
    assert entity_types == {"Person", "Organization", "Project"}

    # Verify relationship types
    rel_types = {r.relationship_type for r in result.relationships}
    assert rel_types == {"worked_for", "funded"}


def test_extraction_result_serialization() -> None:
    """ExtractionResult should serialize to JSON-compatible dict."""
    result = ExtractionResult(
        entities=[ExtractedEntity(label="Test", entity_type="Person")],
        relationships=[
            ExtractedRelationship(
                source_label="A",
                target_label="B",
                relationship_type="knows",
            )
        ],
        summary="Test extraction",
    )

    data = result.model_dump()

    assert "entities" in data
    assert "relationships" in data
    assert "discoveries" in data
    assert "summary" in data
    assert len(data["entities"]) == 1
    assert len(data["relationships"]) == 1
    assert data["entities"][0]["label"] == "Test"
