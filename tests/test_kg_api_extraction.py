"""
API Tests for Knowledge Graph Extraction & Query Endpoints.

Tests the KG API endpoints using httpx AsyncClient with mocked
KnowledgeGraphService. Uses FastAPI's dependency_overrides for
proper dependency injection testing (not patch()).

Covered endpoints:
- POST /kg/projects/{project_id}/extract
- GET /kg/projects/{project_id}/graph
- POST /kg/projects/{project_id}/export
- GET /kg/projects/{project_id}/nodes
- GET /kg/projects/{project_id}/nodes/{node_id}/neighbors
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.kg.domain import DomainProfile, KGProject, ProjectState, ThingType
from app.kg.knowledge_base import KnowledgeBase
from app.kg.models import Node


class MockKnowledgeGraphService:
    """Mock KnowledgeGraphService for testing."""

    def __init__(
        self,
        project: KGProject | None = None,
        kb: KnowledgeBase | None = None,
    ) -> None:
        self.project = project
        self.kb = kb
        self.kb_path = Path("/mock/kb")

        # Track method calls
        self.extract_called = False
        self.export_called = False

    async def get_project(self, project_id: str) -> KGProject | None:
        """Return the mock project if ID matches."""
        if self.project and self.project.id == project_id:
            return self.project
        return None

    async def extract_from_transcript(
        self,
        project_id: str,
        transcript: str,
        title: str,
        source_id: str,
    ) -> dict[str, Any]:
        """Mock extraction - tracks that it was called."""
        self.extract_called = True
        return {
            "entities_extracted": 5,
            "relationships_extracted": 3,
            "discoveries": 1,
            "summary": "Test extraction summary",
        }

    async def get_graph_stats(self, project_id: str) -> dict[str, Any] | None:
        """Return mock stats if KB exists."""
        if self.kb:
            return self.kb.stats()
        return None

    async def export_graph(
        self,
        project_id: str,
        format: str = "graphml",
    ) -> Path | None:
        """Mock export - returns a fake path."""
        if not self.project or not self.project.kb_id:
            return None
        self.export_called = True
        return Path(f"/mock/exports/{project_id}.{format}")


def _create_test_project(
    project_id: str = "testproj1234",
    name: str = "Test Project",
    state: ProjectState = ProjectState.ACTIVE,
    with_profile: bool = True,
    kb_id: str | None = "testkb123456",
) -> KGProject:
    """Create a test project with optional domain profile."""
    profile = None
    if with_profile:
        profile = DomainProfile(
            name="Test Domain",
            description="Domain for testing",
            thing_types=[
                ThingType(name="Person", description="A person", examples=["Alice"]),
                ThingType(name="Organization", description="An org", examples=["CIA"]),
            ],
            connection_types=[],
            seed_entities=[],
        )

    return KGProject(
        id=project_id,
        name=name,
        state=state,
        domain_profile=profile,
        kb_id=kb_id,
        source_count=1 if with_profile else 0,
        thing_count=10 if with_profile else 0,
        connection_count=5 if with_profile else 0,
    )


def _create_test_kb(kb_id: str = "testkb123456") -> KnowledgeBase:
    """Create a test knowledge base with some nodes and edges."""
    kb = KnowledgeBase(id=kb_id, name="Test KB")

    # Add some test nodes
    alice = Node(id="node_alice12", label="Alice", entity_type="Person")
    bob = Node(id="node_bob1234", label="Bob", entity_type="Person")
    cia = Node(id="node_cia1234", label="CIA", entity_type="Organization")

    kb.add_node(alice)
    kb.add_node(bob)
    kb.add_node(cia)

    # Add relationships
    kb.add_relationship(
        source_label="Alice",
        target_label="CIA",
        relationship_type="worked_for",
        source_id="source_001",
    )
    kb.add_relationship(
        source_label="Bob",
        target_label="Alice",
        relationship_type="knows",
        source_id="source_001",
    )

    return kb


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: POST /kg/projects/{project_id}/extract
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_extract_endpoint_success() -> None:
    """Test successful extraction request returns extracting status."""
    from app.api.deps import get_kg_service
    from app.main import app

    project_id = "testproj1234"
    project = _create_test_project(project_id=project_id)
    mock_service = MockKnowledgeGraphService(project=project)

    app.dependency_overrides[get_kg_service] = lambda: mock_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/kg/projects/{project_id}/extract",
                json={
                    "transcript": "This is a test transcript about Alice at CIA.",
                    "title": "Test Video",
                    "source_id": "source_002",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "extracting"
        assert data["project_id"] == project_id
    finally:
        app.dependency_overrides.pop(get_kg_service, None)


@pytest.mark.asyncio
async def test_extract_endpoint_project_not_found() -> None:
    """Test extraction returns 404 when project doesn't exist."""
    from app.api.deps import get_kg_service
    from app.main import app

    mock_service = MockKnowledgeGraphService(project=None)
    app.dependency_overrides[get_kg_service] = lambda: mock_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/kg/projects/nonexistent12/extract",
                json={
                    "transcript": "Test transcript",
                    "title": "Test Video",
                    "source_id": "source_001",
                },
            )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_kg_service, None)


@pytest.mark.asyncio
async def test_extract_endpoint_not_bootstrapped() -> None:
    """Test extraction returns 400 when project has no domain profile."""
    from app.api.deps import get_kg_service
    from app.main import app

    project_id = "testproj1234"
    project = _create_test_project(
        project_id=project_id,
        state=ProjectState.CREATED,
        with_profile=False,
        kb_id=None,
    )
    mock_service = MockKnowledgeGraphService(project=project)

    app.dependency_overrides[get_kg_service] = lambda: mock_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/kg/projects/{project_id}/extract",
                json={
                    "transcript": "Test transcript",
                    "title": "Test Video",
                    "source_id": "source_001",
                },
            )

        assert response.status_code == 400
        assert "not bootstrapped" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_kg_service, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: GET /kg/projects/{project_id}/graph
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_graph_stats_endpoint_success() -> None:
    """Test getting graph statistics returns correct counts."""
    from app.api.deps import get_kg_service
    from app.main import app

    project_id = "testproj1234"
    project = _create_test_project(project_id=project_id)
    kb = _create_test_kb()
    mock_service = MockKnowledgeGraphService(project=project, kb=kb)

    app.dependency_overrides[get_kg_service] = lambda: mock_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/kg/projects/{project_id}/graph")

        assert response.status_code == 200
        data = response.json()
        assert data["node_count"] == 3
        assert data["edge_count"] == 2
        assert "entity_types" in data
        assert data["entity_types"]["Person"] == 2
        assert data["entity_types"]["Organization"] == 1
    finally:
        app.dependency_overrides.pop(get_kg_service, None)


@pytest.mark.asyncio
async def test_get_graph_stats_endpoint_no_data() -> None:
    """Test graph stats returns 404 when no KB exists."""
    from app.api.deps import get_kg_service
    from app.main import app

    project_id = "testproj1234"
    project = _create_test_project(project_id=project_id, kb_id=None)
    mock_service = MockKnowledgeGraphService(project=project, kb=None)

    app.dependency_overrides[get_kg_service] = lambda: mock_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/kg/projects/{project_id}/graph")

        assert response.status_code == 404
        assert "no graph data" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_kg_service, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: POST /kg/projects/{project_id}/export
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_export_endpoint_graphml() -> None:
    """Test exporting graph as GraphML returns path and format."""
    from app.api.deps import get_kg_service
    from app.main import app

    project_id = "testproj1234"
    project = _create_test_project(project_id=project_id)
    kb = _create_test_kb()
    mock_service = MockKnowledgeGraphService(project=project, kb=kb)

    app.dependency_overrides[get_kg_service] = lambda: mock_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/kg/projects/{project_id}/export",
                json={"format": "graphml"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "exported"
        assert data["format"] == "graphml"
        assert project_id in data["path"]
        assert mock_service.export_called is True
    finally:
        app.dependency_overrides.pop(get_kg_service, None)


@pytest.mark.asyncio
async def test_export_endpoint_json() -> None:
    """Test exporting graph as JSON returns correct format."""
    from app.api.deps import get_kg_service
    from app.main import app

    project_id = "testproj1234"
    project = _create_test_project(project_id=project_id)
    kb = _create_test_kb()
    mock_service = MockKnowledgeGraphService(project=project, kb=kb)

    app.dependency_overrides[get_kg_service] = lambda: mock_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/kg/projects/{project_id}/export",
                json={"format": "json"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "exported"
        assert data["format"] == "json"
    finally:
        app.dependency_overrides.pop(get_kg_service, None)


@pytest.mark.asyncio
async def test_export_endpoint_no_data() -> None:
    """Test export returns 404 when no graph data exists."""
    from app.api.deps import get_kg_service
    from app.main import app

    project_id = "testproj1234"
    project = _create_test_project(project_id=project_id, kb_id=None)
    mock_service = MockKnowledgeGraphService(project=project, kb=None)

    app.dependency_overrides[get_kg_service] = lambda: mock_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/kg/projects/{project_id}/export",
                json={"format": "graphml"},
            )

        assert response.status_code == 404
        assert "no graph data" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_kg_service, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: GET /kg/projects/{project_id}/nodes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class MockKGServiceWithPersistence(MockKnowledgeGraphService):
    """Extended mock that supports list_nodes via persistence mocking."""

    def __init__(
        self,
        project: KGProject | None = None,
        kb: KnowledgeBase | None = None,
    ) -> None:
        super().__init__(project=project, kb=kb)
        # Override kb_path to return our mock KB via load_knowledge_base
        self._mock_kb = kb


@pytest.mark.asyncio
async def test_list_nodes_endpoint_all() -> None:
    """Test listing all nodes returns correct data."""
    from unittest.mock import patch

    from app.api.deps import get_kg_service
    from app.main import app

    project_id = "testproj1234"
    project = _create_test_project(project_id=project_id)
    kb = _create_test_kb()
    mock_service = MockKGServiceWithPersistence(project=project, kb=kb)

    app.dependency_overrides[get_kg_service] = lambda: mock_service

    # Mock load_knowledge_base to return our test KB
    with patch(
        "app.api.routers.kg.load_knowledge_base", return_value=kb
    ):
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get(f"/kg/projects/{project_id}/nodes")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 3  # Alice, Bob, CIA

            # Verify node structure
            labels = {node["label"] for node in data}
            assert "Alice" in labels
            assert "Bob" in labels
            assert "CIA" in labels
        finally:
            app.dependency_overrides.pop(get_kg_service, None)


@pytest.mark.asyncio
async def test_list_nodes_endpoint_filtered_by_type() -> None:
    """Test listing nodes filtered by entity type."""
    from unittest.mock import patch

    from app.api.deps import get_kg_service
    from app.main import app

    project_id = "testproj1234"
    project = _create_test_project(project_id=project_id)
    kb = _create_test_kb()
    mock_service = MockKGServiceWithPersistence(project=project, kb=kb)

    app.dependency_overrides[get_kg_service] = lambda: mock_service

    with patch(
        "app.api.routers.kg.load_knowledge_base", return_value=kb
    ):
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/kg/projects/{project_id}/nodes",
                    params={"entity_type": "Person"},
                )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2  # Alice and Bob only

            for node in data:
                assert node["entity_type"] == "Person"
        finally:
            app.dependency_overrides.pop(get_kg_service, None)


@pytest.mark.asyncio
async def test_list_nodes_endpoint_no_graph() -> None:
    """Test listing nodes returns 404 when no graph exists."""
    from app.api.deps import get_kg_service
    from app.main import app

    project_id = "testproj1234"
    project = _create_test_project(project_id=project_id, kb_id=None)
    mock_service = MockKGServiceWithPersistence(project=project, kb=None)

    app.dependency_overrides[get_kg_service] = lambda: mock_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/kg/projects/{project_id}/nodes")

        assert response.status_code == 404
        assert "no graph data" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_kg_service, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: GET /kg/projects/{project_id}/nodes/{node_id}/neighbors
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_neighbors_endpoint_success() -> None:
    """Test getting neighbors returns connected nodes."""
    from unittest.mock import patch

    from app.api.deps import get_kg_service
    from app.main import app

    project_id = "testproj1234"
    project = _create_test_project(project_id=project_id)
    kb = _create_test_kb()
    mock_service = MockKGServiceWithPersistence(project=project, kb=kb)

    app.dependency_overrides[get_kg_service] = lambda: mock_service

    with patch(
        "app.api.routers.kg.load_knowledge_base", return_value=kb
    ):
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                # Alice has connections to CIA (worked_for) and Bob (knows - as target)
                response = await client.get(
                    f"/kg/projects/{project_id}/nodes/node_alice12/neighbors"
                )

            assert response.status_code == 200
            data = response.json()

            # Alice is connected to CIA (via worked_for) and Bob (via knows)
            assert len(data) == 2
            labels = {node["label"] for node in data}
            assert "CIA" in labels
            assert "Bob" in labels
        finally:
            app.dependency_overrides.pop(get_kg_service, None)


@pytest.mark.asyncio
async def test_get_neighbors_endpoint_isolated_node() -> None:
    """Test getting neighbors for a node with no connections."""
    from unittest.mock import patch

    from app.api.deps import get_kg_service
    from app.main import app

    project_id = "testproj1234"
    project = _create_test_project(project_id=project_id)
    kb = _create_test_kb()

    # Add an isolated node
    isolated = Node(id="node_isolate", label="Isolated", entity_type="Thing")
    kb.add_node(isolated)

    mock_service = MockKGServiceWithPersistence(project=project, kb=kb)

    app.dependency_overrides[get_kg_service] = lambda: mock_service

    with patch(
        "app.api.routers.kg.load_knowledge_base", return_value=kb
    ):
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/kg/projects/{project_id}/nodes/node_isolate/neighbors"
                )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 0  # No neighbors
        finally:
            app.dependency_overrides.pop(get_kg_service, None)


@pytest.mark.asyncio
async def test_get_neighbors_endpoint_no_graph() -> None:
    """Test get neighbors returns 404 when no graph exists."""
    from app.api.deps import get_kg_service
    from app.main import app

    project_id = "testproj1234"
    project = _create_test_project(project_id=project_id, kb_id=None)
    mock_service = MockKGServiceWithPersistence(project=project, kb=None)

    app.dependency_overrides[get_kg_service] = lambda: mock_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/kg/projects/{project_id}/nodes/some_node_id/neighbors"
            )

        assert response.status_code == 404
        assert "no graph data" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_kg_service, None)
