"""
Knowledge Graph module for entity and relationship extraction.

This module provides domain models, knowledge base management,
and extraction capabilities for building semantic knowledge graphs
from transcripts and other text sources.
"""

from app.kg.domain import (
    ConnectionType,
    Discovery,
    DiscoveryStatus,
    DomainProfile,
    KGProject,
    ProjectState,
    SeedEntity,
    ThingType,
)
from app.kg.knowledge_base import KnowledgeBase
from app.kg.models import Edge, Node, RelationshipDetail, Source, SourceType
from app.kg.resolution import (
    EntityMatcher,
    MergeHistory,
    ResolutionCandidate,
    ResolutionConfig,
)
from app.kg.schemas import (
    ExtractedDiscovery,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)

__all__ = [
    # Knowledge Base
    "KnowledgeBase",
    # Models
    "Node",
    "Edge",
    "Source",
    "SourceType",
    "RelationshipDetail",
    # Domain Profile
    "DomainProfile",
    "ThingType",
    "ConnectionType",
    "SeedEntity",
    # Project
    "KGProject",
    "ProjectState",
    "Discovery",
    "DiscoveryStatus",
    # Resolution
    "ResolutionCandidate",
    "MergeHistory",
    "ResolutionConfig",
    "EntityMatcher",
    # Extraction Schemas
    "ExtractedEntity",
    "ExtractedRelationship",
    "ExtractedDiscovery",
    "ExtractionResult",
]
