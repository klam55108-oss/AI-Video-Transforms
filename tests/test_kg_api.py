"""
Knowledge Graph API Tests.

Tests for KG endpoints using httpx AsyncClient with ASGITransport.
Uses app.dependency_overrides for mocking KG service (FastAPI pattern).

Testing Checklist Items:
- [x] POST /kg/projects creates project and returns project_id
- [x] GET /kg/projects lists all projects (empty, multiple, pending counts)
- [x] GET /kg/projects/{id} returns status or 404
- [x] DELETE /kg/projects/{id} deletes project or 404
- [x] POST /kg/projects/{id}/bootstrap handles state validation
- [x] GET /kg/projects/{id}/confirmations returns pending discoveries
- [x] POST /kg/projects/{id}/confirm processes confirmations
"""

from __future__ import annotations

from pathlib import Path
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

    async def delete_project(self, project_id: str) -> bool:
        """Delete a project by ID."""
        if project_id in self.projects:
            del self.projects[project_id]
            self.pending_discoveries.pop(project_id, None)
            return True
        return False

    async def export_graph(
        self, project_id: str, export_format: str = "graphml"
    ) -> Any:
        """Mock export returning a fake Path."""
        from pathlib import Path

        project = self.projects.get(project_id)
        if not project or not project.kb_id:
            return None
        # Return a mock path
        if export_format == "csv":
            return Path(f"/tmp/{project_id}.csv.zip")
        return Path(f"/tmp/{project_id}.{export_format}")

    async def batch_export_graphs(
        self, project_ids: list[str], export_format: str = "graphml"
    ) -> Any:
        """Mock batch export returning a fake Path."""
        from pathlib import Path

        # Check if any projects exist
        valid_count = 0
        for pid in project_ids:
            project = self.projects.get(pid)
            if project and project.kb_id:
                valid_count += 1

        if valid_count == 0:
            return None

        return Path("/tmp/batch_export_12345678.zip")

    # Helper methods for test setup
    def add_project(self, project: KGProject) -> None:
        """Add a pre-configured project for testing."""
        self.projects[project.id] = project

    def add_discovery(self, project_id: str, discovery: Discovery) -> None:
        """Add a pending discovery to a project."""
        if project_id not in self.pending_discoveries:
            self.pending_discoveries[project_id] = []
        self.pending_discoveries[project_id].append(discovery)

    @property
    def kb_path(self) -> Any:
        """Mock kb_path property."""
        return None


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
# TEST: GET /kg/projects (list all)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestListProjects:
    """Test GET /kg/projects endpoint (list all projects)."""

    @pytest.mark.asyncio
    async def test_list_projects_empty(self) -> None:
        """Test that empty project list returns empty array."""
        from app.main import app

        mock_service = MockKGService()
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/kg/projects")

            assert response.status_code == 200
            data = response.json()
            assert data["projects"] == []
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_list_projects_returns_all(self) -> None:
        """Test that all projects are returned with correct fields."""
        from app.main import app

        mock_service = MockKGService()
        # Add multiple projects
        project1 = KGProject(
            id="proj001",
            name="Project One",
            state=ProjectState.CREATED,
        )
        project2 = KGProject(
            id="proj002",
            name="Project Two",
            state=ProjectState.ACTIVE,
            thing_count=5,
            connection_count=3,
        )
        mock_service.add_project(project1)
        mock_service.add_project(project2)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/kg/projects")

            assert response.status_code == 200
            data = response.json()
            assert len(data["projects"]) == 2

            # Check project fields are present
            project_ids = {p["project_id"] for p in data["projects"]}
            assert "proj001" in project_ids
            assert "proj002" in project_ids
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_list_projects_includes_pending_count(self) -> None:
        """Test that pending_confirmations count is calculated correctly."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="proj_pending",
            name="Project with Discoveries",
            state=ProjectState.ACTIVE,
            pending_discoveries=[
                Discovery(
                    discovery_type="thing_type",
                    name="person",
                    display_name="Person",
                    description="A human entity",
                    user_question="Track Person entities?",
                    status=DiscoveryStatus.PENDING,
                ),
                Discovery(
                    discovery_type="thing_type",
                    name="organization",
                    display_name="Organization",
                    description="A company or org",
                    user_question="Track Org entities?",
                    status=DiscoveryStatus.PENDING,
                ),
                Discovery(
                    discovery_type="thing_type",
                    name="old_type",
                    display_name="Old Type",
                    description="An old type",
                    user_question="Track Old entities?",
                    status=DiscoveryStatus.CONFIRMED,  # Not pending
                ),
            ],
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/kg/projects")

            assert response.status_code == 200
            data = response.json()
            assert len(data["projects"]) == 1
            # Only 2 PENDING discoveries should be counted
            assert data["projects"][0]["pending_confirmations"] == 2
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: DELETE /kg/projects/{project_id}
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestDeleteProject:
    """Test DELETE /kg/projects/{project_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_project_success(self) -> None:
        """Test successful project deletion."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="de1e7e123456",
            name="To Delete",
            state=ProjectState.CREATED,
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.delete("/kg/projects/de1e7e123456")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "deleted"
            assert data["project_id"] == "de1e7e123456"

            # Verify project is actually removed
            assert "de1e7e123456" not in mock_service.projects
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_delete_project_not_found_404(self) -> None:
        """Test deletion of non-existent project returns 404."""
        from app.main import app

        mock_service = MockKGService()
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.delete("/kg/projects/abcdef123456")

            assert response.status_code == 404
            assert response.json()["detail"] == "Project not found"
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_delete_project_removes_discoveries(self) -> None:
        """Test deletion also removes associated discoveries."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="d15c0e123456",
            name="With Discoveries",
            state=ProjectState.ACTIVE,
        )
        mock_service.add_project(project)
        discovery = Discovery(
            id="d15c12345678",
            discovery_type="thing_type",
            name="SomeType",
            display_name="Some Type",
            description="A type",
            status=DiscoveryStatus.PENDING,
        )
        mock_service.add_discovery("d15c0e123456", discovery)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.delete("/kg/projects/d15c0e123456")

            assert response.status_code == 200
            # Verify discoveries are also removed
            assert "d15c0e123456" not in mock_service.pending_discoveries
        finally:
            app.dependency_overrides.pop(get_kg_service, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: GET /kg/projects/{id}/graph-data
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestGetGraphData:
    """Test GET /kg/projects/{id}/graph-data endpoint."""

    @pytest.mark.asyncio
    async def test_get_graph_data_not_found_404(self) -> None:
        """Test graph-data returns 404 for non-existent project."""
        from app.main import app

        mock_service = MockKGService()
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/kg/projects/abcdef123456/graph-data")

            assert response.status_code == 404
            assert response.json()["detail"] == "No graph data"
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_get_graph_data_empty_graph(self) -> None:
        """Test graph-data returns 404 for project with no kb_id."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="abc123def456",
            name="Empty Project",
            state=ProjectState.CREATED,
            kb_id=None,
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/kg/projects/abc123def456/graph-data")

            assert response.status_code == 404
            assert response.json()["detail"] == "No graph data"
        finally:
            app.dependency_overrides.pop(get_kg_service, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: CSV EXPORT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestCSVExport:
    """Test CSV export functionality."""

    @pytest.mark.asyncio
    async def test_export_csv_format(self) -> None:
        """Test CSV export returns ZIP file with .csv.zip extension."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="abc123def456",
            name="Test Project",
            state=ProjectState.ACTIVE,
            kb_id="kb001",
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/abc123def456/export",
                    json={"format": "csv"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "exported"
            assert data["format"] == "csv"
            assert data["filename"].endswith(".csv.zip")
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_export_csv_no_graph_data(self) -> None:
        """Test CSV export returns 404 when no graph data exists."""
        from app.main import app

        mock_service = MockKGService()
        project = KGProject(
            id="abc123def456",
            name="Empty Project",
            state=ProjectState.CREATED,
            kb_id=None,
        )
        mock_service.add_project(project)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/abc123def456/export",
                    json={"format": "csv"},
                )

            assert response.status_code == 404
            assert response.json()["detail"] == "No graph data to export"
        finally:
            app.dependency_overrides.pop(get_kg_service, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: BATCH EXPORT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestBatchExport:
    """Test batch export functionality."""

    @pytest.mark.asyncio
    async def test_batch_export_multiple_projects(self) -> None:
        """Test batch export with multiple valid projects."""
        from app.main import app

        mock_service = MockKGService()
        project1 = KGProject(
            id="proj001",
            name="Project One",
            state=ProjectState.ACTIVE,
            kb_id="kb001",
        )
        project2 = KGProject(
            id="proj002",
            name="Project Two",
            state=ProjectState.ACTIVE,
            kb_id="kb002",
        )
        mock_service.add_project(project1)
        mock_service.add_project(project2)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/batch-export",
                    json={
                        "project_ids": ["proj001", "proj002"],
                        "format": "graphml",
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "exported"
            assert data["format"] == "graphml"
            assert data["project_count"] == 2
            assert "batch_export" in data["filename"]
            assert data["filename"].endswith(".zip")
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_batch_export_with_invalid_project_id(self) -> None:
        """Test batch export skips invalid projects and continues."""
        from app.main import app

        mock_service = MockKGService()
        project1 = KGProject(
            id="proj001",
            name="Valid Project",
            state=ProjectState.ACTIVE,
            kb_id="kb001",
        )
        mock_service.add_project(project1)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/batch-export",
                    json={
                        "project_ids": ["proj001", "invalid_id"],
                        "format": "json",
                    },
                )

            # Should succeed with valid project
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "exported"
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_batch_export_empty_list(self) -> None:
        """Test batch export with empty project list returns 400."""
        from app.main import app

        mock_service = MockKGService()
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/batch-export",
                    json={"project_ids": [], "format": "graphml"},
                )

            assert response.status_code == 422  # Pydantic validation error
        finally:
            app.dependency_overrides.pop(get_kg_service, None)

    @pytest.mark.asyncio
    async def test_batch_export_all_invalid_projects(self) -> None:
        """Test batch export returns 404 when all projects are invalid."""
        from app.main import app

        mock_service = MockKGService()
        # Add projects without kb_id
        project1 = KGProject(
            id="proj001",
            name="Empty Project 1",
            state=ProjectState.CREATED,
            kb_id=None,
        )
        project2 = KGProject(
            id="proj002",
            name="Empty Project 2",
            state=ProjectState.CREATED,
            kb_id=None,
        )
        mock_service.add_project(project1)
        mock_service.add_project(project2)
        app.dependency_overrides[get_kg_service] = lambda: mock_service

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/kg/projects/batch-export",
                    json={
                        "project_ids": ["proj001", "proj002"],
                        "format": "csv",
                    },
                )

            assert response.status_code == 404
            assert "No projects could be exported" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_kg_service, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST: GET /kg/exports/{filename} (Download)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestDownloadExport:
    """Test GET /kg/exports/{filename} download endpoint."""

    @pytest.mark.asyncio
    async def test_download_export_not_found_404(self) -> None:
        """Test download returns 404 for non-existent file."""
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get("/kg/exports/nonexistent.json")

        assert response.status_code == 404
        assert response.json()["detail"] == "Export file not found"

    @pytest.mark.asyncio
    async def test_download_export_invalid_filename_400(self) -> None:
        """Test download returns 400 for invalid filename format (special chars)."""
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            # Filename with spaces and special characters
            response = await client.get("/kg/exports/test file!@#.json")

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid filename format"

    @pytest.mark.asyncio
    async def test_download_export_invalid_extension_400(self) -> None:
        """Test download returns 400 for disallowed file extension."""
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get("/kg/exports/test.txt")

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid filename format"

    @pytest.mark.asyncio
    async def test_download_export_success(self, tmp_path: Path) -> None:
        """Test successful file download returns correct content."""
        from app.core.config import get_settings
        from app.main import app

        # Create test export file
        settings = get_settings()
        export_dir = Path(settings.data_path) / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        test_content = '{"nodes": [], "edges": []}'
        test_file = export_dir / "testproject.json"
        test_file.write_text(test_content)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/kg/exports/testproject.json")

            assert response.status_code == 200
            assert response.text == test_content
            assert response.headers["content-type"] == "application/json"
            assert 'attachment' in response.headers["content-disposition"]
            assert 'testproject.json' in response.headers["content-disposition"]
        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()

    @pytest.mark.asyncio
    async def test_download_export_path_traversal_blocked(self) -> None:
        """Test that path traversal attempts are blocked by regex pattern.

        Tests filenames that would reach the endpoint (no path separators).
        Filenames with / or \\ are handled at URL routing level by FastAPI.
        """
        from app.main import app

        # Attack vectors that reach our endpoint (no path separators)
        # These test the regex pattern validation
        malicious_filenames = [
            "..passwd.json",  # Starts with dots
            "test..json",  # Double dots in middle
            "test file.json",  # Space in filename
            "test@file.json",  # Special character @
            "test#file.json",  # Special character #
            "test!file.json",  # Special character !
            "test$.json",  # Dollar sign
            "test;cmd.json",  # Semicolon (command injection)
            "test`cmd`.json",  # Backticks (command injection)
            "test|cmd.json",  # Pipe (command injection)
            "test<>.json",  # Angle brackets
            "test*.json",  # Wildcard
            "test?.json",  # Single char wildcard
        ]

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            for malicious in malicious_filenames:
                response = await client.get(f"/kg/exports/{malicious}")
                assert response.status_code == 400, (
                    f"Malicious filename not blocked: {malicious}"
                )
                assert response.json()["detail"] == "Invalid filename format"
