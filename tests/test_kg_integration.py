"""
End-to-end integration tests for Knowledge Graph system.

This module tests complete workflows across multiple components:
- Full bootstrap flow (project creation → Claude analysis → DomainProfile)
- Discovery confirmation flow (pending discovery → user decision → profile update)
- Persistence across service restarts

Unlike unit tests that mock internal components, these tests verify
the system works correctly when components are integrated together.

Uses tmp_path fixture for isolated test directories.
All tests are async using @pytest.mark.asyncio.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.kg.domain import (
    ConnectionType,
    Discovery,
    DiscoveryStatus,
    DomainProfile,
    ProjectState,
    SeedEntity,
    ThingType,
)
from app.services.kg_service import KnowledgeGraphService


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIXTURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.fixture
def sample_transcript() -> str:
    """
    Realistic transcript content for bootstrap testing.

    Contains diverse content that exercises all bootstrap steps:
    - Domain/content type identification
    - Multiple entity types (Person, Organization, Project, Document)
    - Multiple relationship types (worked_for, funded_by, authorized)
    - Key entities with aliases
    """
    return """
    MKUltra: The CIA's Secret Mind Control Program

    This documentary examines the Central Intelligence Agency's covert program
    known as MKUltra, which ran from 1953 to 1973. The program was authorized
    by CIA Director Allen Dulles and operated under the leadership of Sidney Gottlieb,
    head of the Technical Services Staff.

    MKUltra involved numerous subprojects, over 150 in total, many conducted at
    universities and research institutions across the United States. Notable institutions
    include Stanford Research Institute, McGill University where Dr. Donald Cameron
    conducted controversial experiments, and the University of Oklahoma.

    Key documents from the Church Committee hearings in 1975 revealed the extent
    of the program. Senator Frank Church led these congressional investigations
    that exposed CIA abuses.

    The program used various methods including LSD experiments, hypnosis,
    sensory deprivation, and psychological manipulation. Test subjects included
    unwitting citizens, prisoners, and mental patients.

    Funding flowed through front organizations like the Society for Investigation
    of Human Ecology. The Ford Foundation and Rockefeller Foundation were also
    implicated in indirect funding.

    Dr. Sidney Gottlieb, sometimes called the "Black Sorcerer," destroyed many
    MKUltra files in 1973. However, financial records survived due to separate
    record-keeping, leading to public exposure in 1977.
    """


@pytest.fixture
def mock_bootstrap_results() -> dict[str, Any]:
    """
    Pre-defined bootstrap tool outputs that simulate Claude's analysis.

    These results match the structure returned by bootstrap tools and are
    used to populate the bootstrap collector, bypassing actual Claude API calls.
    """
    return {
        "analyze_content_domain": {
            "content_type": "documentary",
            "domain": "history",
            "topic_summary": (
                "A documentary examining the CIA's MKUltra program, a covert "
                "mind control research initiative that operated from 1953 to 1973."
            ),
            "key_themes": [
                "government secrecy",
                "human experimentation",
                "intelligence operations",
                "congressional oversight",
            ],
            "complexity": "complex",
        },
        "identify_thing_types": [
            {
                "name": "Person",
                "description": "Individuals involved in or affected by MKUltra",
                "examples": ["Sidney Gottlieb", "Allen Dulles", "Frank Church"],
                "icon": "👤",
                "priority": 1,
            },
            {
                "name": "Organization",
                "description": "Government agencies, universities, and foundations",
                "examples": ["CIA", "Stanford Research Institute", "Ford Foundation"],
                "icon": "🏢",
                "priority": 1,
            },
            {
                "name": "Project",
                "description": "Research programs and subprojects",
                "examples": ["MKUltra", "Subproject 68"],
                "icon": "📋",
                "priority": 2,
            },
            {
                "name": "Document",
                "description": "Official reports, hearings, and records",
                "examples": ["Church Committee Report", "MKUltra files"],
                "icon": "📄",
                "priority": 2,
            },
        ],
        "identify_connection_types": [
            {
                "name": "worked_for",
                "display_name": "worked for",
                "description": "Employment or operational relationship",
                "examples": [["Sidney Gottlieb", "CIA"]],
                "directional": True,
            },
            {
                "name": "authorized",
                "display_name": "authorized",
                "description": "Official approval relationship",
                "examples": [["Allen Dulles", "MKUltra"]],
                "directional": True,
            },
            {
                "name": "funded_by",
                "display_name": "funded by",
                "description": "Financial support relationship",
                "examples": [["MKUltra", "CIA"]],
                "directional": True,
            },
            {
                "name": "investigated",
                "display_name": "investigated",
                "description": "Oversight or inquiry relationship",
                "examples": [["Church Committee", "MKUltra"]],
                "directional": True,
            },
            {
                "name": "conducted_at",
                "display_name": "conducted at",
                "description": "Location where activity occurred",
                "examples": [["Subproject 68", "McGill University"]],
                "directional": True,
            },
        ],
        "identify_seed_entities": [
            {
                "label": "CIA",
                "thing_type": "Organization",
                "aliases": ["Central Intelligence Agency", "The Agency", "Langley"],
                "description": "United States intelligence agency that operated MKUltra",
                "confidence": 1.0,
            },
            {
                "label": "MKUltra",
                "thing_type": "Project",
                "aliases": ["Project MKUltra", "MK-Ultra", "MKULTRA"],
                "description": "CIA mind control research program (1953-1973)",
                "confidence": 1.0,
            },
            {
                "label": "Sidney Gottlieb",
                "thing_type": "Person",
                "aliases": ["Black Sorcerer", "Dr. Gottlieb"],
                "description": "Head of CIA Technical Services Staff, led MKUltra",
                "confidence": 1.0,
            },
            {
                "label": "Allen Dulles",
                "thing_type": "Person",
                "aliases": [],
                "description": "CIA Director who authorized MKUltra",
                "confidence": 1.0,
            },
            {
                "label": "Church Committee",
                "thing_type": "Organization",
                "aliases": ["Senate Select Committee"],
                "description": "Congressional committee that investigated CIA",
                "confidence": 1.0,
            },
        ],
        "generate_extraction_context": (
            "This domain covers the CIA's MKUltra mind control program. "
            "Key terminology: 'The Agency' refers to the CIA, 'TSS' refers to "
            "Technical Services Staff, 'subproject' refers to numbered programs "
            "under MKUltra. When extracting entities, prefer canonical names: "
            "'CIA' not 'Central Intelligence Agency', 'MKUltra' not 'MK-Ultra'. "
            "Watch for: researchers, institutions, government officials, documents, "
            "and funding relationships. Time period: primarily 1950s-1970s."
        ),
        "finalize_domain_profile": {
            "name": "CIA Mind Control Research",
            "description": (
                "Knowledge graph tracking the CIA's MKUltra program, related "
                "subprojects, key personnel, institutions, and oversight investigations. "
                "Covers government secrecy, human experimentation, and congressional inquiries."
            ),
            "confidence": 0.88,
        },
    }


@pytest.fixture
def sample_domain_profile() -> DomainProfile:
    """Create a sample DomainProfile for testing discovery workflows."""
    return DomainProfile(
        name="CIA Mind Control Research",
        description="Knowledge graph for MKUltra and related programs",
        thing_types=[
            ThingType(
                name="Person",
                description="Individuals involved in MKUltra",
                examples=["Sidney Gottlieb"],
                priority=1,
            ),
            ThingType(
                name="Organization",
                description="Agencies and institutions",
                examples=["CIA"],
                priority=1,
            ),
        ],
        connection_types=[
            ConnectionType(
                name="worked_for",
                display_name="worked for",
                description="Employment relationship",
                examples=[("Sidney Gottlieb", "CIA")],
            ),
        ],
        seed_entities=[
            SeedEntity(
                label="CIA",
                thing_type="Organization",
                aliases=["Central Intelligence Agency"],
                description="United States intelligence agency",
            ),
        ],
        extraction_context="Extract entities from MKUltra-related content.",
        bootstrap_confidence=0.85,
        bootstrapped_from="source123",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FULL BOOTSTRAP FLOW TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestFullBootstrapFlow:
    """
    End-to-end tests for the complete bootstrap workflow.

    Tests verify that:
    1. Project is created in CREATED state
    2. Bootstrap transitions project through BOOTSTRAPPING → ACTIVE
    3. DomainProfile is correctly constructed from tool results
    4. All bootstrap data (thing_types, connection_types, etc.) is populated
    """

    @pytest.mark.asyncio
    async def test_full_bootstrap_flow(
        self,
        tmp_path: Path,
        sample_transcript: str,
        mock_bootstrap_results: dict[str, Any],
    ) -> None:
        """
        Test complete bootstrap flow from project creation to active state.

        Mocks ClaudeSDKClient to simulate agent execution, then populates
        the bootstrap collector with pre-defined results. Verifies the
        service correctly transforms these into a DomainProfile.
        """
        # Create service with isolated directory
        service = KnowledgeGraphService(data_path=tmp_path)

        # Step 1: Create project
        project = await service.create_project("MKUltra Research")
        assert project.state == ProjectState.CREATED
        assert project.domain_profile is None

        # Step 2: Mock Claude client to bypass actual API calls
        with patch("app.services.kg_service.ClaudeSDKClient") as mock_client_class:
            # Setup mock to yield a successful ResultMessage
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.query = AsyncMock()

            # Per SDK docs - tool results are in UserMessage.content as ToolResultBlock
            from claude_agent_sdk import ResultMessage, UserMessage

            from app.kg.tools.bootstrap import BOOTSTRAP_DATA_MARKER

            # Create mock ToolResultBlocks inside UserMessage.content
            # (SDK sends tool results as UserMessage, simulating user providing results)
            def make_tool_result_block(step: str, data: Any) -> MagicMock:
                payload = {"step": step, "data": data}
                block = MagicMock()
                block.__class__.__name__ = "ToolResultBlock"
                block.type = "tool_result"
                block.tool_use_id = f"tool_{step}"
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
            for step, data in mock_bootstrap_results.items():
                msg = MagicMock(spec=UserMessage)
                msg.type = "user"
                msg.content = [make_tool_result_block(step, data)]
                user_messages.append(msg)

            # Final ResultMessage
            mock_result = MagicMock(spec=ResultMessage)
            mock_result.type = "result"
            mock_result.is_error = False
            mock_result.num_turns = 6
            mock_result.total_cost_usd = 0.02

            async def mock_receive():
                for msg in user_messages:
                    yield msg
                yield mock_result

            mock_client.receive_response = mock_receive
            mock_client_class.return_value = mock_client

            # Step 3: Run bootstrap
            profile = await service.bootstrap_from_transcript(
                project_id=project.id,
                transcript=sample_transcript,
                title="MKUltra Documentary",
                source_id="video_mkultra_001",
            )

        # Step 4: Verify DomainProfile was created correctly
        assert profile is not None
        assert profile.name == "CIA Mind Control Research"
        assert profile.bootstrap_confidence == 0.88
        assert profile.bootstrapped_from == "video_mkultra_001"

        # Verify thing_types populated
        assert len(profile.thing_types) == 4
        thing_type_names = {t.name for t in profile.thing_types}
        assert thing_type_names == {"Person", "Organization", "Project", "Document"}

        # Verify connection_types populated
        assert len(profile.connection_types) == 5
        connection_names = {c.name for c in profile.connection_types}
        assert "worked_for" in connection_names
        assert "funded_by" in connection_names

        # Verify seed_entities populated
        assert len(profile.seed_entities) == 5
        seed_labels = {e.label for e in profile.seed_entities}
        assert "CIA" in seed_labels
        assert "MKUltra" in seed_labels

        # Verify extraction_context
        assert "CIA" in profile.extraction_context
        assert "MKUltra" in profile.extraction_context

        # Step 5: Verify project state is ACTIVE
        updated_project = await service.get_project(project.id)
        assert updated_project is not None
        assert updated_project.state == ProjectState.ACTIVE
        assert updated_project.source_count == 1
        assert updated_project.domain_profile is not None
        assert updated_project.error is None

    @pytest.mark.asyncio
    async def test_bootstrap_restores_state_on_failure(
        self,
        tmp_path: Path,
        sample_transcript: str,
    ) -> None:
        """
        Test that bootstrap failure restores project to CREATED state.

        When bootstrap fails (e.g., empty tool results), the project
        should be reverted to CREATED state with an error message.
        """
        service = KnowledgeGraphService(data_path=tmp_path)
        project = await service.create_project("Failed Bootstrap Test")

        with patch("app.services.kg_service.ClaudeSDKClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.query = AsyncMock()

            async def empty_async_gen():
                return
                yield  # Make this an async generator

            mock_client.receive_response = empty_async_gen
            mock_client_class.return_value = mock_client

            # Without any _bootstrap_data in messages, bootstrap will fail
            with pytest.raises(RuntimeError, match="Bootstrap produced no data"):
                await service.bootstrap_from_transcript(
                    project_id=project.id,
                    transcript=sample_transcript,
                    title="Test Video",
                    source_id="source123",
                )

        # Verify project reverted to CREATED with error
        restored = await service.get_project(project.id)
        assert restored is not None
        assert restored.state == ProjectState.CREATED
        assert restored.error is not None
        assert "no data" in restored.error.lower()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DISCOVERY CONFIRMATION FLOW TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestDiscoveryConfirmationFlow:
    """
    End-to-end tests for discovery confirmation workflow.

    When new entity/relationship types are discovered during extraction,
    they are added to pending_discoveries. Users can confirm (add to profile)
    or reject (discard) them.
    """

    @pytest.mark.asyncio
    async def test_discovery_confirmation_flow(
        self,
        tmp_path: Path,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """
        Test complete discovery confirmation flow.

        Steps:
        1. Create project with domain profile
        2. Add pending discovery
        3. Confirm discovery
        4. Verify added to domain profile
        5. Verify removed from pending
        """
        service = KnowledgeGraphService(data_path=tmp_path)

        # Step 1: Create project with domain profile
        project = await service.create_project("Discovery Test")
        project.domain_profile = sample_domain_profile
        project.state = ProjectState.ACTIVE
        await service._save_project(project)

        initial_thing_type_count = len(project.domain_profile.thing_types)

        # Step 2: Add pending discovery (simulates extraction finding new type)
        new_discovery = Discovery(
            discovery_type="thing_type",
            name="Subproject",
            display_name="Subproject",
            description="Numbered research subproject under MKUltra",
            examples=["Subproject 68", "Subproject 54"],
            found_in_source="video_002",
            occurrence_count=12,
            status=DiscoveryStatus.PENDING,
            user_question="Track Subprojects as a separate entity type?",
        )
        project.pending_discoveries = [new_discovery]
        await service._save_project(project)

        # Verify pending confirmations
        pending = await service.get_pending_confirmations(project.id)
        assert len(pending) == 1
        assert pending[0].name == "Subproject"

        # Step 3: Confirm discovery
        result = await service.confirm_discovery(
            project.id, new_discovery.id, confirmed=True
        )
        assert result is True

        # Step 4: Verify added to domain profile
        updated = await service.get_project(project.id)
        assert updated is not None
        assert updated.domain_profile is not None
        assert len(updated.domain_profile.thing_types) == initial_thing_type_count + 1

        # Find the new thing type
        new_type = None
        for tt in updated.domain_profile.thing_types:
            if tt.name == "Subproject":
                new_type = tt
                break

        assert new_type is not None
        assert new_type.description == "Numbered research subproject under MKUltra"
        assert "Subproject 68" in new_type.examples

        # Verify refinement tracking
        assert "video_002" in updated.domain_profile.refined_from
        assert updated.domain_profile.refinement_count >= 1

        # Step 5: Verify removed from pending
        assert len(updated.pending_discoveries) == 0

    @pytest.mark.asyncio
    async def test_discovery_rejection_flow(
        self,
        tmp_path: Path,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """
        Test that rejecting a discovery removes it without adding to profile.
        """
        service = KnowledgeGraphService(data_path=tmp_path)

        project = await service.create_project("Rejection Test")
        project.domain_profile = sample_domain_profile
        project.state = ProjectState.ACTIVE

        initial_thing_type_count = len(project.domain_profile.thing_types)

        # Add discovery to reject
        discovery_to_reject = Discovery(
            discovery_type="thing_type",
            name="Experiment",
            display_name="Experiment",
            description="Individual experiments conducted",
            status=DiscoveryStatus.PENDING,
        )
        project.pending_discoveries = [discovery_to_reject]
        await service._save_project(project)

        # Reject the discovery
        result = await service.confirm_discovery(
            project.id, discovery_to_reject.id, confirmed=False
        )
        assert result is True

        # Verify NOT added to profile
        updated = await service.get_project(project.id)
        assert updated is not None
        assert updated.domain_profile is not None
        assert len(updated.domain_profile.thing_types) == initial_thing_type_count

        # Verify removed from pending
        assert len(updated.pending_discoveries) == 0

    @pytest.mark.asyncio
    async def test_connection_type_discovery_confirmation(
        self,
        tmp_path: Path,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """
        Test confirming a connection_type discovery adds it to profile.
        """
        service = KnowledgeGraphService(data_path=tmp_path)

        project = await service.create_project("Connection Discovery Test")
        project.domain_profile = sample_domain_profile
        project.state = ProjectState.ACTIVE

        initial_conn_count = len(project.domain_profile.connection_types)

        # Add connection type discovery
        conn_discovery = Discovery(
            discovery_type="connection_type",
            name="supervised",
            display_name="supervised",
            description="Management or oversight relationship",
            found_in_source="video_003",
            status=DiscoveryStatus.PENDING,
        )
        project.pending_discoveries = [conn_discovery]
        await service._save_project(project)

        # Confirm the discovery
        result = await service.confirm_discovery(
            project.id, conn_discovery.id, confirmed=True
        )
        assert result is True

        # Verify connection type added
        updated = await service.get_project(project.id)
        assert updated is not None
        assert updated.domain_profile is not None
        assert len(updated.domain_profile.connection_types) == initial_conn_count + 1

        # Find the new connection type
        new_conn = None
        for ct in updated.domain_profile.connection_types:
            if ct.name == "supervised":
                new_conn = ct
                break

        assert new_conn is not None
        assert new_conn.display_name == "supervised"

    @pytest.mark.asyncio
    async def test_multiple_pending_discoveries(
        self,
        tmp_path: Path,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """
        Test handling multiple pending discoveries with mixed decisions.
        """
        service = KnowledgeGraphService(data_path=tmp_path)

        project = await service.create_project("Multiple Discoveries Test")
        project.domain_profile = sample_domain_profile
        project.state = ProjectState.ACTIVE

        # Add multiple discoveries
        discovery1 = Discovery(
            discovery_type="thing_type",
            name="Document",
            display_name="Document",
            description="Official documents and reports",
            status=DiscoveryStatus.PENDING,
        )
        discovery2 = Discovery(
            discovery_type="thing_type",
            name="Location",
            display_name="Location",
            description="Geographic locations",
            status=DiscoveryStatus.PENDING,
        )
        discovery3 = Discovery(
            discovery_type="connection_type",
            name="mentioned_in",
            display_name="mentioned in",
            description="Reference in a document",
            status=DiscoveryStatus.PENDING,
        )

        project.pending_discoveries = [discovery1, discovery2, discovery3]
        await service._save_project(project)

        # Get pending - should show all 3
        pending = await service.get_pending_confirmations(project.id)
        assert len(pending) == 3

        # Confirm first discovery
        await service.confirm_discovery(project.id, discovery1.id, True)

        # Reject second discovery
        await service.confirm_discovery(project.id, discovery2.id, False)

        # One should remain pending
        pending = await service.get_pending_confirmations(project.id)
        assert len(pending) == 1
        assert pending[0].name == "mentioned_in"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PERSISTENCE FLOW TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestPersistenceFlow:
    """
    Tests for data persistence across service restarts.

    Verifies that project data survives when a new KnowledgeGraphService
    instance is created (simulating app restart).
    """

    @pytest.mark.asyncio
    async def test_project_persistence_across_restarts(
        self,
        tmp_path: Path,
        mock_bootstrap_results: dict[str, Any],
    ) -> None:
        """
        Test that all project data survives service restart.

        Steps:
        1. Create service instance #1
        2. Create project and complete bootstrap
        3. Create service instance #2 (simulates restart)
        4. Load project and verify all data intact
        """
        # Step 1: Create first service instance
        service1 = KnowledgeGraphService(data_path=tmp_path)

        # Step 2: Create project
        project = await service1.create_project("Persistence Test")
        project_id = project.id

        # Bootstrap the project (mocked)
        with patch("app.services.kg_service.ClaudeSDKClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.query = AsyncMock()

            # Per SDK docs - tool results are in UserMessage.content as ToolResultBlock
            from claude_agent_sdk import ResultMessage, UserMessage

            from app.kg.tools.bootstrap import BOOTSTRAP_DATA_MARKER

            def make_tool_result_block(step: str, data: Any) -> MagicMock:
                payload = {"step": step, "data": data}
                block = MagicMock()
                block.__class__.__name__ = "ToolResultBlock"
                block.type = "tool_result"
                block.tool_use_id = f"tool_{step}"
                block.content = [
                    {"type": "text", "text": f"{step} completed"},
                    {
                        "type": "text",
                        "text": f"{BOOTSTRAP_DATA_MARKER}{json.dumps(payload)}",
                    },
                ]
                return block

            user_messages = []
            for step, data in mock_bootstrap_results.items():
                msg = MagicMock(spec=UserMessage)
                msg.type = "user"
                msg.content = [make_tool_result_block(step, data)]
                user_messages.append(msg)

            mock_result = MagicMock(spec=ResultMessage)
            mock_result.type = "result"
            mock_result.is_error = False
            mock_result.num_turns = 6
            mock_result.total_cost_usd = 0.02

            async def mock_receive():
                for msg in user_messages:
                    yield msg
                yield mock_result

            mock_client.receive_response = mock_receive
            mock_client_class.return_value = mock_client

            await service1.bootstrap_from_transcript(
                project_id=project_id,
                transcript="Test transcript content",
                title="Test Video",
                source_id="video_persist_001",
            )

        # Verify state before "restart"
        pre_restart = await service1.get_project(project_id)
        assert pre_restart is not None
        assert pre_restart.state == ProjectState.ACTIVE
        assert pre_restart.domain_profile is not None

        # Record values to verify later
        pre_profile_name = pre_restart.domain_profile.name
        pre_thing_type_count = len(pre_restart.domain_profile.thing_types)
        pre_connection_type_count = len(pre_restart.domain_profile.connection_types)
        pre_seed_entity_count = len(pre_restart.domain_profile.seed_entities)
        pre_confidence = pre_restart.domain_profile.bootstrap_confidence

        # Step 3: Create NEW service instance (simulates app restart)
        # This creates a fresh in-memory cache
        service2 = KnowledgeGraphService(data_path=tmp_path)

        # Step 4: Load project from new instance
        loaded = await service2.get_project(project_id)

        # Verify all data intact
        assert loaded is not None
        assert loaded.id == project_id
        assert loaded.name == "Persistence Test"
        assert loaded.state == ProjectState.ACTIVE
        assert loaded.source_count == 1

        # Verify domain profile
        assert loaded.domain_profile is not None
        assert loaded.domain_profile.name == pre_profile_name
        assert loaded.domain_profile.bootstrap_confidence == pre_confidence
        assert loaded.domain_profile.bootstrapped_from == "video_persist_001"

        # Verify nested collections persisted
        assert len(loaded.domain_profile.thing_types) == pre_thing_type_count
        assert len(loaded.domain_profile.connection_types) == pre_connection_type_count
        assert len(loaded.domain_profile.seed_entities) == pre_seed_entity_count

        # Verify specific thing type data
        person_type = next(
            (t for t in loaded.domain_profile.thing_types if t.name == "Person"),
            None,
        )
        assert person_type is not None
        assert "Sidney Gottlieb" in person_type.examples

    @pytest.mark.asyncio
    async def test_pending_discoveries_persist(
        self,
        tmp_path: Path,
        sample_domain_profile: DomainProfile,
    ) -> None:
        """
        Test that pending discoveries survive service restart.
        """
        # Create service and project
        service1 = KnowledgeGraphService(data_path=tmp_path)
        project = await service1.create_project("Discovery Persistence Test")
        project_id = project.id
        project.domain_profile = sample_domain_profile
        project.state = ProjectState.ACTIVE

        # Add pending discovery
        discovery = Discovery(
            discovery_type="thing_type",
            name="TestType",
            display_name="Test Type",
            description="A type for testing persistence",
            status=DiscoveryStatus.PENDING,
            found_in_source="test_source",
            occurrence_count=5,
        )
        project.pending_discoveries = [discovery]
        discovery_id = discovery.id
        await service1._save_project(project)

        # Create new service instance
        service2 = KnowledgeGraphService(data_path=tmp_path)

        # Load and verify
        loaded = await service2.get_project(project_id)
        assert loaded is not None
        assert len(loaded.pending_discoveries) == 1
        assert loaded.pending_discoveries[0].id == discovery_id
        assert loaded.pending_discoveries[0].name == "TestType"
        assert loaded.pending_discoveries[0].status == DiscoveryStatus.PENDING
        assert loaded.pending_discoveries[0].occurrence_count == 5

    @pytest.mark.asyncio
    async def test_list_projects_after_restart(
        self,
        tmp_path: Path,
    ) -> None:
        """
        Test that list_projects returns all projects after restart.
        """
        # Create service and multiple projects
        service1 = KnowledgeGraphService(data_path=tmp_path)

        await service1.create_project("Project Alpha")
        await service1.create_project("Project Beta")
        await service1.create_project("Project Gamma")

        # Verify all listed
        projects = await service1.list_projects()
        assert len(projects) == 3

        # Create new service (restart)
        service2 = KnowledgeGraphService(data_path=tmp_path)

        # List should return all projects from disk
        loaded_projects = await service2.list_projects()
        assert len(loaded_projects) == 3

        loaded_names = {p.name for p in loaded_projects}
        assert loaded_names == {"Project Alpha", "Project Beta", "Project Gamma"}

    @pytest.mark.asyncio
    async def test_no_temp_files_remain_after_save(
        self,
        tmp_path: Path,
    ) -> None:
        """
        Test that atomic write pattern leaves no temp files.

        The service uses write-to-temp-then-rename for safety.
        No .tmp files should remain after successful operations.
        """
        service = KnowledgeGraphService(data_path=tmp_path)

        # Create and save several projects
        for i in range(5):
            await service.create_project(f"Atomic Test {i}")

        # Check for temp files
        projects_dir = tmp_path / "kg_projects"
        temp_files = list(projects_dir.glob("*.tmp"))
        assert len(temp_files) == 0

        # Check correct number of JSON files exist
        json_files = list(projects_dir.glob("*.json"))
        assert len(json_files) == 5

    @pytest.mark.asyncio
    async def test_connection_type_examples_persist_as_tuples(
        self,
        tmp_path: Path,
    ) -> None:
        """
        Test that ConnectionType examples (tuples) serialize/deserialize correctly.

        Pydantic serializes tuples as lists in JSON. The model must handle
        this conversion on load.
        """
        service1 = KnowledgeGraphService(data_path=tmp_path)
        project = await service1.create_project("Tuple Test")
        project.domain_profile = DomainProfile(
            name="Test Domain",
            description="Testing tuple persistence",
            connection_types=[
                ConnectionType(
                    name="relates_to",
                    display_name="relates to",
                    description="General relationship",
                    examples=[("Entity A", "Entity B"), ("Entity C", "Entity D")],
                ),
            ],
        )
        project.state = ProjectState.ACTIVE
        await service1._save_project(project)

        # Restart and load
        service2 = KnowledgeGraphService(data_path=tmp_path)
        loaded = await service2.get_project(project.id)

        assert loaded is not None
        assert loaded.domain_profile is not None
        assert len(loaded.domain_profile.connection_types) == 1

        examples = loaded.domain_profile.connection_types[0].examples
        assert len(examples) == 2
        # Examples should be accessible as tuples
        assert examples[0] == ("Entity A", "Entity B")
