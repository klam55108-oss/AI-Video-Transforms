"""
Tests for Knowledge Graph dynamic extraction prompt generation.

These tests cover the template functions that generate Claude extraction prompts
from a DomainProfile. The templates adapt to domain-specific entity types,
relationship types, and seed entities discovered during bootstrap.
"""

import pytest

from app.kg.domain import (
    DomainProfile,
    ThingType,
    ConnectionType,
    SeedEntity,
)
from app.kg.prompts.templates import (
    generate_extraction_prompt,
    _format_thing_types,
    _format_connection_types,
    _format_seed_entities,
    MAX_CONTENT_LENGTH,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Fixtures
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.fixture
def domain_profile() -> DomainProfile:
    """Create a fully populated DomainProfile for testing.

    This fixture represents a domain profile bootstrapped from a documentary
    about CIA mind control research, with realistic entity types, relationship
    types, and seed entities.
    """
    return DomainProfile(
        id="profile_test",
        name="CIA Mind Control Research",
        description="Knowledge graph about CIA mind control programs and experiments.",
        thing_types=[
            ThingType(
                name="Person",
                description="Individual involved in the research",
                examples=["Sidney Gottlieb", "Allen Dulles"],
                priority=1,
                icon="👤",
            ),
            ThingType(
                name="Organization",
                description="Government agency or institution",
                examples=["CIA", "TSS"],
                priority=1,
                icon="🏛️",
            ),
            ThingType(
                name="Project",
                description="Named research program or operation",
                examples=["MKUltra", "Operation Paperclip"],
                priority=2,
                icon="📁",
            ),
        ],
        connection_types=[
            ConnectionType(
                name="worked_for",
                display_name="worked for",
                description="Employment or operational relationship",
                directional=True,
            ),
            ConnectionType(
                name="funded",
                display_name="funded",
                description="Financial support relationship",
                directional=True,
            ),
            ConnectionType(
                name="collaborated_with",
                display_name="collaborated with",
                description="Joint work relationship",
                directional=False,
            ),
        ],
        seed_entities=[
            SeedEntity(
                label="CIA",
                thing_type="Organization",
                aliases=["Central Intelligence Agency", "The Agency", "Langley"],
                description="U.S. foreign intelligence service",
            ),
            SeedEntity(
                label="Sidney Gottlieb",
                thing_type="Person",
                aliases=["Dr. Gottlieb", "Joseph Scheider"],
            ),
            SeedEntity(
                label="MKUltra",
                thing_type="Project",
                aliases=["Project MKUltra", "MK-Ultra"],
            ),
        ],
        extraction_context="Focus on identifying relationships between individuals, organizations, and research programs.",
    )


@pytest.fixture
def empty_profile() -> DomainProfile:
    """Create an empty DomainProfile for fallback testing."""
    return DomainProfile(
        id="empty_profile",
        name="Empty Domain",
        description="A domain with no types or entities defined.",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# generate_extraction_prompt Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_generate_extraction_prompt_includes_domain_context(
    domain_profile: DomainProfile,
) -> None:
    """Extraction prompt should include domain description and context."""
    prompt = generate_extraction_prompt(
        profile=domain_profile,
        title="MKUltra Documentary Part 1",
        content="Sample transcript content here.",
    )

    # Domain description should appear
    assert domain_profile.description in prompt

    # Extraction context should appear
    assert domain_profile.extraction_context in prompt

    # Title should appear in metadata section
    assert "MKUltra Documentary Part 1" in prompt

    # Default source type
    assert "Source Type: video" in prompt


def test_generate_extraction_prompt_includes_thing_types(
    domain_profile: DomainProfile,
) -> None:
    """Extraction prompt should list all thing types with descriptions."""
    prompt = generate_extraction_prompt(
        profile=domain_profile,
        title="Test Video",
        content="Test content",
    )

    # Each thing type should appear with description
    assert "**Person**:" in prompt
    assert "**Organization**:" in prompt
    assert "**Project**:" in prompt

    # Descriptions should appear
    assert "Individual involved in the research" in prompt
    assert "Government agency or institution" in prompt


def test_generate_extraction_prompt_includes_connection_types(
    domain_profile: DomainProfile,
) -> None:
    """Extraction prompt should list all connection types."""
    prompt = generate_extraction_prompt(
        profile=domain_profile,
        title="Test Video",
        content="Test content",
    )

    # Connection types with display names
    assert "**worked_for**" in prompt
    assert "(worked for)" in prompt
    assert "**funded**" in prompt
    assert "**collaborated_with**" in prompt

    # Directional indicators
    assert "→" in prompt  # Directional relationship
    assert "↔" in prompt  # Bidirectional relationship


def test_generate_extraction_prompt_includes_seed_entities(
    domain_profile: DomainProfile,
) -> None:
    """Extraction prompt should include seed entities for consistency."""
    prompt = generate_extraction_prompt(
        profile=domain_profile,
        title="Test Video",
        content="Test content",
    )

    # Seed entities with types
    assert "**CIA** [Organization]" in prompt
    assert "**Sidney Gottlieb** [Person]" in prompt
    assert "**MKUltra** [Project]" in prompt

    # Aliases should appear
    assert "Central Intelligence Agency" in prompt
    assert "Dr. Gottlieb" in prompt


def test_generate_extraction_prompt_includes_content(
    domain_profile: DomainProfile,
) -> None:
    """Extraction prompt should include the transcript content."""
    content = "This is the actual transcript from the video about MKUltra."

    prompt = generate_extraction_prompt(
        profile=domain_profile,
        title="Documentary",
        content=content,
    )

    assert content in prompt


def test_generate_extraction_prompt_custom_source_type(
    domain_profile: DomainProfile,
) -> None:
    """Extraction prompt should accept custom source type."""
    prompt = generate_extraction_prompt(
        profile=domain_profile,
        title="Song Analysis",
        content="Lyrics content",
        source_type="lyrics",
    )

    assert "Source Type: lyrics" in prompt


def test_generate_extraction_prompt_empty_profile(
    empty_profile: DomainProfile,
) -> None:
    """Extraction prompt should provide fallback guidance for empty profile."""
    prompt = generate_extraction_prompt(
        profile=empty_profile,
        title="Unknown Content",
        content="Some text to analyze",
    )

    # Fallback thing types guidance
    assert "Extract any relevant entities" in prompt

    # Fallback connection types guidance
    assert "Use descriptive relationship types" in prompt

    # Fallback seed entities guidance
    assert "No known entities yet" in prompt


def test_generate_extraction_prompt_includes_output_schema(
    domain_profile: DomainProfile,
) -> None:
    """Extraction prompt should include JSON output schema."""
    prompt = generate_extraction_prompt(
        profile=domain_profile,
        title="Test",
        content="Test",
    )

    # Schema structure should appear
    assert '"entities":' in prompt
    assert '"relationships":' in prompt
    assert '"discoveries":' in prompt
    assert '"summary":' in prompt

    # Field names from schema
    assert '"label":' in prompt
    assert '"entity_type":' in prompt
    assert '"source_label":' in prompt
    assert '"target_label":' in prompt
    assert '"confidence":' in prompt


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# _format_thing_types Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_format_thing_types_with_examples(domain_profile: DomainProfile) -> None:
    """Thing types formatting should include examples."""
    output = _format_thing_types(domain_profile)

    # Check format: - **Name**: Description (e.g., Example1, Example2)
    assert "- **Person**:" in output
    assert "Sidney Gottlieb" in output
    assert "Allen Dulles" in output

    # Examples should be in parenthetical format
    assert "(e.g.," in output


def test_format_thing_types_sorted_by_priority(domain_profile: DomainProfile) -> None:
    """Thing types should be sorted by priority (lower = higher priority)."""
    output = _format_thing_types(domain_profile)

    # Priority 1 types should appear before priority 2
    person_pos = output.index("**Person**")
    org_pos = output.index("**Organization**")
    project_pos = output.index("**Project**")

    # Person and Organization have priority 1, Project has priority 2
    assert project_pos > person_pos
    assert project_pos > org_pos


def test_format_thing_types_empty(empty_profile: DomainProfile) -> None:
    """Empty thing types should return fallback guidance."""
    output = _format_thing_types(empty_profile)

    assert "Extract any relevant entities" in output
    assert "people, places, organizations, events" in output


def test_format_thing_types_limits_examples() -> None:
    """Thing types formatting should limit to 3 examples max."""
    profile = DomainProfile(
        name="Test",
        description="Test domain",
        thing_types=[
            ThingType(
                name="TestType",
                description="A test type",
                examples=["Ex1", "Ex2", "Ex3", "Ex4", "Ex5"],
            ),
        ],
    )

    output = _format_thing_types(profile)

    # Should only include first 3 examples
    assert "Ex1" in output
    assert "Ex2" in output
    assert "Ex3" in output
    assert "Ex4" not in output
    assert "Ex5" not in output


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# _format_connection_types Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_format_connection_types_directional(domain_profile: DomainProfile) -> None:
    """Directional connections should show → arrow."""
    output = _format_connection_types(domain_profile)

    # worked_for is directional
    assert "**worked_for**" in output
    assert "→" in output


def test_format_connection_types_bidirectional(domain_profile: DomainProfile) -> None:
    """Bidirectional connections should show ↔ arrow."""
    output = _format_connection_types(domain_profile)

    # collaborated_with is not directional
    assert "**collaborated_with**" in output
    assert "↔" in output


def test_format_connection_types_includes_display_name(
    domain_profile: DomainProfile,
) -> None:
    """Connection types should include display name in parentheses."""
    output = _format_connection_types(domain_profile)

    # Format: **name** (display_name) direction: description
    assert "(worked for)" in output
    assert "(funded)" in output
    assert "(collaborated with)" in output


def test_format_connection_types_empty(empty_profile: DomainProfile) -> None:
    """Empty connection types should return fallback guidance."""
    output = _format_connection_types(empty_profile)

    assert "Use descriptive relationship types" in output
    assert "worked_for" in output
    assert "created" in output
    assert "references" in output


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# _format_seed_entities Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_format_seed_entities_with_aliases(domain_profile: DomainProfile) -> None:
    """Seed entities formatting should include aliases."""
    output = _format_seed_entities(domain_profile)

    # CIA has aliases
    assert "**CIA** [Organization]" in output
    assert "(also: Central Intelligence Agency" in output
    assert "The Agency" in output
    assert "Langley" in output


def test_format_seed_entities_without_aliases() -> None:
    """Seed entities without aliases should not show 'also:' section."""
    profile = DomainProfile(
        name="Test",
        description="Test domain",
        seed_entities=[
            SeedEntity(
                label="NoAliasEntity",
                thing_type="Thing",
                aliases=[],  # No aliases
            ),
        ],
    )

    output = _format_seed_entities(profile)

    assert "**NoAliasEntity** [Thing]" in output
    assert "(also:" not in output


def test_format_seed_entities_empty(empty_profile: DomainProfile) -> None:
    """Empty seed entities should return fallback guidance."""
    output = _format_seed_entities(empty_profile)

    assert "No known entities yet" in output
    assert "establish consistent labels" in output


def test_format_seed_entities_multiple(domain_profile: DomainProfile) -> None:
    """All seed entities should appear in output."""
    output = _format_seed_entities(domain_profile)

    # All three seed entities from fixture
    assert "**CIA**" in output
    assert "**Sidney Gottlieb**" in output
    assert "**MKUltra**" in output

    # Each with their type
    assert "[Organization]" in output
    assert "[Person]" in output
    assert "[Project]" in output


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Content Truncation Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_truncates_long_content(domain_profile: DomainProfile) -> None:
    """Long content should be truncated to MAX_CONTENT_LENGTH."""
    # Create content longer than MAX_CONTENT_LENGTH
    long_content = "A" * (MAX_CONTENT_LENGTH + 1000)

    prompt = generate_extraction_prompt(
        profile=domain_profile,
        title="Long Content Test",
        content=long_content,
    )

    # Content should be truncated
    assert len(long_content) > MAX_CONTENT_LENGTH

    # Full long content should NOT appear
    assert long_content not in prompt

    # Truncated content SHOULD appear
    truncated = long_content[:MAX_CONTENT_LENGTH]
    assert truncated in prompt

    # Truncation notice should appear
    assert "[Content truncated for length...]" in prompt


def test_short_content_not_truncated(domain_profile: DomainProfile) -> None:
    """Short content should not show truncation notice."""
    short_content = "This is a short transcript."

    prompt = generate_extraction_prompt(
        profile=domain_profile,
        title="Short Content",
        content=short_content,
    )

    # Full content should appear
    assert short_content in prompt

    # No truncation notice
    assert "[Content truncated" not in prompt


def test_exact_length_content_not_truncated(domain_profile: DomainProfile) -> None:
    """Content exactly at MAX_CONTENT_LENGTH should not be truncated."""
    exact_content = "B" * MAX_CONTENT_LENGTH

    prompt = generate_extraction_prompt(
        profile=domain_profile,
        title="Exact Length",
        content=exact_content,
    )

    # Full content should appear
    assert exact_content in prompt

    # No truncation notice (equals limit, not exceeds)
    assert "[Content truncated" not in prompt


def test_max_content_length_constant() -> None:
    """MAX_CONTENT_LENGTH should be a reasonable size for context window."""
    # Should leave room for ~4K tokens of prompt overhead
    assert MAX_CONTENT_LENGTH == 14000

    # Sanity check: should be positive and reasonable
    assert 10000 < MAX_CONTENT_LENGTH < 50000
