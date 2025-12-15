"""
Tests for Knowledge Graph domain models.

This module tests the Pydantic models used for the KG bootstrap system:
- ThingType: Entity types to extract
- ConnectionType: Relationship types to track
- SeedEntity: Key entities for naming consistency
- DomainProfile: Auto-inferred domain configuration
- Discovery: New findings awaiting user confirmation
- KGProject: User-facing research project wrapper
"""

from __future__ import annotations


class TestThingType:
    """Test ThingType model."""

    def test_thing_type_creation_with_defaults(self):
        """Test creating a ThingType with minimal required fields."""
        from app.kg.domain import ThingType

        thing_type = ThingType(
            name="Person",
            description="A human individual mentioned in the content",
        )

        assert thing_type.name == "Person"
        assert thing_type.description == "A human individual mentioned in the content"
        # Check defaults
        assert thing_type.examples == []
        assert thing_type.priority == 2
        assert thing_type.icon == "📦"
        assert thing_type.plural is None

    def test_thing_type_with_all_fields(self):
        """Test creating a ThingType with all fields specified."""
        from app.kg.domain import ThingType

        thing_type = ThingType(
            name="Organization",
            description="A company, agency, or institution",
            examples=["CIA", "FBI", "NSA"],
            priority=1,
            icon="🏢",
            plural="Organizations",
        )

        assert thing_type.name == "Organization"
        assert thing_type.description == "A company, agency, or institution"
        assert thing_type.examples == ["CIA", "FBI", "NSA"]
        assert thing_type.priority == 1
        assert thing_type.icon == "🏢"
        assert thing_type.plural == "Organizations"


class TestConnectionType:
    """Test ConnectionType model."""

    def test_connection_type_creation(self):
        """Test creating a ConnectionType with required fields."""
        from app.kg.domain import ConnectionType

        connection_type = ConnectionType(
            name="worked_for",
            display_name="worked for",
            description="Employment relationship between person and organization",
        )

        assert connection_type.name == "worked_for"
        assert connection_type.display_name == "worked for"
        assert (
            connection_type.description
            == "Employment relationship between person and organization"
        )
        assert connection_type.examples == []

    def test_connection_type_directional_default(self):
        """Test that ConnectionType.directional defaults to True."""
        from app.kg.domain import ConnectionType

        connection_type = ConnectionType(
            name="funded_by",
            display_name="funded by",
            description="Financial support relationship",
        )

        # Directional should default to True (A→B is different from B→A)
        assert connection_type.directional is True

    def test_connection_type_with_examples(self):
        """Test ConnectionType with example pairs."""
        from app.kg.domain import ConnectionType

        connection_type = ConnectionType(
            name="collaborated_with",
            display_name="collaborated with",
            description="Cooperative relationship between entities",
            examples=[("Person A", "Person B"), ("Org X", "Org Y")],
            directional=False,
        )

        assert len(connection_type.examples) == 2
        assert connection_type.examples[0] == ("Person A", "Person B")
        assert connection_type.directional is False


class TestSeedEntity:
    """Test SeedEntity model."""

    def test_seed_entity_creation(self):
        """Test creating a SeedEntity with required fields."""
        from app.kg.domain import SeedEntity

        seed_entity = SeedEntity(
            label="CIA",
            thing_type="Organization",
        )

        assert seed_entity.label == "CIA"
        assert seed_entity.thing_type == "Organization"
        # Check defaults
        assert seed_entity.aliases == []
        assert seed_entity.description is None
        assert seed_entity.confidence == 1.0

    def test_seed_entity_with_aliases(self):
        """Test creating a SeedEntity with aliases for disambiguation."""
        from app.kg.domain import SeedEntity

        seed_entity = SeedEntity(
            label="CIA",
            thing_type="Organization",
            aliases=["Central Intelligence Agency", "The Agency", "Langley"],
            description="United States intelligence agency",
            confidence=0.95,
        )

        assert seed_entity.label == "CIA"
        assert len(seed_entity.aliases) == 3
        assert "Central Intelligence Agency" in seed_entity.aliases
        assert seed_entity.description == "United States intelligence agency"
        assert seed_entity.confidence == 0.95


class TestDomainProfile:
    """Test DomainProfile model."""

    def test_domain_profile_creation_with_defaults(self):
        """Test creating a DomainProfile with minimal fields."""
        from app.kg.domain import DomainProfile

        profile = DomainProfile(
            name="CIA Mind Control Research",
            description="Knowledge graph about MKUltra and related programs",
        )

        assert profile.name == "CIA Mind Control Research"
        assert (
            profile.description == "Knowledge graph about MKUltra and related programs"
        )
        # Check defaults
        assert profile.thing_types == []
        assert profile.connection_types == []
        assert profile.seed_entities == []
        assert profile.extraction_context == ""
        assert profile.bootstrap_confidence == 0.0
        assert profile.bootstrapped_from == ""
        assert profile.refinement_count == 0
        assert profile.refined_from == []

    def test_domain_profile_id_generation(self):
        """Test that DomainProfile auto-generates a 12-character ID."""
        from app.kg.domain import DomainProfile

        profile1 = DomainProfile(name="Profile 1", description="First profile")
        profile2 = DomainProfile(name="Profile 2", description="Second profile")

        # IDs should be 12 characters (hex from uuid4)
        assert len(profile1.id) == 12
        assert len(profile2.id) == 12
        # IDs should be unique
        assert profile1.id != profile2.id
        # IDs should be hexadecimal
        assert all(c in "0123456789abcdef" for c in profile1.id)

    def test_domain_profile_add_thing_type(self):
        """Test adding a ThingType to a DomainProfile."""
        from app.kg.domain import DomainProfile, ThingType

        profile = DomainProfile(name="Test Domain", description="Test description")
        original_count = profile.refinement_count
        original_updated_at = profile.updated_at

        thing_type = ThingType(
            name="Document",
            description="Official documents and reports",
        )

        profile.add_thing_type(thing_type)

        assert len(profile.thing_types) == 1
        assert profile.thing_types[0].name == "Document"
        assert profile.refinement_count == original_count + 1
        assert profile.updated_at >= original_updated_at

    def test_domain_profile_add_connection_type(self):
        """Test adding a ConnectionType to a DomainProfile."""
        from app.kg.domain import ConnectionType, DomainProfile

        profile = DomainProfile(name="Test Domain", description="Test description")
        original_count = profile.refinement_count

        connection_type = ConnectionType(
            name="references",
            display_name="references",
            description="One document referencing another",
        )

        profile.add_connection_type(connection_type)

        assert len(profile.connection_types) == 1
        assert profile.connection_types[0].name == "references"
        assert profile.refinement_count == original_count + 1

    def test_domain_profile_get_thing_type_names(self):
        """Test getting list of thing type names."""
        from app.kg.domain import DomainProfile, ThingType

        profile = DomainProfile(
            name="Test Domain",
            description="Test description",
            thing_types=[
                ThingType(name="Person", description="Individual"),
                ThingType(name="Organization", description="Institution"),
                ThingType(name="Project", description="Research program"),
            ],
        )

        names = profile.get_thing_type_names()

        assert names == ["Person", "Organization", "Project"]

    def test_domain_profile_get_connection_type_names(self):
        """Test getting list of connection type names."""
        from app.kg.domain import ConnectionType, DomainProfile

        profile = DomainProfile(
            name="Test Domain",
            description="Test description",
            connection_types=[
                ConnectionType(
                    name="worked_for",
                    display_name="worked for",
                    description="Employment",
                ),
                ConnectionType(
                    name="funded_by", display_name="funded by", description="Funding"
                ),
            ],
        )

        names = profile.get_connection_type_names()

        assert names == ["worked_for", "funded_by"]

    def test_domain_profile_refinement_count_increment(self):
        """Test that refinement_count increments correctly with multiple additions."""
        from app.kg.domain import ConnectionType, DomainProfile, ThingType

        profile = DomainProfile(name="Test Domain", description="Test description")

        assert profile.refinement_count == 0

        profile.add_thing_type(ThingType(name="Type1", description="First"))
        assert profile.refinement_count == 1

        profile.add_thing_type(ThingType(name="Type2", description="Second"))
        assert profile.refinement_count == 2

        profile.add_connection_type(
            ConnectionType(
                name="conn1", display_name="conn 1", description="First connection"
            )
        )
        assert profile.refinement_count == 3


class TestDiscovery:
    """Test Discovery model."""

    def test_discovery_creation(self):
        """Test creating a Discovery with required fields."""
        from app.kg.domain import Discovery

        discovery = Discovery(
            discovery_type="thing_type",
            name="Subproject",
            display_name="Subproject",
            description="A subdivision of a larger research program",
        )

        assert discovery.discovery_type == "thing_type"
        assert discovery.name == "Subproject"
        assert discovery.display_name == "Subproject"
        assert discovery.description == "A subdivision of a larger research program"
        # Check defaults
        assert discovery.examples == []
        assert discovery.found_in_source == ""
        assert discovery.occurrence_count == 0
        assert discovery.user_question == ""

    def test_discovery_default_status_pending(self):
        """Test that Discovery.status defaults to PENDING."""
        from app.kg.domain import Discovery, DiscoveryStatus

        discovery = Discovery(
            discovery_type="connection_type",
            name="supervised",
            display_name="supervised",
            description="Management relationship",
        )

        assert discovery.status == DiscoveryStatus.PENDING
        assert discovery.status.value == "pending"

    def test_discovery_id_generation(self):
        """Test that Discovery auto-generates an 8-character ID."""
        from app.kg.domain import Discovery

        discovery1 = Discovery(
            discovery_type="thing_type",
            name="Type1",
            display_name="Type 1",
            description="First discovery",
        )
        discovery2 = Discovery(
            discovery_type="thing_type",
            name="Type2",
            display_name="Type 2",
            description="Second discovery",
        )

        # IDs should be 8 characters (shorter than other domain objects)
        assert len(discovery1.id) == 8
        assert len(discovery2.id) == 8
        # IDs should be unique
        assert discovery1.id != discovery2.id

    def test_discovery_with_examples_and_source(self):
        """Test Discovery with examples and source tracking."""
        from app.kg.domain import Discovery, DiscoveryStatus

        discovery = Discovery(
            discovery_type="thing_type",
            name="Contractor",
            display_name="Contractor",
            description="External company working on projects",
            examples=["Lockheed Martin", "RAND Corporation"],
            found_in_source="abc123def456",
            occurrence_count=5,
            status=DiscoveryStatus.CONFIRMED,
            user_question="Track Contractors as a separate entity type?",
        )

        assert len(discovery.examples) == 2
        assert discovery.found_in_source == "abc123def456"
        assert discovery.occurrence_count == 5
        assert discovery.status == DiscoveryStatus.CONFIRMED
        assert "Contractors" in discovery.user_question


class TestKGProject:
    """Test KGProject model."""

    def test_kg_project_creation(self):
        """Test creating a KGProject with required fields."""
        from app.kg.domain import KGProject

        project = KGProject(name="MKUltra Research")

        assert project.name == "MKUltra Research"
        # Check that ID is generated
        assert len(project.id) == 12
        # Check optional fields default to None
        assert project.domain_profile is None
        assert project.kb_id is None
        assert project.error is None

    def test_kg_project_default_state_created(self):
        """Test that KGProject.state defaults to CREATED."""
        from app.kg.domain import KGProject, ProjectState

        project = KGProject(name="New Project")

        assert project.state == ProjectState.CREATED
        assert project.state.value == "created"

    def test_kg_project_stats_defaults(self):
        """Test that KGProject statistics default to zero."""
        from app.kg.domain import KGProject

        project = KGProject(name="Empty Project")

        assert project.source_count == 0
        assert project.thing_count == 0
        assert project.connection_count == 0
        assert project.pending_discoveries == []

    def test_kg_project_with_domain_profile(self):
        """Test creating a KGProject with an attached DomainProfile."""
        from app.kg.domain import DomainProfile, KGProject, ProjectState

        profile = DomainProfile(
            name="CIA Research Domain",
            description="Domain for CIA research documents",
        )

        project = KGProject(
            name="CIA Research Project",
            state=ProjectState.ACTIVE,
            domain_profile=profile,
            source_count=5,
            thing_count=150,
            connection_count=320,
            kb_id="kb_abc123def",
        )

        assert project.state == ProjectState.ACTIVE
        assert project.domain_profile is not None
        assert project.domain_profile.name == "CIA Research Domain"
        assert project.source_count == 5
        assert project.thing_count == 150
        assert project.connection_count == 320
        assert project.kb_id == "kb_abc123def"

    def test_kg_project_all_states(self):
        """Test that all ProjectState values are valid."""
        from app.kg.domain import KGProject, ProjectState

        # Test all states can be assigned
        states = [
            ProjectState.CREATED,
            ProjectState.BOOTSTRAPPING,
            ProjectState.ACTIVE,
            ProjectState.STABLE,
        ]

        for state in states:
            project = KGProject(name=f"Project in {state.value}", state=state)
            assert project.state == state

    def test_kg_project_timestamps(self):
        """Test that KGProject has created_at and updated_at timestamps."""
        from app.kg.domain import KGProject

        project = KGProject(name="Timestamped Project")

        assert project.created_at is not None
        assert project.updated_at is not None
        # updated_at should be at or after created_at
        assert project.updated_at >= project.created_at
