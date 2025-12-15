"""
End-to-End Tests for Knowledge Graph Flow.

Tests the complete workflow: create → bootstrap → extract → get_stats
using real KnowledgeGraphService with mocked Claude API calls.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.kg_tool import (
    bootstrap_kg_project,
    create_kg_project,
    extract_to_kg,
    get_kg_stats,
)
from app.kg.domain import (
    ConnectionType,
    DomainProfile,
    ProjectState,
    SeedEntity,
    ThingType,
)
from app.kg.schemas import (
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)
from app.services.kg_service import KnowledgeGraphService

# Access the underlying handler functions from SdkMcpTool objects
_create_kg_project = create_kg_project.handler
_bootstrap_kg_project = bootstrap_kg_project.handler
_extract_to_kg = extract_to_kg.handler
_get_kg_stats = get_kg_stats.handler

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SAMPLE DATA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TRANSCRIPT_1 = """
Dr. Sidney Gottlieb directed the CIA's MK-Ultra program.
He reported to Allen Dulles, the Director of Central Intelligence.
The program began in 1953 and involved research into mind control techniques.
"""

TRANSCRIPT_2 = """
Operation Midnight Climax was run by George White in San Francisco,
funded by the CIA. It was one of many MK-Ultra subprojects that tested
LSD on unwitting subjects in safehouses across the city.
"""


def create_mock_domain_profile() -> DomainProfile:
    """Create a realistic domain profile for MK-Ultra documentary content."""
    return DomainProfile(
        name="CIA Mind Control Programs",
        description="Domain covering CIA psychological research programs and key personnel",
        thing_types=[
            ThingType(
                name="Person",
                description="Individuals involved in the programs",
                examples=["Sidney Gottlieb", "Allen Dulles"],
                priority=1,
            ),
            ThingType(
                name="Organization",
                description="Government agencies and institutions",
                examples=["CIA", "US Army"],
                priority=1,
            ),
            ThingType(
                name="Program",
                description="Covert operations and research projects",
                examples=["MK-Ultra", "Operation Midnight Climax"],
                priority=1,
            ),
            ThingType(
                name="Location",
                description="Places where operations occurred",
                examples=["San Francisco", "Fort Detrick"],
                priority=2,
            ),
        ],
        connection_types=[
            ConnectionType(
                name="directed",
                display_name="directed",
                description="Person directed a program or operation",
                examples=[("Sidney Gottlieb", "MK-Ultra")],
            ),
            ConnectionType(
                name="reported_to",
                display_name="reported to",
                description="Reporting relationship between people",
                examples=[("Sidney Gottlieb", "Allen Dulles")],
            ),
            ConnectionType(
                name="funded_by",
                display_name="funded by",
                description="Financial support relationship",
                examples=[("Operation Midnight Climax", "CIA")],
            ),
            ConnectionType(
                name="located_in",
                display_name="located in",
                description="Geographic location of operations",
                examples=[("Operation Midnight Climax", "San Francisco")],
            ),
        ],
        seed_entities=[
            SeedEntity(
                label="Sidney Gottlieb",
                thing_type="Person",
                aliases=["Dr. Gottlieb", "Joseph Scheider"],
            ),
            SeedEntity(
                label="CIA",
                thing_type="Organization",
                aliases=["Central Intelligence Agency"],
            ),
            SeedEntity(
                label="MK-Ultra",
                thing_type="Program",
                aliases=["Project MK-Ultra", "MKULTRA"],
            ),
        ],
        extraction_context="Focus on CIA personnel, programs, and their relationships.",
        bootstrap_confidence=0.9,
        bootstrapped_from="ep1_source",
    )


def create_mock_extraction_result_ep2() -> ExtractionResult:
    """Create extraction result for Episode 2 transcript."""
    return ExtractionResult(
        entities=[
            ExtractedEntity(
                label="Operation Midnight Climax",
                entity_type="Program",
                aliases=["Midnight Climax"],
                description="CIA safehouse operation testing LSD",
            ),
            ExtractedEntity(
                label="George White",
                entity_type="Person",
                aliases=["George Hunter White"],
                description="Federal narcotics agent who ran Midnight Climax",
            ),
            ExtractedEntity(
                label="San Francisco",
                entity_type="Location",
                aliases=["SF"],
                description="Location of Operation Midnight Climax safehouses",
            ),
            ExtractedEntity(
                label="CIA",
                entity_type="Organization",
                aliases=["Central Intelligence Agency"],
                description="Funding agency for MK-Ultra subprojects",
            ),
        ],
        relationships=[
            ExtractedRelationship(
                source_label="George White",
                target_label="Operation Midnight Climax",
                relationship_type="directed",
                confidence=0.95,
                evidence="Operation Midnight Climax was run by George White",
            ),
            ExtractedRelationship(
                source_label="Operation Midnight Climax",
                target_label="San Francisco",
                relationship_type="located_in",
                confidence=0.98,
                evidence="in San Francisco",
            ),
            ExtractedRelationship(
                source_label="Operation Midnight Climax",
                target_label="CIA",
                relationship_type="funded_by",
                confidence=0.95,
                evidence="funded by the CIA",
            ),
        ],
        discoveries=[],
        summary="Extracted entities and relationships about Operation Midnight Climax.",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIXTURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.fixture
def kg_service(tmp_path: Path) -> KnowledgeGraphService:
    """Create a real KnowledgeGraphService with tmp_path storage."""
    return KnowledgeGraphService(data_path=tmp_path)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# E2E TEST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_complete_video_to_kg_flow(kg_service: KnowledgeGraphService) -> None:
    """
    Test the complete Knowledge Graph workflow from video transcript to populated graph.

    Flow:
    1. Create project → get project_id
    2. Bootstrap with first transcript → creates domain profile
    3. Extract from second transcript → populates graph
    4. Get stats → verify counts > 0

    This tests the integration between MCP tools and the KnowledgeGraphService,
    with Claude API calls mocked to return realistic data.
    """
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: Create Project
    # ─────────────────────────────────────────────────────────────────────────
    with patch("app.agent.kg_tool._get_kg_service", return_value=kg_service):
        result = await _create_kg_project({"name": "Test Documentary"})

    assert "content" in result, f"Expected content in result, got: {result}"
    text = result["content"][0]["text"]
    assert "Project Created" in text
    assert "Test Documentary" in text

    # Extract project_id from the response
    # The format is: **ID:** `{project_id}`
    match = re.search(r"\*\*ID:\*\* `([^`]+)`", text)
    assert match, f"Could not find project ID in response: {text}"
    project_id = match.group(1)

    # Verify project exists in service
    project = await kg_service.get_project(project_id)
    assert project is not None
    assert project.name == "Test Documentary"
    assert project.state == ProjectState.CREATED
    assert project.domain_profile is None  # Not bootstrapped yet

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: Bootstrap with First Transcript
    # ─────────────────────────────────────────────────────────────────────────
    mock_domain_profile = create_mock_domain_profile()

    # Mock the Claude-dependent bootstrap_from_transcript method
    with patch.object(
        kg_service,
        "bootstrap_from_transcript",
        new=AsyncMock(return_value=mock_domain_profile),
    ) as mock_bootstrap:
        with patch("app.agent.kg_tool._get_kg_service", return_value=kg_service):
            result = await _bootstrap_kg_project(
                {
                    "project_id": project_id,
                    "transcript": TRANSCRIPT_1,
                    "title": "Episode 1: The Origins",
                }
            )

    assert "content" in result, f"Expected content in result, got: {result}"
    text = result["content"][0]["text"]
    assert "Bootstrap Complete" in text
    assert "Entity Types Detected" in text
    assert "Person" in text
    assert "Organization" in text
    assert "Relationship Types Detected" in text
    assert "directed" in text or "reported to" in text

    # Verify bootstrap was called with correct args
    mock_bootstrap.assert_called_once()
    call_kwargs = mock_bootstrap.call_args.kwargs
    assert call_kwargs["project_id"] == project_id
    assert "Sidney Gottlieb" in call_kwargs["transcript"]
    assert call_kwargs["title"] == "Episode 1: The Origins"

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: Simulate project state update (normally done by real bootstrap)
    # ─────────────────────────────────────────────────────────────────────────
    # Since we mocked bootstrap_from_transcript, we need to manually update project state
    project = await kg_service.get_project(project_id)
    assert project is not None, "Project should exist after creation"
    project.domain_profile = mock_domain_profile
    project.state = ProjectState.ACTIVE
    project.source_count = 1
    await kg_service._save_project(project)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: Extract from Second Transcript
    # ─────────────────────────────────────────────────────────────────────────
    mock_extraction_result = {
        "entities_extracted": 4,
        "relationships_extracted": 3,
        "discoveries": 0,
        "summary": "Extracted entities about Operation Midnight Climax.",
    }

    # Mock the Claude-dependent extract_from_transcript method
    with patch.object(
        kg_service,
        "extract_from_transcript",
        new=AsyncMock(return_value=mock_extraction_result),
    ) as mock_extract:
        with patch("app.agent.kg_tool._get_kg_service", return_value=kg_service):
            result = await _extract_to_kg(
                {
                    "project_id": project_id,
                    "transcript": TRANSCRIPT_2,
                    "title": "Episode 2: Midnight Climax",
                    "source_id": "ep2_test",
                }
            )

    assert "content" in result, f"Expected content in result, got: {result}"
    text = result["content"][0]["text"]
    assert "Extraction Complete" in text
    assert "Episode 2: Midnight Climax" in text
    assert "ep2_test" in text
    assert "4" in text  # entities_extracted
    assert "3" in text  # relationships_extracted

    # Verify extract was called with correct args
    mock_extract.assert_called_once()
    call_kwargs = mock_extract.call_args.kwargs
    assert call_kwargs["project_id"] == project_id
    assert "George White" in call_kwargs["transcript"]
    assert call_kwargs["title"] == "Episode 2: Midnight Climax"
    assert call_kwargs["source_id"] == "ep2_test"

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5: Simulate project stats update (normally done by real extraction)
    # ─────────────────────────────────────────────────────────────────────────
    project = await kg_service.get_project(project_id)
    assert project is not None, "Project should exist"
    project.thing_count = 4
    project.connection_count = 3
    project.source_count = 2
    await kg_service._save_project(project)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 6: Get Stats and Verify
    # ─────────────────────────────────────────────────────────────────────────
    mock_stats = {
        "node_count": 4,
        "edge_count": 3,
        "source_count": 2,
        "nodes_by_type": {
            "Person": 1,
            "Program": 1,
            "Location": 1,
            "Organization": 1,
        },
        "edges_by_type": {
            "directed": 1,
            "located_in": 1,
            "funded_by": 1,
        },
    }

    with patch.object(
        kg_service,
        "get_graph_stats",
        new=AsyncMock(return_value=mock_stats),
    ):
        with patch("app.agent.kg_tool._get_kg_service", return_value=kg_service):
            result = await _get_kg_stats({"project_id": project_id})

    assert "content" in result, f"Expected content in result, got: {result}"
    text = result["content"][0]["text"]
    assert "Statistics for" in text

    # Verify counts are present and > 0
    assert "4" in text  # node_count
    assert "3" in text  # edge_count
    assert "2" in text  # source_count

    # Verify type breakdowns
    assert "Person" in text
    assert "Organization" in text
    assert "directed" in text or "funded_by" in text


@pytest.mark.asyncio
async def test_flow_rejects_extract_before_bootstrap(
    kg_service: KnowledgeGraphService,
) -> None:
    """
    Test that extraction is properly rejected when project isn't bootstrapped.

    This verifies the workflow enforcement: bootstrap must come before extract.
    """
    # Create project
    with patch("app.agent.kg_tool._get_kg_service", return_value=kg_service):
        result = await _create_kg_project({"name": "Unbootstrapped Project"})

    text = result["content"][0]["text"]
    match = re.search(r"\*\*ID:\*\* `([^`]+)`", text)
    assert match is not None, "Could not find project ID in response"
    project_id = match.group(1)

    # Try to extract without bootstrapping first
    with patch("app.agent.kg_tool._get_kg_service", return_value=kg_service):
        result = await _extract_to_kg(
            {
                "project_id": project_id,
                "transcript": TRANSCRIPT_2,
                "title": "Episode 2",
            }
        )

    # Should fail with helpful error message
    assert result.get("success") is False
    assert "not been bootstrapped" in result["error"]
    assert "bootstrap_kg_project" in result["error"]


@pytest.mark.asyncio
async def test_flow_rejects_double_bootstrap(
    kg_service: KnowledgeGraphService,
) -> None:
    """
    Test that a second bootstrap attempt is rejected.

    Projects should only be bootstrapped once. Additional content
    should use extract_to_kg instead.
    """
    # Create project
    with patch("app.agent.kg_tool._get_kg_service", return_value=kg_service):
        result = await _create_kg_project({"name": "Already Bootstrapped"})

    text = result["content"][0]["text"]
    match = re.search(r"\*\*ID:\*\* `([^`]+)`", text)
    assert match is not None, "Could not find project ID in response"
    project_id = match.group(1)

    # Manually set up a bootstrapped project
    project = await kg_service.get_project(project_id)
    assert project is not None, "Project should exist after creation"
    project.domain_profile = create_mock_domain_profile()
    project.state = ProjectState.ACTIVE
    await kg_service._save_project(project)

    # Try to bootstrap again
    with patch("app.agent.kg_tool._get_kg_service", return_value=kg_service):
        result = await _bootstrap_kg_project(
            {
                "project_id": project_id,
                "transcript": TRANSCRIPT_1,
                "title": "Another Episode",
            }
        )

    # Should fail with helpful error message
    assert result.get("success") is False
    assert "already bootstrapped" in result["error"]
    assert "extract_to_kg" in result["error"]
