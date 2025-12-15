"""
Knowledge Graph API Tests.

Tests for KG endpoints using httpx AsyncClient with ASGITransport.
Uses app.dependency_overrides for mocking KG service (FastAPI pattern).

Testing Checklist Items:
- [x] POST /kg/projects creates project and returns project_id
- [x] GET /kg/projects/{id} returns status or 404
- [x] POST /kg/projects/{id}/bootstrap handles state validation
- [x] GET /kg/projects/{id}/confirmations returns pending discoveries
- [x] POST /kg/projects/{id}/confirm processes confirmations
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_kg_service
from app.kg.domain import (
    Discovery,
    DiscoveryStatus,
    DomainProfile,
    KGProject,
    ProjectState,
    ThingType,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MOCK SERVICE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class MockKGService:
    """
    Mock KnowledgeGraphService for API testing.

    Provides in-memory storage for projects and discoveries,
    allowing tests to control service behavior without disk I/O.
    """

    def __init__(self) -> None:
        self.projects: dict[str, KGProject] = {}
        self.pending_discoveries: dict[str, list[Discovery]] = {}
        # Track calls for verification
        self.bootstrap_calls: list[dict[str, Any]] = []

    async def create_project(self, name: str) -> KGProject:
        """Create a mock project."""
        project = KGProject(name=name, state=ProjectState.CREATED)
        self.projects[project.id] = project
        return project

    async def get_project(self, project_id: str) -> KGProject | None:
        """Get project by ID."""
        return self.projects.get(project_id)

    async def list_projects(self) -> list[KGProject]:
        """List all projects."""
        return list(self.projects.values())

    async def bootstrap_from_transcript(
        self,
        project_id: str,
        transcript: str,
        title: str,
        source_id: str,
    ) -> DomainProfile:
        """Track bootstrap call and return mock profile."""
        self.bootstrap_calls.append(
            {
                "project_id": project_id,
                "transcript": transcript,
                "title": title,
                "source_id": source_id,
            }
        )
        # Return a minimal domain profile
        return DomainProfile(
            name="Mock Domain",
            description="Mock domain for testing",
            thing_types=[ThingType(name="Person", description="A person")],
        )

    async def get_pending_confirmations(self, project_id: str) -> list[Discovery]:
        """Get pending discoveries for a project."""
        return self.pending_discoveries.get(project_id, [])

    async def confirm_discovery(
        self,
        project_id: str,
        discovery_id: str,
        confirmed: bool,
    ) -> bool:
        """Confirm or reject a discovery."""
        discoveries = self.pending_discoveries.get(project_id, [])
        for d in discoveries:
            if d.id == discovery_id:
                d.status = (
                    DiscoveryStatus.CONFIRMED if confirmed else DiscoveryStatus.REJECTED
                )
                return True
        return False

    # Helper methods for test setup
    def add_project(self, project: KGProject) -> None:
        """Add a pre-configured project for testing."""
        self.projects[project.id] = project

    def add_discovery(self, project_id: str, discovery: Discovery) -> None:
        """Add a pending discovery to a project."""
        if project_id not in self.pending_discoveries:
            self.pending_discoveries[project_id] = []
        self.pending_discoveries[project_id].append(discovery)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: POST /kg/projects
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestCreateProject:
    """Test POST /kg/projects endpoint."""

    @pytest.mark.asyncio
    async def test_create_project_success(self) -> None:
        """Test successful project creation returns 200 with project data."""
        from app.main import app

        mock_service = MockKGService()
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects",
                    json={"name": "Test Project"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Test Project"
            assert data["state"] == "created"
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_create_project_returns_project_id(self) -> None:
        """Test that created project has a valid 12-character project_id."""
        from app.main import app

        mock_service = MockKGService()
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects",
                    json={"name": "ID Test Project"},
                )

            assert response.status_code == 200
            data = response.json()
            assert "project_id" in data
            # Project IDs are 12-character hex strings
            assert len(data["project_id"]) == 12
            assert all(c in "0123456789abcdef" for c in data["project_id"])
        finally:
            app.dependency_overrides.pop(get_kg_service, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: GET /kg/projects/{project_id}
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestGetProjectStatus:
    """Test GET /kg/projects/{project_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_project_status_success(self) -> None:
        """Test successful retrieval of project status."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="abc123def456",
            name="Status Test",
            state=ProjectState.ACTIVE,
            source_count=3,
            thing_count=15,
            connection_count=8,
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/kg/projects/abc123def456")

            assert response.status_code == 200
            data = response.json()
            assert data["project_id"] == "abc123def456"
            assert data["name"] == "Status Test"
            assert data["state"] == "active"
            assert data["source_count"] == 3
            assert data["thing_count"] == 15
            assert data["connection_count"] == 8
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_get_project_status_not_found_404(self) -> None:
        """Test that non-existent project returns 404."""
        from app.main import app

        mock_service = MockKGService()
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/kg/projects/000000000000")

            assert response.status_code == 404
            assert response.json()["detail"] == "Project not found"
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_get_project_status_includes_domain_info(self) -> None:
        """Test that bootstrapped project includes domain name and description."""
        from app.main import app

        mock_service = MockKGService()
        profile = DomainProfile(
            name="CIA Research Domain",
            description="Mind control research domain",
            thing_types=[ThingType(name="Person", description="A person")],
        )
        project = KGProject(
            id="d0a1c2123456",
            name="Domain Test",
            state=ProjectState.ACTIVE,
            domain_profile=profile,
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/kg/projects/d0a1c2123456")

            assert response.status_code == 200
            data = response.json()
            assert data["domain_name"] == "CIA Research Domain"
            assert data["domain_description"] == "Mind control research domain"
        finally:
            app.dependency_overrides.pop(get_kg_service, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: POST /kg/projects/{project_id}/bootstrap
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestBootstrapProject:
    """Test POST /kg/projects/{project_id}/bootstrap endpoint."""

    @pytest.mark.asyncio
    async def test_bootstrap_project_success(self) -> None:
        """Test successful bootstrap initiation returns bootstrapping status."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="b00112345678",
            name="Bootstrap Test",
            state=ProjectState.CREATED,
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/b00112345678/bootstrap",
                    json={
                        "transcript": "This is a test transcript about MKUltra...",
                        "title": "Test Video Title",
                        "source_id": "src12345678",
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "bootstrapping"
            assert data["project_id"] == "b00112345678"
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_bootstrap_project_not_found_404(self) -> None:
        """Test bootstrap on non-existent project returns 404."""
        from app.main import app

        mock_service = MockKGService()
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/000000000000/bootstrap",
                    json={
                        "transcript": "Test transcript",
                        "title": "Test Title",
                        "source_id": "src00000000",
                    },
                )

            assert response.status_code == 404
            assert response.json()["detail"] == "Project not found"
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_bootstrap_project_already_bootstrapped_400(self) -> None:
        """Test bootstrap on already-bootstrapped project returns 400."""
        from app.main import app

        mock_service = MockKGService()
        # Project is in ACTIVE state (already bootstrapped)
        project = KGProject(
            id="ac11e1234567",
            name="Already Active",
            state=ProjectState.ACTIVE,
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/ac11e1234567/bootstrap",
                    json={
                        "transcript": "Trying to bootstrap again",
                        "title": "Second Bootstrap",
                        "source_id": "src11111111",
                    },
                )

            assert response.status_code == 400
            assert response.json()["detail"] == "Project already bootstrapped"
        finally:
            app.dependency_overrides.pop(get_kg_service, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: GET /kg/projects/{project_id}/confirmations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestGetConfirmations:
    """Test GET /kg/projects/{project_id}/confirmations endpoint."""

    @pytest.mark.asyncio
    async def test_get_confirmations_empty(self) -> None:
        """Test that project with no discoveries returns empty list."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="00d15c123456",
            name="No Discoveries",
            state=ProjectState.ACTIVE,
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/kg/projects/00d15c123456/confirmations")

            assert response.status_code == 200
            data = response.json()
            assert data == []
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_get_confirmations_returns_pending(self) -> None:
        """Test that pending discoveries are returned with correct fields."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="0e0d10123456",
            name="Has Discoveries",
            state=ProjectState.ACTIVE,
        )
        mock_service.add_project(project)

        # Add a pending discovery
        discovery = Discovery(
            id="disc1234",
            discovery_type="thing_type",
            name="Subproject",
            display_name="Subproject",
            description="A CIA subproject within MKUltra",
            examples=["Subproject 68", "Subproject 119", "Subproject 57"],
            user_question="Track Subprojects as a separate entity type?",
            status=DiscoveryStatus.PENDING,
        )
        mock_service.add_discovery("0e0d10123456", discovery)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/kg/projects/0e0d10123456/confirmations")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["id"] == "disc1234"
            assert data[0]["discovery_type"] == "thing_type"
            assert data[0]["name"] == "Subproject"
            assert data[0]["display_name"] == "Subproject"
            assert data[0]["description"] == "A CIA subproject within MKUltra"
            assert len(data[0]["examples"]) == 3
            assert (
                data[0]["user_question"]
                == "Track Subprojects as a separate entity type?"
            )
        finally:
            app.dependency_overrides.pop(get_kg_service, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: POST /kg/projects/{project_id}/confirm
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestConfirmDiscovery:
    """Test POST /kg/projects/{project_id}/confirm endpoint."""

    @pytest.mark.asyncio
    async def test_confirm_discovery_success(self) -> None:
        """Test successful confirmation of a discovery."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="c00f11123456",
            name="Confirm Test",
            state=ProjectState.ACTIVE,
        )
        mock_service.add_project(project)

        discovery = Discovery(
            id="toconfirm",
            discovery_type="thing_type",
            name="Researcher",
            display_name="Researcher",
            description="A researcher involved in the project",
            examples=["Dr. Gottlieb", "Dr. Cameron"],
            user_question="Track Researchers?",
            status=DiscoveryStatus.PENDING,
        )
        mock_service.add_discovery("c00f11123456", discovery)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/c00f11123456/confirm",
                    json={
                        "discovery_id": "toconfirm",
                        "confirmed": True,
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "confirmed"
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_confirm_discovery_reject(self) -> None:
        """Test successful rejection of a discovery."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="e3ec11234567",
            name="Reject Test",
            state=ProjectState.ACTIVE,
        )
        mock_service.add_project(project)

        discovery = Discovery(
            id="toreject1",
            discovery_type="connection_type",
            name="funded_by",
            display_name="funded by",
            description="Funding relationship",
            examples=["CIA funded project"],
            user_question="Track funding relationships?",
            status=DiscoveryStatus.PENDING,
        )
        mock_service.add_discovery("e3ec11234567", discovery)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/e3ec11234567/confirm",
                    json={
                        "discovery_id": "toreject1",
                        "confirmed": False,
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "rejected"
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_confirm_discovery_not_found_404(self) -> None:
        """Test confirmation of non-existent discovery returns 404."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="00d15c654321",
            name="No Discovery",
            state=ProjectState.ACTIVE,
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/00d15c654321/confirm",
                    json={
                        "discovery_id": "doesnotex",
                        "confirmed": True,
                    },
                )

            assert response.status_code == 404
            assert response.json()["detail"] == "Discovery not found"
        finally:
            app.dependency_overrides.pop(get_kg_service, None)
