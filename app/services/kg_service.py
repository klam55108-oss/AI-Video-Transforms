"""
Knowledge Graph Service — orchestrates KG operations.

Manages the lifecycle of KG projects including:
- Project creation and retrieval
- Domain profile bootstrap from video transcripts
- Discovery confirmation workflow
- Atomic persistence of project state

Follows existing service patterns (SessionService, StorageService).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
)

from app.core.config import get_settings
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
from app.kg.knowledge_base import KnowledgeBase
from app.kg.models import Source, SourceType
from app.kg.persistence import export_graphml, load_knowledge_base, save_knowledge_base
from app.kg.prompts.bootstrap_prompt import BOOTSTRAP_SYSTEM_PROMPT
from app.kg.prompts.templates import generate_extraction_prompt
from app.kg.schemas import ExtractedDiscovery, ExtractionResult
from app.kg.tools.bootstrap import (
    BOOTSTRAP_TOOL_NAMES,
    clear_bootstrap_collector,
    create_bootstrap_mcp_server,
    get_bootstrap_data,
)
from app.kg.tools.extraction import EXTRACTION_TOOL_NAMES, create_extraction_mcp_server

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Get current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


class KnowledgeGraphService:
    """
    Service for Knowledge Graph operations.

    Handles:
    - Project lifecycle (create, get, list)
    - Domain inference from video transcripts (bootstrap)
    - Discovery confirmation workflow
    - Atomic persistence of project state

    Thread Safety:
        Uses atomic writes (write to temp file, then rename) for persistence.
        The bootstrap collector uses thread-local locking for concurrent access.
    """

    def __init__(self, data_path: Path) -> None:
        """
        Initialize Knowledge Graph Service.

        Args:
            data_path: Base directory for data storage (e.g., Path("data"))
        """
        self.data_path = data_path
        self.projects_path = data_path / "kg_projects"
        self.projects_path.mkdir(parents=True, exist_ok=True)

        # Knowledge base storage path
        self.kb_path = data_path / "knowledge_bases"
        self.kb_path.mkdir(parents=True, exist_ok=True)

        # In-memory project cache for fast retrieval with LRU eviction
        self._projects: OrderedDict[str, KGProject] = OrderedDict()
        self._max_cache_size = get_settings().kg_project_cache_max_size

        # Concurrency control for Claude API calls
        self._claude_semaphore = asyncio.Semaphore(
            get_settings().claude_api_max_concurrent
        )

        # Bootstrap MCP server (created once, reused)
        self._bootstrap_server = create_bootstrap_mcp_server()

        # Extraction MCP server (created once, reused)
        self._extraction_server = create_extraction_mcp_server()

        logger.info(
            f"KnowledgeGraphService initialized with data_path={data_path}, "
            f"max_concurrent_claude={get_settings().claude_api_max_concurrent}, "
            f"max_cache_size={self._max_cache_size}"
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PROJECT LIFECYCLE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def create_project(self, name: str) -> KGProject:
        """
        Create a new KG project.

        Project starts in CREATED state, waiting for first video
        to trigger bootstrap and domain inference.

        Args:
            name: User-provided project name

        Returns:
            The newly created KGProject
        """
        project = KGProject(name=name, state=ProjectState.CREATED)

        # Enforce cache limit before adding
        self._enforce_cache_limit()
        self._projects[project.id] = project
        await self._save_project(project)

        logger.info(f"Created KG project: {project.id} ({name})")
        return project

    async def get_project(self, project_id: str) -> KGProject | None:
        """
        Get project by ID.

        Checks in-memory cache first, then loads from disk if not found.

        Args:
            project_id: 12-character project identifier

        Returns:
            KGProject if found, None otherwise
        """
        # Check cache first
        if project_id in self._projects:
            # Move to end (LRU update)
            self._projects.move_to_end(project_id)
            return self._projects[project_id]

        # Try loading from disk
        project_file = self.projects_path / f"{project_id}.json"
        if project_file.exists():
            try:
                data = json.loads(project_file.read_text(encoding="utf-8"))
                project = KGProject.model_validate(data)
                # Enforce cache limit before adding
                self._enforce_cache_limit()
                self._projects[project_id] = project
                return project
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to load project {project_id}: {e}")
                return None

        return None

    async def list_projects(self) -> list[KGProject]:
        """
        List all projects.

        Scans disk for project files and returns sorted by creation date.

        Returns:
            List of KGProject objects, newest first
        """
        projects: list[KGProject] = []

        for f in self.projects_path.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                project = KGProject.model_validate(data)
                projects.append(project)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Skipping invalid project file {f.name}: {e}")
                continue

        # Sort by creation date, newest first
        return sorted(projects, key=lambda p: p.created_at, reverse=True)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # BOOTSTRAP (First Video)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def bootstrap_from_transcript(
        self,
        project_id: str,
        transcript: str,
        title: str,
        source_id: str,
    ) -> DomainProfile:
        """
        Bootstrap domain profile from first video transcript.

        Runs Claude with bootstrap MCP tools to analyze the transcript
        and infer entity types, relationship types, seed entities, and
        extraction context.

        Args:
            project_id: Target project ID
            transcript: Full transcript text
            title: Video title
            source_id: Unique identifier for the source video

        Returns:
            The inferred DomainProfile

        Raises:
            ValueError: If project not found
            RuntimeError: If bootstrap fails
        """
        project = await self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Update state to bootstrapping
        project.state = ProjectState.BOOTSTRAPPING
        project.error = None
        await self._save_project(project)

        logger.info(f"Starting bootstrap for project {project_id}")

        try:
            # Clear the bootstrap data collector before starting
            clear_bootstrap_collector()

            # Build the prompt for bootstrap analysis
            prompt = self._build_bootstrap_prompt(transcript, title, project.name)

            # Configure Claude with bootstrap tools
            options = ClaudeAgentOptions(
                model=get_settings().claude_model,
                system_prompt=BOOTSTRAP_SYSTEM_PROMPT,
                mcp_servers={"kg-bootstrap": self._bootstrap_server},
                allowed_tools=BOOTSTRAP_TOOL_NAMES,
                max_turns=10,
                permission_mode="bypassPermissions",  # Tools are safe, no user approval needed
            )

            # Run Claude to perform bootstrap analysis (with concurrency limit)
            async with self._claude_semaphore:
                async with ClaudeSDKClient(options) as client:
                    await client.query(prompt)

                    # Consume all messages (tools execute and store data in collector)
                    async for message in client.receive_response():
                        if isinstance(message, ResultMessage):
                            if message.is_error:
                                raise RuntimeError(
                                    f"Bootstrap agent error: {message.result}"
                                )
                            logger.info(
                                f"Bootstrap completed in {message.num_turns} turns, "
                                f"cost: ${message.total_cost_usd or 0:.4f}"
                            )
                        elif isinstance(message, AssistantMessage):
                            # Log progress (optional)
                            pass

            # Collect bootstrap data from tools
            bootstrap_data = get_bootstrap_data()

            if not bootstrap_data:
                raise RuntimeError(
                    "Bootstrap produced no data - tools may not have run"
                )

            # Build domain profile from collected data
            profile = self._build_domain_profile(bootstrap_data, source_id)

            # Update project with profile
            project.domain_profile = profile
            project.state = ProjectState.ACTIVE
            project.source_count = 1
            project.updated_at = _utc_now()

            await self._save_project(project)

            logger.info(
                f"Bootstrap complete for project {project_id}: "
                f"{len(profile.thing_types)} thing types, "
                f"{len(profile.connection_types)} connection types, "
                f"{len(profile.seed_entities)} seed entities"
            )

            return profile

        except Exception as e:
            # Restore project to created state on failure
            project.state = ProjectState.CREATED
            project.error = str(e)
            project.updated_at = _utc_now()
            await self._save_project(project)

            logger.error(f"Bootstrap failed for project {project_id}: {e}")
            raise

    def _build_bootstrap_prompt(
        self, transcript: str, title: str, project_name: str
    ) -> str:
        """
        Build the prompt for bootstrap analysis.

        Truncates transcript if needed to stay within context limits.

        Args:
            transcript: Full transcript text
            title: Video title
            project_name: User's project name

        Returns:
            Formatted prompt string
        """
        # Truncate transcript if needed (leave room for system prompt and tools)
        max_transcript = 12000
        truncated = len(transcript) > max_transcript
        content = transcript[:max_transcript]

        truncation_note = (
            "\n\n[Transcript truncated for length...]" if truncated else ""
        )

        return f"""Project: {project_name}
Video Title: {title}

Analyze this content and create a domain profile for knowledge extraction.
Call all bootstrap tools in order to build a complete domain profile.

## Transcript

{content}{truncation_note}
"""

    def _build_domain_profile(
        self, data: dict[str, Any], source_id: str
    ) -> DomainProfile:
        """
        Build DomainProfile from collected bootstrap tool results.

        Args:
            data: Dict with keys matching bootstrap tool steps
            source_id: ID of the source video

        Returns:
            Constructed DomainProfile
        """
        finalization = data.get("finalize_domain_profile", {})
        analysis = data.get("analyze_content_domain", {})

        # Build thing types from collected data
        thing_types = [ThingType(**t) for t in data.get("identify_thing_types", [])]

        # Build connection types (handle tuple conversion for examples)
        connection_types_data = data.get("identify_connection_types", [])
        connection_types = []
        for c in connection_types_data:
            # Convert example lists to tuples
            examples = [
                tuple(ex) if isinstance(ex, list) else ex
                for ex in c.get("examples", [])
            ]
            connection_types.append(
                ConnectionType(
                    name=c["name"],
                    display_name=c["display_name"],
                    description=c["description"],
                    examples=examples,
                    directional=c.get("directional", True),
                )
            )

        # Build seed entities
        seed_entities = [
            SeedEntity(**e) for e in data.get("identify_seed_entities", [])
        ]

        # Get extraction context
        extraction_context = data.get("generate_extraction_context", "")

        # Determine name and description
        name = (
            finalization.get("name") or analysis.get("topic_summary", "Untitled")[:50]
        )
        description = finalization.get("description") or analysis.get(
            "topic_summary", ""
        )

        return DomainProfile(
            name=name,
            description=description,
            thing_types=thing_types,
            connection_types=connection_types,
            seed_entities=seed_entities,
            extraction_context=extraction_context,
            bootstrap_confidence=finalization.get("confidence", 0.5),
            bootstrapped_from=source_id,
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # DISCOVERY CONFIRMATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def get_pending_confirmations(self, project_id: str) -> list[Discovery]:
        """
        Get discoveries waiting for user confirmation.

        Discoveries are new entity or relationship types found during
        extraction that don't match the current domain profile.

        Args:
            project_id: Target project ID

        Returns:
            List of pending Discovery objects
        """
        project = await self.get_project(project_id)
        if not project:
            return []

        return [
            d
            for d in project.pending_discoveries
            if d.status == DiscoveryStatus.PENDING
        ]

    async def confirm_discovery(
        self,
        project_id: str,
        discovery_id: str,
        confirmed: bool,
    ) -> bool:
        """
        Process user's confirmation decision for a discovery.

        If confirmed, adds the discovered type to the domain profile.
        Either way, removes the discovery from pending list.

        Args:
            project_id: Target project ID
            discovery_id: 8-character discovery identifier
            confirmed: True to add to profile, False to reject

        Returns:
            True if discovery was processed, False if not found
        """
        project = await self.get_project(project_id)
        if not project or not project.domain_profile:
            return False

        # Find the discovery
        discovery = None
        for d in project.pending_discoveries:
            if d.id == discovery_id:
                discovery = d
                break

        if not discovery:
            return False

        if confirmed:
            # Add to domain profile based on discovery type
            if discovery.discovery_type == "thing_type":
                project.domain_profile.add_thing_type(
                    ThingType(
                        name=discovery.name,
                        description=discovery.description,
                        examples=discovery.examples,
                        priority=2,
                    )
                )
            elif discovery.discovery_type == "connection_type":
                project.domain_profile.add_connection_type(
                    ConnectionType(
                        name=discovery.name,
                        display_name=discovery.display_name,
                        description=discovery.description,
                    )
                )

            # Track refinement source
            if discovery.found_in_source:
                project.domain_profile.refined_from.append(discovery.found_in_source)

            discovery.status = DiscoveryStatus.CONFIRMED
            logger.info(
                f"Discovery {discovery_id} confirmed: {discovery.name} "
                f"({discovery.discovery_type})"
            )
        else:
            discovery.status = DiscoveryStatus.REJECTED
            logger.info(f"Discovery {discovery_id} rejected: {discovery.name}")

        # Remove from pending (keep only pending items)
        project.pending_discoveries = [
            d
            for d in project.pending_discoveries
            if d.status == DiscoveryStatus.PENDING
        ]

        project.updated_at = _utc_now()
        await self._save_project(project)

        return True

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EXTRACTION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def extract_from_transcript(
        self,
        project_id: str,
        transcript: str,
        title: str,
        source_id: str,
    ) -> dict[str, Any]:
        """
        Extract entities and relationships from a transcript.

        Uses the project's DomainProfile to guide extraction. Runs Claude with
        the extraction MCP tool to analyze content and return structured data.
        Results are stored in the project's KnowledgeBase.

        Args:
            project_id: Target project ID
            transcript: Full transcript text to extract from
            title: Title of the source content
            source_id: Unique identifier for this source

        Returns:
            Dict with extraction statistics:
            - entities_extracted: Number of entities found
            - relationships_extracted: Number of relationships found
            - discoveries: Number of new type discoveries
            - summary: Optional summary from the extraction

        Raises:
            ValueError: If project not found or not bootstrapped
            RuntimeError: If extraction fails
        """
        project = await self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        if not project.domain_profile:
            raise ValueError("Project has no domain profile. Run bootstrap first.")

        logger.info(f"Starting extraction for project {project_id}, source: {title}")

        # Get or create KB
        kb = await self._get_or_create_kb(project)

        # Generate extraction prompt from domain profile
        prompt = generate_extraction_prompt(
            profile=project.domain_profile,
            title=title,
            content=transcript,
        )

        # Configure Claude with extraction tools
        options = ClaudeAgentOptions(
            model=get_settings().claude_model,
            system_prompt=(
                "You are a knowledge extraction specialist. Analyze the content "
                "and call the extract_knowledge tool with your findings. Extract "
                "all relevant entities and relationships based on the domain profile."
            ),
            mcp_servers={"kg-extraction": self._extraction_server},
            allowed_tools=EXTRACTION_TOOL_NAMES,
            max_turns=3,
            permission_mode="bypassPermissions",
        )

        extraction_result: ExtractionResult | None = None

        try:
            # Run extraction with concurrency limit
            async with self._claude_semaphore:
                async with ClaudeSDKClient(options) as client:
                    await client.query(prompt)

                    # Process messages to find extraction result
                    async for message in client.receive_response():
                        if isinstance(message, ResultMessage):
                            if message.is_error:
                                raise RuntimeError(
                                    f"Extraction agent error: {message.result}"
                                )
                            logger.info(
                                f"Extraction completed in {message.num_turns} turns, "
                                f"cost: ${message.total_cost_usd or 0:.4f}"
                            )

                            # Check for extraction result in tool results
                            logger.debug(
                                f"Checking ResultMessage for extraction result "
                                f"(has tool_results: {hasattr(message, 'tool_results')})"
                            )
                            if (
                                hasattr(message, "tool_results")
                                and message.tool_results
                            ):
                                logger.debug(
                                    f"Found {len(message.tool_results)} tool results to check"
                                )
                                for i, result in enumerate(message.tool_results):
                                    if (
                                        isinstance(result, dict)
                                        and "_extraction_result" in result
                                    ):
                                        logger.info(
                                            f"Found extraction result in tool_results[{i}]"
                                        )
                                        extraction_result = (
                                            ExtractionResult.model_validate(
                                                result["_extraction_result"]
                                            )
                                        )
                        elif isinstance(message, AssistantMessage):
                            # Check tool use blocks for extraction results
                            logger.debug(
                                f"Checking AssistantMessage for extraction result "
                                f"(has content: {hasattr(message, 'content')})"
                            )
                            if hasattr(message, "content"):
                                for i, block in enumerate(message.content):
                                    if hasattr(block, "tool_result"):
                                        tool_result = block.tool_result
                                        if (
                                            isinstance(tool_result, dict)
                                            and "_extraction_result" in tool_result
                                        ):
                                            logger.info(
                                                f"Found extraction result in content[{i}].tool_result"
                                            )
                                            extraction_result = (
                                                ExtractionResult.model_validate(
                                                    tool_result["_extraction_result"]
                                                )
                                            )

        except Exception as e:
            logger.error(f"Extraction failed for project {project_id}: {e}")
            raise RuntimeError(f"Extraction failed: {e}") from e

        if not extraction_result:
            logger.error(
                f"No extraction result found for project {project_id}. "
                f"Check that the extraction tool returned _extraction_result in its response."
            )
            raise ValueError("Extraction failed - no results returned from agent")

        # Add source to KB
        source = Source(id=source_id, title=title, source_type=SourceType.VIDEO)
        kb.add_source(source)

        # Apply extraction results to KB
        self._apply_extraction_to_kb(kb, extraction_result, source_id)

        # Save KB
        save_knowledge_base(kb, self.kb_path)

        # Update project stats
        stats = kb.stats()
        project.thing_count = stats["node_count"]
        project.connection_count = stats["edge_count"]
        project.source_count = stats["source_count"]
        project.kb_id = kb.id

        # Add any discoveries to pending for user confirmation
        for disc in extraction_result.discoveries:
            project.pending_discoveries.append(
                Discovery(
                    discovery_type=disc.discovery_type,
                    name=disc.name,
                    display_name=disc.display_name,
                    description=disc.description,
                    examples=disc.examples,
                    found_in_source=source_id,
                    user_question=self._generate_discovery_question(disc),
                )
            )

        project.updated_at = _utc_now()
        await self._save_project(project)

        logger.info(
            f"Extraction complete for project {project_id}: "
            f"{len(extraction_result.entities)} entities, "
            f"{len(extraction_result.relationships)} relationships, "
            f"{len(extraction_result.discoveries)} discoveries"
        )

        return {
            "entities_extracted": len(extraction_result.entities),
            "relationships_extracted": len(extraction_result.relationships),
            "discoveries": len(extraction_result.discoveries),
            "summary": extraction_result.summary,
        }

    def _apply_extraction_to_kb(
        self,
        kb: KnowledgeBase,
        result: ExtractionResult,
        source_id: str,
    ) -> None:
        """
        Apply extraction results to a knowledge base.

        Creates or updates nodes for each entity and adds relationships
        between them. Handles alias merging for existing entities.

        Args:
            kb: KnowledgeBase to update
            result: ExtractionResult containing entities and relationships
            source_id: ID of the source for provenance tracking
        """
        # Add entities as nodes
        for entity in result.entities:
            node, created = kb.get_or_create_node(
                label=entity.label,
                entity_type=entity.entity_type,
                aliases=entity.aliases,
                description=entity.description,
            )
            node.add_source(source_id)

            # Add any new aliases from this extraction
            for alias in entity.aliases:
                node.add_alias(alias)

        # Add relationships as edges
        for rel in result.relationships:
            kb.add_relationship(
                source_label=rel.source_label,
                target_label=rel.target_label,
                relationship_type=rel.relationship_type,
                source_id=source_id,
                confidence=rel.confidence,
                evidence=rel.evidence,
            )

    async def _get_or_create_kb(self, project: KGProject) -> KnowledgeBase:
        """
        Get existing KnowledgeBase or create a new one.

        If the project has a kb_id, attempts to load the existing KB.
        Otherwise, creates a new KB linked to the project's domain profile.

        Args:
            project: KGProject to get/create KB for

        Returns:
            KnowledgeBase instance (existing or newly created)
        """
        if project.kb_id:
            kb_path = self.kb_path / project.kb_id
            kb = load_knowledge_base(kb_path)
            if kb:
                return kb
            # Existing KB failed to load - log warning for investigation
            logger.warning(
                f"Failed to load existing KB at {kb_path} for project {project.id}. "
                f"Creating new KB. This may indicate data corruption."
            )

        # Create new KB linked to project
        kb = KnowledgeBase(
            name=project.name,
            description=f"Knowledge base for {project.name}",
            domain_profile=project.domain_profile,
        )
        return kb

    def _generate_discovery_question(self, disc: ExtractedDiscovery) -> str:
        """
        Generate a user-friendly question for a discovery.

        Creates a natural language question to ask the user about
        whether to add a newly discovered type to the domain profile.

        Args:
            disc: ExtractedDiscovery to generate question for

        Returns:
            Human-readable question string
        """
        examples = ", ".join(disc.examples[:3])
        if disc.discovery_type == "thing_type":
            return f"I found '{disc.display_name}' items (like {examples}). Should I track these?"
        else:
            return f"I noticed things '{disc.display_name}' each other. Track this connection type?"

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EXPORT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def export_graph(
        self,
        project_id: str,
        format: str = "graphml",
    ) -> Path | None:
        """
        Export a project's knowledge graph to file.

        Supports GraphML format (default) for use with visualization tools
        like Gephi, yEd, or Cytoscape. Also supports JSON export.

        Args:
            project_id: ID of the project to export
            format: Export format - "graphml" (default) or "json"

        Returns:
            Path to the exported file, or None if no graph data exists
        """
        project = await self.get_project(project_id)
        if not project or not project.kb_id:
            return None

        kb = load_knowledge_base(self.kb_path / project.kb_id)
        if not kb:
            return None

        # Create exports directory
        export_path = self.data_path / "exports"
        export_path.mkdir(parents=True, exist_ok=True)

        output_file = export_path / f"{project_id}.{format}"

        if format == "graphml":
            export_graphml(kb, output_file)
        else:
            # JSON export
            output_file = output_file.with_suffix(".json")
            data = {
                "nodes": [n.model_dump() for n in kb._nodes.values()],
                "edges": [e.model_dump() for e in kb._edges.values()],
                "sources": [s.model_dump() for s in kb._sources.values()],
            }
            output_file.write_text(json.dumps(data, indent=2, default=str))

        logger.info(f"Exported graph for project {project_id} to {output_file}")
        return output_file

    async def get_graph_stats(self, project_id: str) -> dict[str, Any] | None:
        """
        Get statistics for a project's knowledge graph.

        Returns counts of nodes, edges, sources, and breakdowns
        by entity type and relationship type.

        Args:
            project_id: ID of the project

        Returns:
            Statistics dictionary, or None if no graph data exists
        """
        project = await self.get_project(project_id)
        if not project or not project.kb_id:
            return None

        kb = load_knowledge_base(self.kb_path / project.kb_id)
        if not kb:
            return None

        return kb.stats()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CACHE MANAGEMENT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _enforce_cache_limit(self) -> None:
        """
        Evict oldest entries if cache exceeds limit.

        Uses LRU (Least Recently Used) eviction policy via OrderedDict.
        Evicts oldest projects until cache size is below the limit.
        """
        while len(self._projects) >= self._max_cache_size:
            evicted_id, _ = self._projects.popitem(last=False)
            logger.info(f"Cache eviction: removed project {evicted_id}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PERSISTENCE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def _save_project(self, project: KGProject) -> None:
        """
        Save project to disk using atomic write pattern.

        Uses write-to-temp-then-rename for thread safety. File renames
        are atomic on POSIX systems, preventing partial writes.

        Args:
            project: Project to persist
        """
        project_file = self.projects_path / f"{project.id}.json"

        # Create temp file in same directory (ensures same filesystem for rename)
        fd, temp_path = tempfile.mkstemp(
            suffix=".tmp",
            prefix=f"project_{project.id}_",
            dir=self.projects_path,
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(project.model_dump_json(indent=2))

            # Atomic rename
            os.replace(temp_path, project_file)

            # Update cache
            self._projects[project.id] = project

        except Exception:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
