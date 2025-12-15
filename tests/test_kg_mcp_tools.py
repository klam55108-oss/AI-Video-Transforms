"""
Tests for Knowledge Graph MCP Tools.

Tests the MCP tools in app/agent/kg_tool.py by mocking the KG service
dependency. Each tool is tested for success and error cases.

Note: The @tool decorator from claude_agent_sdk wraps functions in SdkMcpTool
objects. We access the underlying function via the `.handler` attribute.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.kg_tool import (
    bootstrap_kg_project,
    create_kg_project,
    extract_to_kg,
    get_kg_stats,
    list_kg_projects,
)
from app.kg.domain import (
    ConnectionType,
    DomainProfile,
    KGProject,
    ProjectState,
    SeedEntity,
    ThingType,
)

# Access the underlying handler functions from SdkMcpTool objects
_list_kg_projects = list_kg_projects.handler
_create_kg_project = create_kg_project.handler
_bootstrap_kg_project = bootstrap_kg_project.handler
_extract_to_kg = extract_to_kg.handler
_get_kg_stats = get_kg_stats.handler


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIXTURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.fixture
def mock_kg_service() -> MagicMock:
    """Create a mock KG service with async methods."""
    service = MagicMock()
    service.create_project = AsyncMock()
    service.get_project = AsyncMock()
    service.list_projects = AsyncMock()
    service.bootstrap_from_transcript = AsyncMock()
    service.extract_from_transcript = AsyncMock()
    service.get_graph_stats = AsyncMock()
    return service


@pytest.fixture
def sample_project() -> KGProject:
    """Create a sample KG project without domain profile (not bootstrapped)."""
    return KGProject(
        id="proj12345678",
        name="Test Project",
        state=ProjectState.CREATED,
        domain_profile=None,
        source_count=0,
        thing_count=0,
        connection_count=0,
    )


@pytest.fixture
def sample_domain_profile() -> DomainProfile:
    """Create a sample domain profile for bootstrapped projects."""
    return DomainProfile(
        name="Documentary Analysis",
        description="Domain for analyzing documentary content",
        thing_types=[
            ThingType(
                name="Person",
                description="A person mentioned in the content",
                examples=["John Doe", "Jane Smith"],
            ),
            ThingType(
                name="Organization",
                description="An organization or company",
                examples=["CIA", "FBI"],
            ),
        ],
        connection_types=[
            ConnectionType(
                name="worked_for",
                display_name="worked for",
                description="Employment relationship",
            ),
        ],
        seed_entities=[
            SeedEntity(label="John Doe", thing_type="Person", aliases=["J. Doe"]),
        ],
        extraction_context="Focus on people and organizations in government.",
        bootstrap_confidence=0.85,
        bootstrapped_from="src12345",
    )


@pytest.fixture
def bootstrapped_project(
    sample_project: KGProject, sample_domain_profile: DomainProfile
) -> KGProject:
    """Create a bootstrapped project with domain profile."""
    sample_project.state = ProjectState.ACTIVE
    sample_project.domain_profile = sample_domain_profile
    sample_project.source_count = 1
    return sample_project


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: list_kg_projects
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_list_kg_projects_empty(mock_kg_service: MagicMock) -> None:
    """Test listing projects when none exist."""
    mock_kg_service.list_projects.return_value = []

    with patch("app.agent.kg_tool._get_kg_service", return_value=mock_kg_service):
        result = await _list_kg_projects({})

    assert "content" in result
    assert len(result["content"]) == 1
    assert "No Knowledge Graph projects found" in result["content"][0]["text"]
    mock_kg_service.list_projects.assert_called_once()


@pytest.mark.asyncio
async def test_list_kg_projects_with_data(
    mock_kg_service: MagicMock, bootstrapped_project: KGProject
) -> None:
    """Test listing projects with existing data."""
    # Add some stats to the project
    bootstrapped_project.thing_count = 25
    bootstrapped_project.connection_count = 40
    bootstrapped_project.source_count = 3

    mock_kg_service.list_projects.return_value = [bootstrapped_project]

    with patch("app.agent.kg_tool._get_kg_service", return_value=mock_kg_service):
        result = await _list_kg_projects({})

    assert "content" in result
    text = result["content"][0]["text"]
    assert "Knowledge Graph Projects" in text
    assert bootstrapped_project.id in text
    assert bootstrapped_project.name in text
    assert "25" in text  # thing_count
    assert "40" in text  # connection_count
    assert "3" in text  # source_count


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: create_kg_project
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_create_kg_project_success(
    mock_kg_service: MagicMock, sample_project: KGProject
) -> None:
    """Test successful project creation."""
    mock_kg_service.create_project.return_value = sample_project

    with patch("app.agent.kg_tool._get_kg_service", return_value=mock_kg_service):
        result = await _create_kg_project({"name": "Test Project"})

    assert "content" in result
    text = result["content"][0]["text"]
    assert "Project Created" in text
    assert sample_project.id in text
    assert sample_project.name in text
    assert "bootstrap_kg_project" in text  # Should mention next step
    mock_kg_service.create_project.assert_called_once_with("Test Project")


@pytest.mark.asyncio
async def test_create_kg_project_empty_name(mock_kg_service: MagicMock) -> None:
    """Test project creation with empty name."""
    with patch("app.agent.kg_tool._get_kg_service", return_value=mock_kg_service):
        result = await _create_kg_project({"name": ""})

    assert result == {"success": False, "error": "Project name is required"}
    mock_kg_service.create_project.assert_not_called()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: bootstrap_kg_project
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_bootstrap_kg_project_success(
    mock_kg_service: MagicMock,
    sample_project: KGProject,
    sample_domain_profile: DomainProfile,
) -> None:
    """Test successful bootstrap of a project."""
    mock_kg_service.get_project.return_value = sample_project
    mock_kg_service.bootstrap_from_transcript.return_value = sample_domain_profile

    args = {
        "project_id": sample_project.id,
        "transcript": "This is a test transcript about John Doe at the CIA.",
        "title": "Test Documentary",
    }

    with patch("app.agent.kg_tool._get_kg_service", return_value=mock_kg_service):
        result = await _bootstrap_kg_project(args)

    assert "content" in result
    text = result["content"][0]["text"]
    assert "Bootstrap Complete" in text
    assert "Entity Types Detected" in text
    assert "Person" in text
    assert "Organization" in text
    assert "Relationship Types Detected" in text
    assert "worked for" in text or "worked_for" in text
    assert "extract_to_kg" in text  # Should mention next step

    mock_kg_service.get_project.assert_called_once_with(sample_project.id)
    mock_kg_service.bootstrap_from_transcript.assert_called_once()


@pytest.mark.asyncio
async def test_bootstrap_kg_project_already_done(
    mock_kg_service: MagicMock, bootstrapped_project: KGProject
) -> None:
    """Test bootstrap fails when project already has domain profile."""
    mock_kg_service.get_project.return_value = bootstrapped_project

    args = {
        "project_id": bootstrapped_project.id,
        "transcript": "Some transcript",
        "title": "Some title",
    }

    with patch("app.agent.kg_tool._get_kg_service", return_value=mock_kg_service):
        result = await _bootstrap_kg_project(args)

    assert result["success"] is False
    assert "already bootstrapped" in result["error"]
    assert "extract_to_kg" in result["error"]  # Should suggest alternative
    mock_kg_service.bootstrap_from_transcript.assert_not_called()


@pytest.mark.asyncio
async def test_bootstrap_kg_project_not_found(mock_kg_service: MagicMock) -> None:
    """Test bootstrap fails when project doesn't exist."""
    mock_kg_service.get_project.return_value = None

    args = {
        "project_id": "nonexistent",
        "transcript": "Some transcript",
        "title": "Some title",
    }

    with patch("app.agent.kg_tool._get_kg_service", return_value=mock_kg_service):
        result = await _bootstrap_kg_project(args)

    assert result["success"] is False
    assert "not found" in result["error"]
    mock_kg_service.bootstrap_from_transcript.assert_not_called()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: extract_to_kg
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_extract_to_kg_success(
    mock_kg_service: MagicMock, bootstrapped_project: KGProject
) -> None:
    """Test successful extraction from transcript."""
    mock_kg_service.get_project.return_value = bootstrapped_project
    mock_kg_service.extract_from_transcript.return_value = {
        "entities_extracted": 15,
        "relationships_extracted": 22,
        "discoveries": 2,
        "summary": "Extracted key figures and their connections.",
    }

    args = {
        "project_id": bootstrapped_project.id,
        "transcript": "John Doe worked for the CIA in the 1960s.",
        "title": "Episode 2: The Early Years",
        "source_id": "ep2_12345",
    }

    with patch("app.agent.kg_tool._get_kg_service", return_value=mock_kg_service):
        result = await _extract_to_kg(args)

    assert "content" in result
    text = result["content"][0]["text"]
    assert "Extraction Complete" in text
    assert "15" in text  # entities
    assert "22" in text  # relationships
    assert "2" in text  # discoveries
    assert "Episode 2" in text
    assert "ep2_12345" in text

    mock_kg_service.extract_from_transcript.assert_called_once_with(
        project_id=bootstrapped_project.id,
        transcript="John Doe worked for the CIA in the 1960s.",
        title="Episode 2: The Early Years",
        source_id="ep2_12345",
    )


@pytest.mark.asyncio
async def test_extract_to_kg_generates_source_id(
    mock_kg_service: MagicMock, bootstrapped_project: KGProject
) -> None:
    """Test extraction generates source_id when not provided."""
    mock_kg_service.get_project.return_value = bootstrapped_project
    mock_kg_service.extract_from_transcript.return_value = {
        "entities_extracted": 5,
        "relationships_extracted": 3,
        "discoveries": 0,
        "summary": None,
    }

    args = {
        "project_id": bootstrapped_project.id,
        "transcript": "Some content.",
        "title": "Test Title",
        # No source_id provided
    }

    with patch("app.agent.kg_tool._get_kg_service", return_value=mock_kg_service):
        result = await _extract_to_kg(args)

    assert "content" in result
    # Verify extract was called with a generated source_id (8 hex chars)
    call_kwargs = mock_kg_service.extract_from_transcript.call_args.kwargs
    assert len(call_kwargs["source_id"]) == 8


@pytest.mark.asyncio
async def test_extract_to_kg_not_bootstrapped(
    mock_kg_service: MagicMock, sample_project: KGProject
) -> None:
    """Test extraction fails when project is not bootstrapped."""
    # sample_project has no domain_profile
    mock_kg_service.get_project.return_value = sample_project

    args = {
        "project_id": sample_project.id,
        "transcript": "Some transcript",
        "title": "Some title",
    }

    with patch("app.agent.kg_tool._get_kg_service", return_value=mock_kg_service):
        result = await _extract_to_kg(args)

    assert result["success"] is False
    assert "not been bootstrapped" in result["error"]
    assert "bootstrap_kg_project" in result["error"]  # Should suggest fix
    mock_kg_service.extract_from_transcript.assert_not_called()


@pytest.mark.asyncio
async def test_extract_to_kg_project_not_found(mock_kg_service: MagicMock) -> None:
    """Test extraction fails when project doesn't exist."""
    mock_kg_service.get_project.return_value = None

    args = {
        "project_id": "nonexistent",
        "transcript": "Some transcript",
        "title": "Some title",
    }

    with patch("app.agent.kg_tool._get_kg_service", return_value=mock_kg_service):
        result = await _extract_to_kg(args)

    assert result["success"] is False
    assert "not found" in result["error"]
    mock_kg_service.extract_from_transcript.assert_not_called()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: get_kg_stats
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_kg_stats_success(
    mock_kg_service: MagicMock, bootstrapped_project: KGProject
) -> None:
    """Test successful retrieval of graph statistics."""
    mock_kg_service.get_project.return_value = bootstrapped_project
    mock_kg_service.get_graph_stats.return_value = {
        "node_count": 50,
        "edge_count": 120,
        "source_count": 5,
        "nodes_by_type": {
            "Person": 30,
            "Organization": 15,
            "Event": 5,
        },
        "edges_by_type": {
            "worked_for": 45,
            "participated_in": 35,
            "funded_by": 40,
        },
    }

    with patch("app.agent.kg_tool._get_kg_service", return_value=mock_kg_service):
        result = await _get_kg_stats({"project_id": bootstrapped_project.id})

    assert "content" in result
    text = result["content"][0]["text"]
    assert "Statistics for" in text
    assert "50" in text  # node_count
    assert "120" in text  # edge_count
    assert "Person: 30" in text
    assert "Organization: 15" in text
    assert "worked_for: 45" in text


@pytest.mark.asyncio
async def test_get_kg_stats_no_data(
    mock_kg_service: MagicMock, sample_project: KGProject
) -> None:
    """Test stats when project has no graph data yet."""
    mock_kg_service.get_project.return_value = sample_project
    mock_kg_service.get_graph_stats.return_value = None

    with patch("app.agent.kg_tool._get_kg_service", return_value=mock_kg_service):
        result = await _get_kg_stats({"project_id": sample_project.id})

    assert "content" in result
    text = result["content"][0]["text"]
    assert "No graph data yet" in text
    assert "bootstrapped" in text


@pytest.mark.asyncio
async def test_get_kg_stats_project_not_found(mock_kg_service: MagicMock) -> None:
    """Test stats fails when project doesn't exist."""
    mock_kg_service.get_project.return_value = None

    with patch("app.agent.kg_tool._get_kg_service", return_value=mock_kg_service):
        result = await _get_kg_stats({"project_id": "nonexistent"})

    assert result["success"] is False
    assert "not found" in result["error"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: Error Handling
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_tool_handles_service_exception(mock_kg_service: MagicMock) -> None:
    """Test that tools gracefully handle service exceptions."""
    mock_kg_service.list_projects.side_effect = RuntimeError(
        "Database connection failed"
    )

    with patch("app.agent.kg_tool._get_kg_service", return_value=mock_kg_service):
        result = await _list_kg_projects({})

    assert result["success"] is False
    assert "Database connection failed" in result["error"]


@pytest.mark.asyncio
async def test_extract_handles_extraction_failure(
    mock_kg_service: MagicMock, bootstrapped_project: KGProject
) -> None:
    """Test that extract_to_kg handles extraction failures gracefully."""
    mock_kg_service.get_project.return_value = bootstrapped_project
    mock_kg_service.extract_from_transcript.side_effect = RuntimeError(
        "LLM rate limit exceeded"
    )

    args = {
        "project_id": bootstrapped_project.id,
        "transcript": "Some transcript",
        "title": "Some title",
    }

    with patch("app.agent.kg_tool._get_kg_service", return_value=mock_kg_service):
        result = await _extract_to_kg(args)

    assert result["success"] is False
    assert "LLM rate limit exceeded" in result["error"]
