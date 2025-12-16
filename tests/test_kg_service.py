"""
Tests for Knowledge Graph Service.

This module tests the KnowledgeGraphService including:
- Project lifecycle (create, get, list)
- Persistence (atomic writes, cross-instance persistence)
- Discovery confirmation workflow

Uses tmp_path fixture for isolated test directories.
All tests are async using @pytest.mark.asyncio.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
from app.services.kg_service import KnowledgeGraphService

if TYPE_CHECKING:
    pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIXTURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.fixture
def kg_service(tmp_path: Path) -> KnowledgeGraphService:
    """Create a KnowledgeGraphService with isolated tmp_path directory."""
    return KnowledgeGraphService(data_path=tmp_path)


@pytest.fixture
def sample_domain_profile() -> DomainProfile:
    """Create a sample DomainProfile for testing."""
    return DomainProfile(
        name="Test Domain",
        description="A test domain for unit testing purposes",
        thing_types=[
            ThingType(
                name="Person",
                description="A human individual",
                examples=["Alice", "Bob"],
                priority=1,
            ),
            ThingType(
                name="Organization",
                description="A company or institution",
                examples=["ACME Corp"],
                priority=2,
            ),
        ],
        connection_types=[
            ConnectionType(
                name="works_for",
                display_name="works for",
                description="Employment relationship",
                examples=[("Alice", "ACME Corp")],
            ),
        ],
        seed_entities=[
            SeedEntity(
                label="Alice",
                thing_type="Person",
                aliases=["Alice Smith"],
                description="Main protagonist",
            ),
        ],
        extraction_context="Extract entities and relationships from test content.",
        bootstrap_confidence=0.85,
        bootstrapped_from="source123",
    )


@pytest.fixture
def sample_discovery() -> Discovery:
    """Create a sample Discovery for testing."""
    return Discovery(
        discovery_type="thing_type",
        name="Document",
        display_name="Document",
        description="Official records and reports",
        examples=["Report A", "Memo B"],
        found_in_source="source456",
        occurrence_count=3,
        status=DiscoveryStatus.PENDING,
        user_question="Track Documents as a separate entity type?",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PROJECT LIFECYCLE TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestCreateProject:
    """Tests for project creation."""

    @pytest.mark.asyncio
    async def test_create_project(self, kg_service: KnowledgeGraphService) -> None:
        """Test creating a new project with a given name."""
        project = await kg_service.create_project("My Research Project")

        assert project is not None
        assert project.name == "My Research Project"
        assert isinstance(project, KGProject)

    @pytest.mark.asyncio
    async def test_create_project_generates_id(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that creating a project auto-generates a unique 12-char ID."""
        project1 = await kg_service.create_project("Project One")
        project2 = await kg_service.create_project("Project Two")

        # IDs should be 12 characters (hex from uuid4)
        assert len(project1.id) == 12
        assert len(project2.id) == 12
        # IDs should be unique
        assert project1.id != project2.id
        # IDs should be hexadecimal
        assert all(c in "0123456789abcdef" for c in project1.id)

    @pytest.mark.asyncio
    async def test_create_project_initial_state_created(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that new projects start in CREATED state."""
        project = await kg_service.create_project("New Project")

        assert project.state == ProjectState.CREATED
        assert project.domain_profile is None
        assert project.source_count == 0
        assert project.pending_discoveries == []


class TestGetProject:
    """Tests for project retrieval."""

    @pytest.mark.asyncio
    async def test_get_project_exists(self, kg_service: KnowledgeGraphService) -> None:
        """Test retrieving an existing project from cache."""
        created = await kg_service.create_project("Test Project")
        retrieved = await kg_service.get_project(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Test Project"

    @pytest.mark.asyncio
    async def test_get_project_not_found_returns_none(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that getting a non-existent project returns None."""
        result = await kg_service.get_project("000000000000")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_project_loads_from_disk(self, tmp_path: Path) -> None:
        """Test that get_project loads from disk if not in cache."""
        # Create project with first service instance
        service1 = KnowledgeGraphService(data_path=tmp_path)
        project = await service1.create_project("Persistent Project")
        project_id = project.id

        # Create new service instance (empty cache)
        service2 = KnowledgeGraphService(data_path=tmp_path)

        # Project should be loaded from disk
        loaded = await service2.get_project(project_id)

        assert loaded is not None
        assert loaded.id == project_id
        assert loaded.name == "Persistent Project"


class TestListProjects:
    """Tests for listing projects."""

    @pytest.mark.asyncio
    async def test_list_projects_empty(self, kg_service: KnowledgeGraphService) -> None:
        """Test listing projects when none exist."""
        projects = await kg_service.list_projects()

        assert projects == []

    @pytest.mark.asyncio
    async def test_list_projects_returns_all(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that list_projects returns all created projects."""
        await kg_service.create_project("Project A")
        await kg_service.create_project("Project B")
        await kg_service.create_project("Project C")

        projects = await kg_service.list_projects()

        assert len(projects) == 3
        names = {p.name for p in projects}
        assert names == {"Project A", "Project B", "Project C"}

    @pytest.mark.asyncio
    async def test_list_projects_sorted_by_created_at(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that projects are sorted by created_at, newest first."""
        # Create projects in order
        await kg_service.create_project("First")
        await kg_service.create_project("Second")
        await kg_service.create_project("Third")

        projects = await kg_service.list_projects()

        # Newest first means p3 should be first
        assert len(projects) == 3
        # Projects created later should have later created_at
        assert projects[0].created_at >= projects[1].created_at
        assert projects[1].created_at >= projects[2].created_at


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PERSISTENCE TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestPersistence:
    """Tests for project persistence."""

    @pytest.mark.asyncio
    async def test_save_project_creates_file(
        self, kg_service: KnowledgeGraphService, tmp_path: Path
    ) -> None:
        """Test that creating a project saves a JSON file to disk."""
        project = await kg_service.create_project("Saved Project")

        expected_file = tmp_path / "kg_projects" / f"{project.id}.json"
        assert expected_file.exists()

        # Verify file contents are valid JSON
        data = json.loads(expected_file.read_text(encoding="utf-8"))
        assert data["name"] == "Saved Project"
        assert data["id"] == project.id

    @pytest.mark.asyncio
    async def test_save_project_atomic_write(
        self, kg_service: KnowledgeGraphService, tmp_path: Path
    ) -> None:
        """Test that save uses atomic write pattern (temp file then rename)."""
        project = await kg_service.create_project("Atomic Test")
        project_file = tmp_path / "kg_projects" / f"{project.id}.json"

        # File should exist (atomic rename completed)
        assert project_file.exists()

        # No temp files should remain
        temp_files = list((tmp_path / "kg_projects").glob("*.tmp"))
        assert len(temp_files) == 0

    @pytest.mark.asyncio
    async def test_project_persists_across_service_instances(
        self, tmp_path: Path, sample_domain_profile: DomainProfile
    ) -> None:
        """Test that project data persists across service instances."""
        # Create and modify project with first service
        service1 = KnowledgeGraphService(data_path=tmp_path)
        project = await service1.create_project("Persistent Test")
        project_id = project.id

        # Manually set domain profile to simulate bootstrap completion
        project.domain_profile = sample_domain_profile
        project.state = ProjectState.ACTIVE
        project.source_count = 1
        await service1._save_project(project)

        # Create new service instance (simulating app restart)
        service2 = KnowledgeGraphService(data_path=tmp_path)

        # Load project and verify state persisted
        loaded = await service2.get_project(project_id)

        assert loaded is not None
        assert loaded.name == "Persistent Test"
        assert loaded.state == ProjectState.ACTIVE
        assert loaded.source_count == 1
        assert loaded.domain_profile is not None
        assert loaded.domain_profile.name == "Test Domain"
        assert len(loaded.domain_profile.thing_types) == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DISCOVERY CONFIRMATION TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestGetPendingConfirmations:
    """Tests for getting pending discovery confirmations."""

    @pytest.mark.asyncio
    async def test_get_pending_confirmations_empty(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test getting pending confirmations when none exist."""
        project = await kg_service.create_project("Empty Project")

        pending = await kg_service.get_pending_confirmations(project.id)

        assert pending == []

    @pytest.mark.asyncio
    async def test_get_pending_confirmations_returns_pending_only(
        self, kg_service: KnowledgeGraphService, sample_discovery: Discovery
    ) -> None:
        """Test that only PENDING discoveries are returned."""
        project = await kg_service.create_project("Discovery Project")

        # Add discoveries with different statuses
        pending_discovery = sample_discovery.model_copy()
        pending_discovery.status = DiscoveryStatus.PENDING

        confirmed_discovery = Discovery(
            discovery_type="connection_type",
            name="approved",
            display_name="approved",
            description="Already approved",
            status=DiscoveryStatus.CONFIRMED,
        )

        rejected_discovery = Discovery(
            discovery_type="thing_type",
            name="rejected",
            display_name="rejected",
            description="Already rejected",
            status=DiscoveryStatus.REJECTED,
        )

        project.pending_discoveries = [
            pending_discovery,
            confirmed_discovery,
            rejected_discovery,
        ]
        await kg_service._save_project(project)

        # Only pending should be returned
        pending = await kg_service.get_pending_confirmations(project.id)

        assert len(pending) == 1
        assert pending[0].status == DiscoveryStatus.PENDING
        assert pending[0].name == sample_discovery.name


class TestConfirmDiscovery:
    """Tests for confirming or rejecting discoveries."""

    @pytest.mark.asyncio
    async def test_confirm_discovery_confirmed(
        self,
        kg_service: KnowledgeGraphService,
        sample_domain_profile: DomainProfile,
        sample_discovery: Discovery,
    ) -> None:
        """Test confirming a discovery updates its status."""
        project = await kg_service.create_project("Confirm Test")
        project.domain_profile = sample_domain_profile
        project.pending_discoveries = [sample_discovery]
        await kg_service._save_project(project)

        discovery_id = sample_discovery.id
        result = await kg_service.confirm_discovery(project.id, discovery_id, True)

        assert result is True

        # Discovery should be removed from pending (it's now confirmed)
        updated_project = await kg_service.get_project(project.id)
        assert updated_project is not None
        assert len(updated_project.pending_discoveries) == 0

    @pytest.mark.asyncio
    async def test_confirm_discovery_rejected(
        self,
        kg_service: KnowledgeGraphService,
        sample_domain_profile: DomainProfile,
        sample_discovery: Discovery,
    ) -> None:
        """Test rejecting a discovery removes it from pending."""
        project = await kg_service.create_project("Reject Test")
        project.domain_profile = sample_domain_profile
        project.pending_discoveries = [sample_discovery]
        await kg_service._save_project(project)

        discovery_id = sample_discovery.id
        result = await kg_service.confirm_discovery(project.id, discovery_id, False)

        assert result is True

        # Discovery should be removed from pending
        updated_project = await kg_service.get_project(project.id)
        assert updated_project is not None
        assert len(updated_project.pending_discoveries) == 0

    @pytest.mark.asyncio
    async def test_confirm_discovery_adds_to_domain_profile(
        self,
        kg_service: KnowledgeGraphService,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """Test that confirming a discovery adds the type to domain profile."""
        project = await kg_service.create_project("Add to Profile Test")
        project.domain_profile = sample_domain_profile
        initial_thing_type_count = len(project.domain_profile.thing_types)

        # Create a discovery for a new thing type
        new_thing_discovery = Discovery(
            discovery_type="thing_type",
            name="Document",
            display_name="Document",
            description="Official records and reports",
            examples=["Report A", "Memo B"],
            found_in_source="source789",
        )
        project.pending_discoveries = [new_thing_discovery]
        await kg_service._save_project(project)

        # Confirm the discovery
        result = await kg_service.confirm_discovery(
            project.id, new_thing_discovery.id, True
        )

        assert result is True

        # Domain profile should now have the new thing type
        updated_project = await kg_service.get_project(project.id)
        assert updated_project is not None
        assert updated_project.domain_profile is not None
        assert (
            len(updated_project.domain_profile.thing_types)
            == initial_thing_type_count + 1
        )

        # Find the newly added thing type
        new_type = None
        for tt in updated_project.domain_profile.thing_types:
            if tt.name == "Document":
                new_type = tt
                break

        assert new_type is not None
        assert new_type.description == "Official records and reports"

        # Refinement tracking should be updated
        assert "source789" in updated_project.domain_profile.refined_from

    @pytest.mark.asyncio
    async def test_confirm_discovery_not_found(
        self,
        kg_service: KnowledgeGraphService,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """Test that confirming a non-existent discovery returns False."""
        project = await kg_service.create_project("Not Found Test")
        project.domain_profile = sample_domain_profile
        await kg_service._save_project(project)

        result = await kg_service.confirm_discovery(project.id, "nonexistent", True)

        assert result is False

    @pytest.mark.asyncio
    async def test_confirm_discovery_connection_type(
        self,
        kg_service: KnowledgeGraphService,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """Test that confirming a connection type discovery adds it to profile."""
        project = await kg_service.create_project("Connection Type Test")
        project.domain_profile = sample_domain_profile
        initial_connection_count = len(project.domain_profile.connection_types)

        # Create a discovery for a new connection type
        new_conn_discovery = Discovery(
            discovery_type="connection_type",
            name="supervised_by",
            display_name="supervised by",
            description="Management relationship",
            found_in_source="source101",
        )
        project.pending_discoveries = [new_conn_discovery]
        await kg_service._save_project(project)

        # Confirm the discovery
        result = await kg_service.confirm_discovery(
            project.id, new_conn_discovery.id, True
        )

        assert result is True

        # Domain profile should now have the new connection type
        updated_project = await kg_service.get_project(project.id)
        assert updated_project is not None
        assert updated_project.domain_profile is not None
        assert (
            len(updated_project.domain_profile.connection_types)
            == initial_connection_count + 1
        )

        # Find the newly added connection type
        new_conn = None
        for ct in updated_project.domain_profile.connection_types:
            if ct.name == "supervised_by":
                new_conn = ct
                break

        assert new_conn is not None
        assert new_conn.display_name == "supervised by"

    @pytest.mark.asyncio
    async def test_confirm_discovery_no_domain_profile(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that confirming discovery on project without domain profile returns False."""
        project = await kg_service.create_project("No Profile Test")
        # Project has no domain_profile (None by default)

        result = await kg_service.confirm_discovery(project.id, "any_id", True)

        assert result is False

    @pytest.mark.asyncio
    async def test_confirm_discovery_project_not_found(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that confirming discovery on non-existent project returns False."""
        result = await kg_service.confirm_discovery("000000000000", "any_id", True)

        assert result is False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BOOTSTRAP TESTS (with mocked ClaudeSDKClient)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestBootstrapFromTranscript:
    """Tests for bootstrap_from_transcript with mocked Claude client."""

    @pytest.mark.asyncio
    async def test_bootstrap_project_not_found(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that bootstrap raises ValueError for non-existent project."""
        with pytest.raises(ValueError, match="not found"):
            await kg_service.bootstrap_from_transcript(
                project_id="000000000000",
                transcript="Some transcript content",
                title="Test Video",
                source_id="source123",
            )

    @pytest.mark.asyncio
    async def test_bootstrap_updates_state_to_bootstrapping(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that bootstrap transitions project to BOOTSTRAPPING state."""
        project = await kg_service.create_project("Bootstrap Test")

        # Mock the Claude client to avoid actual API calls
        with patch("app.services.kg_service.ClaudeSDKClient") as mock_client_class:
            # Setup mock to raise immediately so we can check state change
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.query = AsyncMock()

            # Create a proper async generator for receive_response
            async def empty_async_gen():
                return
                yield  # Make this an async generator

            mock_client.receive_response = empty_async_gen
            mock_client_class.return_value = mock_client

            # Without any _bootstrap_data in messages, bootstrap will fail
            with pytest.raises(RuntimeError, match="Bootstrap produced no data"):
                await kg_service.bootstrap_from_transcript(
                    project_id=project.id,
                    transcript="Test transcript content for the video",
                    title="Test Video",
                    source_id="source123",
                )

            # After failure, state should be restored to CREATED
            restored_project = await kg_service.get_project(project.id)
            assert restored_project is not None
            assert restored_project.state == ProjectState.CREATED
            assert restored_project.error is not None

    @pytest.mark.asyncio
    async def test_bootstrap_success_creates_domain_profile(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test successful bootstrap creates a domain profile."""
        project = await kg_service.create_project("Successful Bootstrap")

        # Mock the Claude client and bootstrap data
        mock_bootstrap_data = {
            "analyze_content_domain": {
                "content_type": "documentary",
                "domain": "history",
                "topic_summary": "A documentary about historical events.",
                "key_themes": ["history", "events"],
                "complexity": "moderate",
            },
            "identify_thing_types": [
                {
                    "name": "Person",
                    "description": "A human individual",
                    "examples": ["John Doe"],
                    "icon": "👤",
                    "priority": 1,
                },
            ],
            "identify_connection_types": [
                {
                    "name": "worked_for",
                    "display_name": "worked for",
                    "description": "Employment relationship",
                    "examples": [["John", "Company"]],
                    "directional": True,
                },
            ],
            "identify_seed_entities": [
                {
                    "label": "John Doe",
                    "thing_type": "Person",
                    "aliases": [],
                    "description": "Main character",
                    "confidence": 1.0,
                },
            ],
            "generate_extraction_context": (
                "Extract entities and relationships from historical documentaries. "
                "Focus on people, organizations, and their connections."
            ),
            "finalize_domain_profile": {
                "name": "Historical Events Domain",
                "description": "A domain for tracking historical events and people.",
                "confidence": 0.85,
            },
        }

        with patch("app.services.kg_service.ClaudeSDKClient") as mock_client_class:
            # Setup mock Claude client
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.query = AsyncMock()

            # Mock receive_response to return UserMessages with ToolResultBlocks
            # and a final ResultMessage (per SDK - tool results are in UserMessage.content)
            from claude_agent_sdk import ResultMessage, UserMessage

            from app.kg.tools.bootstrap import BOOTSTRAP_DATA_MARKER

            # Create mock ToolResultBlocks inside UserMessage.content
            # (SDK sends tool results as UserMessage, simulating user providing tool results)
            def make_tool_result_block(step: str, data: Any) -> MagicMock:
                """Create a mock ToolResultBlock with embedded bootstrap data."""
                import json

                payload = {"step": step, "data": data}
                block = MagicMock()
                # Note: We check block_class == "ToolResultBlock" in the code
                block.__class__.__name__ = "ToolResultBlock"
                block.type = "tool_result"
                block.tool_use_id = f"tool_{step}"
                # Content as list of text blocks
                block.content = [
                    {"type": "text", "text": f"{step} completed"},
                    {
                        "type": "text",
                        "text": f"{BOOTSTRAP_DATA_MARKER}{json.dumps(payload)}",
                    },
                ]
                return block

            # Create UserMessages with tool results
            user_messages = []
            for step, data in mock_bootstrap_data.items():
                msg = MagicMock(spec=UserMessage)
                msg.type = "user"
                msg.content = [make_tool_result_block(step, data)]
                user_messages.append(msg)

            # Final ResultMessage (no tool_results attribute per SDK docs)
            mock_result = MagicMock(spec=ResultMessage)
            mock_result.type = "result"
            mock_result.is_error = False
            mock_result.num_turns = 5
            mock_result.total_cost_usd = 0.01

            async def mock_receive():
                # Yield UserMessages with tool results first
                for msg in user_messages:
                    yield msg
                # Then yield the final ResultMessage
                yield mock_result

            mock_client.receive_response = mock_receive
            mock_client_class.return_value = mock_client

            profile = await kg_service.bootstrap_from_transcript(
                project_id=project.id,
                transcript="Detailed transcript about historical events.",
                title="History Documentary",
                source_id="video123",
            )

        # Verify the profile was created
        assert profile is not None
        assert profile.name == "Historical Events Domain"
        assert profile.bootstrap_confidence == 0.85
        assert len(profile.thing_types) == 1
        assert len(profile.connection_types) == 1
        assert len(profile.seed_entities) == 1

        # Verify project was updated
        updated_project = await kg_service.get_project(project.id)
        assert updated_project is not None
        assert updated_project.state == ProjectState.ACTIVE
        assert updated_project.source_count == 1
        assert updated_project.domain_profile is not None

    @pytest.mark.asyncio
    async def test_bootstrap_timeout_restores_state(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that bootstrap timeout restores project to CREATED state."""
        project = await kg_service.create_project("Timeout Test")

        with patch("app.services.kg_service.ClaudeSDKClient") as mock_client_class:
            import asyncio

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.query = AsyncMock()

            # Simulate a timeout by raising TimeoutError
            async def timeout_receive():
                await asyncio.sleep(0.1)
                raise asyncio.TimeoutError("Operation timed out")
                yield  # noqa: F401 - unreachable but makes this an async generator

            mock_client.receive_response = timeout_receive
            mock_client_class.return_value = mock_client

            with pytest.raises(asyncio.TimeoutError):
                await kg_service.bootstrap_from_transcript(
                    project_id=project.id,
                    transcript="Test transcript",
                    title="Test Video",
                    source_id="source123",
                )

            # Project state should be restored to CREATED
            restored_project = await kg_service.get_project(project.id)
            assert restored_project is not None
            assert restored_project.state == ProjectState.CREATED
            assert restored_project.error is not None
            assert "timed out" in restored_project.error.lower()

    @pytest.mark.asyncio
    async def test_bootstrap_concurrent_attempts_blocked(
        self, kg_service: KnowledgeGraphService
    ) -> None:
        """Test that concurrent bootstrap attempts on same project are blocked."""
        project = await kg_service.create_project("Concurrent Test")

        # Manually set project to BOOTSTRAPPING to simulate in-progress bootstrap
        project.state = ProjectState.BOOTSTRAPPING
        await kg_service._save_project(project)

        # Attempt bootstrap should fail because project is already bootstrapping
        with pytest.raises(ValueError, match="already bootstrapping|not in CREATED"):
            await kg_service.bootstrap_from_transcript(
                project_id=project.id,
                transcript="Test transcript",
                title="Test Video",
                source_id="source123",
            )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MALFORMED TOOL RESPONSE TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestExtractMarkedContent:
    """Tests for _extract_marked_content robustness with malformed responses."""

    def test_extract_none_content_returns_none(self) -> None:
        """Test that None content returns None gracefully."""
        from app.services.kg_service import _extract_marked_content

        result = _extract_marked_content(None, "__TEST_MARKER__:")
        assert result is None

    def test_extract_empty_string_returns_none(self) -> None:
        """Test that empty string returns None."""
        from app.services.kg_service import _extract_marked_content

        result = _extract_marked_content("", "__TEST_MARKER__:")
        assert result is None

    def test_extract_invalid_json_returns_none(self) -> None:
        """Test that invalid JSON after marker returns None (doesn't crash)."""
        from app.services.kg_service import _extract_marked_content

        # Valid marker but invalid JSON
        result = _extract_marked_content(
            "__TEST_MARKER__:this is not valid json{", "__TEST_MARKER__:"
        )
        assert result is None

    def test_extract_truncated_json_returns_none(self) -> None:
        """Test that truncated JSON returns None."""
        from app.services.kg_service import _extract_marked_content

        # JSON cut off mid-way
        result = _extract_marked_content(
            '__TEST_MARKER__:{"key": "value", "incomplete', "__TEST_MARKER__:"
        )
        assert result is None

    def test_extract_wrong_marker_returns_none(self) -> None:
        """Test that content with different marker returns None."""
        from app.services.kg_service import _extract_marked_content

        result = _extract_marked_content(
            '__OTHER_MARKER__:{"data": true}', "__TEST_MARKER__:"
        )
        assert result is None

    def test_extract_valid_string_content(self) -> None:
        """Test extraction from valid string content."""
        from app.services.kg_service import _extract_marked_content

        result = _extract_marked_content(
            '__TEST_MARKER__:{"step": "test", "data": {"value": 42}}',
            "__TEST_MARKER__:",
        )
        assert result is not None
        assert result["step"] == "test"
        assert result["data"]["value"] == 42

    def test_extract_from_list_content(self) -> None:
        """Test extraction from list of content blocks."""
        from app.services.kg_service import _extract_marked_content

        content = [
            {"type": "text", "text": "Some intro text"},
            {"type": "text", "text": '__TEST_MARKER__:{"found": true}'},
        ]
        result = _extract_marked_content(content, "__TEST_MARKER__:")
        assert result is not None
        assert result["found"] is True

    def test_extract_from_list_no_match(self) -> None:
        """Test that list without matching marker returns None."""
        from app.services.kg_service import _extract_marked_content

        content = [
            {"type": "text", "text": "Some text without marker"},
            {"type": "image", "url": "http://example.com/img.png"},
        ]
        result = _extract_marked_content(content, "__TEST_MARKER__:")
        assert result is None

    def test_extract_unexpected_type_returns_none(self) -> None:
        """Test that unexpected content type returns None."""
        from app.services.kg_service import _extract_marked_content

        # Pass an integer - should not crash
        result = _extract_marked_content(42, "__TEST_MARKER__:")  # type: ignore
        assert result is None

    def test_extract_from_object_with_text_attr(self) -> None:
        """Test extraction from object with type/text attributes."""
        from app.services.kg_service import _extract_marked_content

        class MockBlock:
            type = "text"
            text = '__TEST_MARKER__:{"extracted": "from_object"}'

        content = [MockBlock()]
        result = _extract_marked_content(content, "__TEST_MARKER__:")
        assert result is not None
        assert result["extracted"] == "from_object"

    def test_extract_nested_json(self) -> None:
        """Test extraction of deeply nested JSON."""
        from app.services.kg_service import _extract_marked_content

        nested_data = {
            "level1": {
                "level2": {
                    "level3": {"items": [1, 2, 3], "nested_str": "deeply nested"}
                }
            }
        }
        import json

        content = f"__TEST_MARKER__:{json.dumps(nested_data)}"
        result = _extract_marked_content(content, "__TEST_MARKER__:")
        assert result is not None
        assert result["level1"]["level2"]["level3"]["nested_str"] == "deeply nested"
