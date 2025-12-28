"""
Knowledge Graph domain models for bootstrap and project lifecycle.

This module defines domain models for the KG bootstrap system:
- ThingType: Entity types to extract (e.g., Person, Organization)
- ConnectionType: Relationship types to track (e.g., worked_for, funded_by)
- SeedEntity: Key entities for naming consistency across extractions
- DomainProfile: Auto-inferred domain configuration from first video
- Discovery: New findings awaiting user confirmation
- KGProject: User-facing research project wrapper

Note: Graph storage models (Node, Edge, Source) are in models.py.
      Extraction output schemas (ExtractedEntity, etc.) are in schemas.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

# Forward reference for resolution types (imported at end to avoid circular import)
# These are imported at module level after class definitions


def _generate_id() -> str:
    """Generate a 12-character hex ID from UUID4."""
    return uuid4().hex[:12]


def _utc_now() -> datetime:
    """Get current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Domain Profile Models (Bootstrap Phase)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ThingType(BaseModel):
    """
    A type of entity to extract from content.

    ThingTypes are inferred during bootstrap and define the categories
    of entities the system should look for (e.g., Person, Organization).

    Attributes:
        name: Type name in PascalCase (e.g., "Person", "Organization")
        description: What this type represents in the domain
        examples: 2-3 examples found in the source content
        priority: 1=high, 2=medium, 3=low extraction priority
        icon: Emoji for UI display
        plural: Plural form (auto-generated if None)
    """

    name: str
    description: str
    examples: list[str] = Field(default_factory=list)
    priority: int = 2
    icon: str = "📦"
    plural: str | None = None


class ConnectionType(BaseModel):
    """
    A type of relationship to extract between entities.

    ConnectionTypes define meaningful relationships the extraction
    process should look for (e.g., worked_for, funded_by).

    Attributes:
        name: Internal name in snake_case (e.g., "worked_for")
        display_name: Human-readable form (e.g., "worked for")
        description: What this relationship means
        examples: Example pairs as (source, target) tuples
        directional: Is A→B different from B→A?
    """

    name: str
    display_name: str
    description: str
    examples: list[tuple[str, str]] = Field(default_factory=list)
    directional: bool = True


class SeedEntity(BaseModel):
    """
    An entity identified during bootstrap to seed consistency.

    Seed entities are key entities from the first video that establish
    canonical naming across future extractions.

    Attributes:
        label: Primary name (e.g., "CIA")
        thing_type: Which ThingType this belongs to
        aliases: Alternative names (e.g., ["Central Intelligence Agency"])
        description: Brief description for disambiguation
        confidence: Confidence score (1.0 for bootstrap seeds)
    """

    label: str
    thing_type: str
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    confidence: float = 1.0


class DomainProfile(BaseModel):
    """
    Auto-inferred domain configuration from bootstrap analysis.

    Created by analyzing the first video transcript. Captures what
    entity types, relationships, and seed entities to extract.

    Attributes:
        id: Unique 12-character identifier
        name: Human-readable domain name (e.g., "CIA Mind Control Research")
        description: 2-3 sentence domain description
        thing_types: Entity types to extract
        connection_types: Relationship types to track
        seed_entities: Key entities for naming consistency
        extraction_context: Prompt context for future extractions
        bootstrap_confidence: How confident was the inference (0.0-1.0)
        bootstrapped_from: Source ID of the first video
        refinement_count: Number of user confirmations applied
        refined_from: Source IDs that triggered refinements
        created_at: Creation timestamp
        updated_at: Last modification timestamp
    """

    id: str = Field(default_factory=_generate_id)
    name: str
    description: str
    thing_types: list[ThingType] = Field(default_factory=list)
    connection_types: list[ConnectionType] = Field(default_factory=list)
    seed_entities: list[SeedEntity] = Field(default_factory=list)
    extraction_context: str = ""
    bootstrap_confidence: float = 0.0
    bootstrapped_from: str = ""
    refinement_count: int = 0
    refined_from: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    def get_thing_type_names(self) -> list[str]:
        """Get list of thing type names for extraction prompts."""
        return [t.name for t in self.thing_types]

    def get_connection_type_names(self) -> list[str]:
        """Get list of connection type names for extraction prompts."""
        return [c.name for c in self.connection_types]

    def add_thing_type(self, thing_type: ThingType) -> None:
        """Add a new thing type (from user confirmation)."""
        self.thing_types.append(thing_type)
        self.refinement_count += 1
        self.updated_at = _utc_now()

    def add_connection_type(self, connection_type: ConnectionType) -> None:
        """Add a new connection type (from user confirmation)."""
        self.connection_types.append(connection_type)
        self.refinement_count += 1
        self.updated_at = _utc_now()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Project Lifecycle Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class DiscoveryStatus(str, Enum):
    """Status of a discovery awaiting user confirmation."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class Discovery(BaseModel):
    """
    Something new found that doesn't fit the current domain profile.

    Discoveries are surfaced to users as simple Yes/No questions
    to refine the domain profile over time.

    Attributes:
        id: Unique 8-character identifier
        discovery_type: "thing_type" or "connection_type"
        name: Internal name
        display_name: Human-readable name
        description: Why this seems important
        examples: Evidence from the source
        found_in_source: Source ID where discovered
        occurrence_count: How many times seen
        status: pending/confirmed/rejected
        user_question: Simple question for user (e.g., "Track Subprojects?")
        created_at: When discovered
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    discovery_type: str
    name: str
    display_name: str
    description: str
    examples: list[str] = Field(default_factory=list)
    found_in_source: str = ""
    occurrence_count: int = 0
    status: DiscoveryStatus = DiscoveryStatus.PENDING
    user_question: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class ProjectState(str, Enum):
    """State of a KG project lifecycle."""

    CREATED = "created"  # Just created, no videos processed
    BOOTSTRAPPING = "bootstrapping"  # Processing first video
    ACTIVE = "active"  # Domain inferred, accepting videos
    STABLE = "stable"  # 5+ videos, domain stable


class KGProject(BaseModel):
    """
    User's research project — wraps the technical knowledge base.

    This is the user-facing entity. The underlying KnowledgeBase
    and DomainProfile are implementation details.

    Attributes:
        id: Unique 12-character identifier
        name: User-provided project name
        state: Current lifecycle state
        domain_profile: Auto-inferred domain configuration
        pending_discoveries: Discoveries awaiting user confirmation
        pending_merges: Resolution candidates awaiting user confirmation
        merge_history: Audit trail of completed merges
        resolution_config: Configuration for entity resolution algorithm
        source_count: Number of videos processed
        thing_count: Number of entities extracted
        connection_count: Number of relationships extracted
        kb_id: Internal KnowledgeBase reference
        error: Last error message (if any)
        created_at: Creation timestamp
        updated_at: Last modification timestamp
    """

    id: str = Field(default_factory=_generate_id)
    name: str
    state: ProjectState = ProjectState.CREATED
    domain_profile: DomainProfile | None = None
    pending_discoveries: list[Discovery] = Field(default_factory=list)
    pending_merges: list["ResolutionCandidate"] = Field(default_factory=list)
    merge_history: list["MergeHistory"] = Field(default_factory=list)
    resolution_config: "ResolutionConfig" = Field(
        default_factory=lambda: _get_default_resolution_config()
    )
    source_count: int = 0
    thing_count: int = 0
    connection_count: int = 0
    kb_id: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


def _get_default_resolution_config() -> "ResolutionConfig":
    """Get default ResolutionConfig. Avoids circular import at class definition time."""
    from app.kg.resolution import ResolutionConfig

    return ResolutionConfig()


# Import resolution types for runtime validation
# These are imported after class definitions to avoid circular imports
from app.kg.resolution import MergeHistory, ResolutionCandidate, ResolutionConfig  # noqa: E402

# Update forward references for Pydantic
KGProject.model_rebuild()
