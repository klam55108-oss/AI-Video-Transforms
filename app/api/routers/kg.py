"""
Knowledge Graph API endpoints.

Provides endpoints for KG project management:
- Project creation and status retrieval
- Domain profile bootstrap from video transcripts
- Discovery confirmation workflow
- Entity extraction from transcripts
- Graph export (GraphML/JSON)
- Node queries and neighbor traversal

Follows existing router patterns (chat.py, transcripts.py).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps import ValidatedProjectId, get_kg_service
from app.kg.domain import DiscoveryStatus, ProjectState
from app.kg.persistence import load_knowledge_base
from app.models.api import (
    CreateProjectResponse,
    DiscoveryResponse,
    ListProjectsResponse,
    ProjectStatusResponse,
)
from app.models.requests import (
    BootstrapRequest,
    ConfirmDiscoveryRequest,
    CreateProjectRequest,
    ExportRequest,
    ExtractRequest,
)
from app.services.kg_service import KnowledgeGraphService


router = APIRouter(prefix="/kg", tags=["knowledge-graph"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post("/projects", response_model=CreateProjectResponse)
async def create_project(
    request: CreateProjectRequest,
    kg_service: KnowledgeGraphService = Depends(get_kg_service),
) -> CreateProjectResponse:
    """
    Create a new KG project.

    Projects start in CREATED state, waiting for the first video
    to trigger bootstrap and domain inference.

    Args:
        request: Project creation request with name
        kg_service: Injected KG service

    Returns:
        CreateProjectResponse with project ID, name, and state
    """
    project = await kg_service.create_project(request.name)
    return CreateProjectResponse(
        project_id=project.id,
        name=project.name,
        state=project.state.value,
    )


@router.get("/projects", response_model=ListProjectsResponse)
async def list_projects(
    kg_service: KnowledgeGraphService = Depends(get_kg_service),
) -> ListProjectsResponse:
    """List all KG projects sorted by creation date (newest first)."""
    projects = await kg_service.list_projects()
    return ListProjectsResponse(
        projects=[
            ProjectStatusResponse(
                project_id=p.id,
                name=p.name,
                state=p.state.value,
                source_count=p.source_count,
                thing_count=p.thing_count,
                connection_count=p.connection_count,
                pending_confirmations=len(
                    [
                        d
                        for d in p.pending_discoveries
                        if d.status == DiscoveryStatus.PENDING
                    ]
                ),
                domain_name=p.domain_profile.name if p.domain_profile else None,
                domain_description=(
                    p.domain_profile.description if p.domain_profile else None
                ),
                error=p.error,
            )
            for p in projects
        ]
    )


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str = Depends(ValidatedProjectId()),
    kg_service: KnowledgeGraphService = Depends(get_kg_service),
) -> dict[str, str]:
    """
    Delete a KG project and all associated data.

    Removes the project, its domain profile, and any extracted
    knowledge graph data.

    Args:
        project_id: 12-character project identifier
        kg_service: Injected KG service

    Returns:
        Status dict with "deleted" status

    Raises:
        HTTPException: 404 if project not found
    """
    success = await kg_service.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")

    return {"status": "deleted", "project_id": project_id}


@router.get("/projects/{project_id}", response_model=ProjectStatusResponse)
async def get_project_status(
    project_id: str = Depends(ValidatedProjectId()),
    kg_service: KnowledgeGraphService = Depends(get_kg_service),
) -> ProjectStatusResponse:
    """
    Get project status and statistics.

    Args:
        project_id: 12-character project identifier
        kg_service: Injected KG service

    Returns:
        ProjectStatusResponse with current stats and domain info

    Raises:
        HTTPException: 404 if project not found
    """
    project = await kg_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    pending = await kg_service.get_pending_confirmations(project_id)

    return ProjectStatusResponse(
        project_id=project.id,
        name=project.name,
        state=project.state.value,
        source_count=project.source_count,
        thing_count=project.thing_count,
        connection_count=project.connection_count,
        pending_confirmations=len(pending),
        domain_name=project.domain_profile.name if project.domain_profile else None,
        domain_description=(
            project.domain_profile.description if project.domain_profile else None
        ),
        error=project.error,
    )


@router.post("/projects/{project_id}/bootstrap")
async def bootstrap_project(
    request: BootstrapRequest,
    background_tasks: BackgroundTasks,
    project_id: str = Depends(ValidatedProjectId()),
    kg_service: KnowledgeGraphService = Depends(get_kg_service),
) -> dict[str, str]:
    """
    Bootstrap domain profile from first video transcript.

    Runs asynchronously in background. Poll GET /kg/projects/{id}
    to check status (state will transition from "bootstrapping" to "active").

    Args:
        project_id: Target project ID
        request: Bootstrap request with transcript, title, source_id
        background_tasks: FastAPI background task manager
        kg_service: Injected KG service

    Returns:
        Status dict with "bootstrapping" status and project_id

    Raises:
        HTTPException: 404 if project not found
        HTTPException: 400 if project already bootstrapped
    """
    project = await kg_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.state != ProjectState.CREATED:
        raise HTTPException(status_code=400, detail="Project already bootstrapped")

    # Run bootstrap in background to avoid request timeout
    background_tasks.add_task(
        kg_service.bootstrap_from_transcript,
        project_id,
        request.transcript,
        request.title,
        request.source_id,
    )

    return {"status": "bootstrapping", "project_id": project_id}


@router.get(
    "/projects/{project_id}/confirmations", response_model=list[DiscoveryResponse]
)
async def get_pending_confirmations(
    project_id: str = Depends(ValidatedProjectId()),
    kg_service: KnowledgeGraphService = Depends(get_kg_service),
) -> list[DiscoveryResponse]:
    """
    Get discoveries waiting for user confirmation.

    Discoveries are new entity or relationship types found during
    extraction that don't match the current domain profile.

    Args:
        project_id: Target project ID
        kg_service: Injected KG service

    Returns:
        List of DiscoveryResponse objects for pending discoveries
    """
    discoveries = await kg_service.get_pending_confirmations(project_id)
    return [
        DiscoveryResponse(
            id=d.id,
            discovery_type=d.discovery_type,
            name=d.name,
            display_name=d.display_name,
            description=d.description,
            examples=d.examples[:5],  # Limit examples for response size
            user_question=d.user_question,
        )
        for d in discoveries
    ]


@router.post("/projects/{project_id}/confirm")
async def confirm_discovery(
    request: ConfirmDiscoveryRequest,
    project_id: str = Depends(ValidatedProjectId()),
    kg_service: KnowledgeGraphService = Depends(get_kg_service),
) -> dict[str, str]:
    """
    Confirm or reject a discovery.

    If confirmed, the discovery is added to the domain profile
    and will be used in future extractions.

    Args:
        project_id: Target project ID
        request: Confirmation request with discovery_id and confirmed flag
        kg_service: Injected KG service

    Returns:
        Status dict with "confirmed" or "rejected" status

    Raises:
        HTTPException: 404 if discovery not found
    """
    success = await kg_service.confirm_discovery(
        project_id,
        request.discovery_id,
        request.confirmed,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Discovery not found")

    return {"status": "confirmed" if request.confirmed else "rejected"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EXTRACTION & EXPORT ENDPOINTS (Phase 2)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post("/projects/{project_id}/extract")
async def extract_from_transcript(
    request: ExtractRequest,
    background_tasks: BackgroundTasks,
    project_id: str = Depends(ValidatedProjectId()),
    kg_service: KnowledgeGraphService = Depends(get_kg_service),
) -> dict[str, str]:
    """
    Extract entities and relationships from a transcript.

    Runs asynchronously in background. The extraction uses the project's
    DomainProfile (created during bootstrap) to guide entity recognition.
    Poll GET /kg/projects/{id} to check updated counts.

    Args:
        project_id: Target project ID
        request: ExtractRequest with transcript, title, and source_id
        background_tasks: FastAPI background task manager
        kg_service: Injected KG service

    Returns:
        Status dict with "extracting" status and project_id

    Raises:
        HTTPException: 404 if project not found
        HTTPException: 400 if project not bootstrapped
    """
    project = await kg_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.domain_profile:
        raise HTTPException(status_code=400, detail="Project not bootstrapped")

    # Run extraction in background to avoid request timeout
    background_tasks.add_task(
        kg_service.extract_from_transcript,
        project_id,
        request.transcript,
        request.title,
        request.source_id,
    )

    return {"status": "extracting", "project_id": project_id}


@router.get("/projects/{project_id}/graph")
async def get_graph_stats(
    project_id: str = Depends(ValidatedProjectId()),
    kg_service: KnowledgeGraphService = Depends(get_kg_service),
) -> dict[str, Any]:
    """
    Get knowledge graph statistics.

    Returns counts of nodes, edges, sources, and breakdowns by
    entity type and relationship type.

    Args:
        project_id: Target project ID
        kg_service: Injected KG service

    Returns:
        Statistics dict with node_count, edge_count, source_count,
        entity_types breakdown, and relationship_types breakdown

    Raises:
        HTTPException: 404 if no graph data exists
    """
    stats = await kg_service.get_graph_stats(project_id)
    if not stats:
        raise HTTPException(status_code=404, detail="No graph data yet")
    return stats


@router.post("/projects/{project_id}/export")
async def export_graph(
    request: ExportRequest,
    project_id: str = Depends(ValidatedProjectId()),
    kg_service: KnowledgeGraphService = Depends(get_kg_service),
) -> dict[str, str]:
    """
    Export knowledge graph to file.

    Supports GraphML format (default) for use with visualization tools
    like Gephi, yEd, or Cytoscape. Also supports JSON export.

    Args:
        project_id: Target project ID
        request: ExportRequest with format ("graphml" or "json")
        kg_service: Injected KG service

    Returns:
        Dict with status, path, and format

    Raises:
        HTTPException: 404 if no graph data to export
    """
    export_path = await kg_service.export_graph(project_id, request.format)
    if not export_path:
        raise HTTPException(status_code=404, detail="No graph data to export")

    return {
        "status": "exported",
        "path": str(export_path),
        "format": request.format,
    }


@router.get("/projects/{project_id}/nodes")
async def list_nodes(
    entity_type: str | None = None,
    project_id: str = Depends(ValidatedProjectId()),
    kg_service: KnowledgeGraphService = Depends(get_kg_service),
) -> list[dict[str, Any]]:
    """
    List nodes in the knowledge graph.

    Optionally filter by entity type (e.g., "Person", "Organization").

    Args:
        project_id: Target project ID
        entity_type: Optional filter by entity type
        kg_service: Injected KG service

    Returns:
        List of node dicts with id, label, entity_type, aliases, etc.

    Raises:
        HTTPException: 404 if no graph data exists
    """
    project = await kg_service.get_project(project_id)
    if not project or not project.kb_id:
        raise HTTPException(status_code=404, detail="No graph data")

    kb = load_knowledge_base(kg_service.kb_path / project.kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    nodes = kb.find_nodes(entity_type=entity_type)
    return [n.model_dump() for n in nodes]


@router.get("/projects/{project_id}/nodes/{node_id}/neighbors")
async def get_neighbors(
    node_id: str,
    project_id: str = Depends(ValidatedProjectId()),
    kg_service: KnowledgeGraphService = Depends(get_kg_service),
) -> list[dict[str, Any]]:
    """
    Get neighbors of a node.

    Returns all nodes connected to the specified node via any edge
    (both incoming and outgoing connections).

    Args:
        project_id: Target project ID
        node_id: 12-character node identifier
        kg_service: Injected KG service

    Returns:
        List of neighbor node dicts

    Raises:
        HTTPException: 404 if no graph data exists
    """
    project = await kg_service.get_project(project_id)
    if not project or not project.kb_id:
        raise HTTPException(status_code=404, detail="No graph data")

    kb = load_knowledge_base(kg_service.kb_path / project.kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    neighbors = kb.get_neighbors(node_id)
    return [n.model_dump() for n in neighbors]
