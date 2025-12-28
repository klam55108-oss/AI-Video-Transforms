"""
Dynamic extraction prompt generation from DomainProfile.

This module generates customized extraction prompts based on what was learned
during the bootstrap phase. The prompts adapt to the specific domain, entity
types, relationship types, and seed entities discovered in the first video.

Key Design Decisions:
- 14,000 char content limit leaves room for prompt overhead (~4K tokens)
- Formatting functions produce markdown for readability
- Seed entities are surfaced to ensure consistent naming across extractions
- Empty profile sections gracefully degrade to generic guidance
"""

from __future__ import annotations

from app.kg.domain import DomainProfile


# Maximum content length to include in extraction prompt
# Leaves room for ~4K tokens of prompt structure + domain context
MAX_CONTENT_LENGTH = 14000


def generate_extraction_prompt(
    profile: DomainProfile,
    title: str,
    content: str,
    source_type: str = "video",
) -> str:
    """
    Generate extraction prompt from domain profile.

    This is the key to generalization — the prompt adapts based on what was
    learned during bootstrap. The same extraction code works for documentaries,
    music analysis, technical content, or any other domain.

    Args:
        profile: Domain profile with thing types, connection types, and seed entities
        title: Title of the source content being processed
        content: Text content to extract entities from (will be truncated if needed)
        source_type: Type of source for context (default: "video")

    Returns:
        Complete extraction prompt string for Claude
    """
    thing_types_section = _format_thing_types(profile)
    connection_types_section = _format_connection_types(profile)
    seed_entities_section = _format_seed_entities(profile)

    # Truncate content if needed
    truncated = len(content) > MAX_CONTENT_LENGTH
    content_text = content[:MAX_CONTENT_LENGTH]

    return f"""# Entity and Relationship Extraction

You are extracting entities and relationships from content to build a knowledge graph.

## Domain Context

{profile.description}

{profile.extraction_context}

## Thing Types to Extract

{thing_types_section}

## Connection Types to Use

{connection_types_section}

## Known Entities (Use Consistent Labels)

{seed_entities_section}

## Output Format

Return valid JSON matching this schema:

```json
{{
  "entities": [
    {{
      "label": "Entity Name",
      "entity_type": "ThingType",
      "aliases": ["other", "names"],
      "description": "Brief description"
    }}
  ],
  "relationships": [
    {{
      "source_label": "Source Entity",
      "target_label": "Target Entity",
      "relationship_type": "connection_type",
      "confidence": 0.9,
      "evidence": "Quote or description supporting this"
    }}
  ],
  "discoveries": [
    {{
      "discovery_type": "thing_type",
      "name": "NewTypeName",
      "display_name": "New Type Name",
      "description": "Why this seems important",
      "examples": ["Example 1", "Example 2"]
    }}
  ],
  "summary": "2-3 sentence summary of key information extracted"
}}
```

## Guidelines

1. Use CONSISTENT labels — check Known Entities first
2. Include confidence scores (0.0-1.0) for relationships
3. **CRITICAL: Include evidence quotes** — For each relationship, provide a supporting quote from the transcript (50-150 chars)
4. Flag discoveries for new thing/connection types not in the lists above
5. Be thorough but avoid over-extraction
6. Capture cross-references to other content if apparent

## Evidence Examples

Good evidence for relationships:
- "worked_for": `"Sidney Gottlieb, who directed the CIA's MK-Ultra program..."`
- "mentioned_in": `"Fear is explored deeply in the song 'The Search'..."`
- "connected_to": `"These themes of isolation connect directly to his childhood experiences..."`

Evidence should be:
- Direct quotes or close paraphrases from the transcript
- 50-150 characters (enough context, not too long)
- Specific enough to verify the relationship claim

---

## Content Metadata

Title: {title}
Source Type: {source_type}

## Content

{content_text}

{"[Content truncated for length...]" if truncated else ""}
"""


def _format_thing_types(profile: DomainProfile) -> str:
    """
    Format thing types for prompt.

    Produces a bulleted list with descriptions and examples.
    Falls back to generic guidance if no thing types defined.

    Args:
        profile: Domain profile containing thing types

    Returns:
        Formatted markdown string with thing type definitions
    """
    if not profile.thing_types:
        return "Extract any relevant entities (people, places, organizations, events, etc.)"

    lines = []
    for t in sorted(profile.thing_types, key=lambda x: x.priority):
        examples = f" (e.g., {', '.join(t.examples[:3])})" if t.examples else ""
        lines.append(f"- **{t.name}**: {t.description}{examples}")
    return "\n".join(lines)


def _format_connection_types(profile: DomainProfile) -> str:
    """
    Format connection types for prompt.

    Produces a bulleted list with directionality indicators.
    Falls back to generic guidance if no connection types defined.

    Args:
        profile: Domain profile containing connection types

    Returns:
        Formatted markdown string with connection type definitions
    """
    if not profile.connection_types:
        return (
            "Use descriptive relationship types (e.g., worked_for, created, references)"
        )

    lines = []
    for c in profile.connection_types:
        direction = "→" if c.directional else "↔"
        lines.append(f"- **{c.name}** ({c.display_name}) {direction}: {c.description}")
    return "\n".join(lines)


def _format_seed_entities(profile: DomainProfile) -> str:
    """
    Format seed entities for consistency guidance.

    Surfaces known entities so the extraction uses consistent labels.
    This prevents duplicate nodes (e.g., "CIA" vs "Central Intelligence Agency").

    Args:
        profile: Domain profile containing seed entities

    Returns:
        Formatted markdown string with seed entity list
    """
    if not profile.seed_entities:
        return "No known entities yet — establish consistent labels."

    lines = []
    for e in profile.seed_entities:
        aliases = f" (also: {', '.join(e.aliases)})" if e.aliases else ""
        lines.append(f"- **{e.label}** [{e.thing_type}]{aliases}")
    return "\n".join(lines)
