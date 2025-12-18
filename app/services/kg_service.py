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
import csv
import json
import logging
import os
import shutil
import tempfile
import zipfile
from collections import OrderedDict
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    UserMessage,
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
    BOOTSTRAP_DATA_MARKER,
    BOOTSTRAP_TOOL_NAMES,
    create_bootstrap_mcp_server,
)
from app.kg.tools.extraction import (
    EXTRACTION_DATA_MARKER,
    EXTRACTION_TOOL_NAMES,
    create_extraction_mcp_server,
)

logger = logging.getLogger(__name__)


def _extract_marked_content(
    content: str | list[Any] | None,
    marker: str,
    source: str = "",
) -> dict[str, Any] | None:
    """
    Extract JSON data from tool result content marked with a prefix.

    This generic helper is used by both bootstrap and extraction phases to parse
    data embedded in Claude Agent SDK tool result content blocks. Data is embedded
    with a marker prefix because the SDK strips custom top-level keys.

    Args:
        content: ToolResultBlock.content - can be string or list of blocks
        marker: The prefix marker to look for (e.g., BOOTSTRAP_DATA_MARKER)
        source: Debug label for logging

    Returns:
        Parsed JSON dict if found, None otherwise
    """
    if content is None:
        return None

    # ToolResultBlock.content can be string or list[dict]
    if isinstance(content, str):
        # Single string content - check for marker
        if content.startswith(marker):
            try:
                json_str = content[len(marker) :]
                payload = json.loads(json_str)
                logger.debug(f"Extracted marked content ({source})")
                return payload
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse marked JSON: {e}")
        return None

    # List of content blocks
    if not isinstance(content, list):
        logger.debug(f"Unexpected content type: {type(content)}")
        return None

    for i, block in enumerate(content):
        text = None
        # Handle dict block
        if isinstance(block, dict):
            if block.get("type") == "text":
                text = block.get("text", "")
        # Handle object block
        elif hasattr(block, "type"):
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text = getattr(block, "text", "")

        if text and text.startswith(marker):
            try:
                json_str = text[len(marker) :]
                payload = json.loads(json_str)
                logger.debug(f"Extracted marked content ({source}[{i}])")
                return payload
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse marked JSON: {e}")

    return None


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

    async def delete_project(self, project_id: str) -> bool:
        """
        Delete a KG project and its associated data.

        Removes:
        - Project from in-memory cache
        - Project JSON file from disk
        - Associated KnowledgeBase directory (if exists)

        Args:
            project_id: 12-character project identifier

        Returns:
            True if project was deleted, False if not found
        """
        # Get project to find associated KB
        project = await self.get_project(project_id)
        if not project:
            return False

        # Remove from cache
        if project_id in self._projects:
            del self._projects[project_id]

        # Delete project JSON file
        project_file = self.projects_path / f"{project_id}.json"
        if project_file.exists():
            project_file.unlink()
            logger.info(f"Deleted project file: {project_file}")

        # Delete associated KnowledgeBase if exists (async to avoid blocking)
        if project.kb_id:
            kb_dir = self.kb_path / project.kb_id
            if kb_dir.exists() and kb_dir.is_dir():
                await asyncio.to_thread(shutil.rmtree, kb_dir)
                logger.info(f"Deleted knowledge base: {kb_dir}")

        logger.info(f"Deleted KG project: {project_id} ({project.name})")
        return True

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

        # Validate project state - only CREATED projects can be bootstrapped
        if project.state != ProjectState.CREATED:
            if project.state == ProjectState.BOOTSTRAPPING:
                raise ValueError(
                    f"Project {project_id} is already bootstrapping. "
                    "Wait for current bootstrap to complete or fail."
                )
            else:
                raise ValueError(
                    f"Project {project_id} is not in CREATED state "
                    f"(current: {project.state.value}). Only new projects can be bootstrapped."
                )

        # Update state to bootstrapping
        project.state = ProjectState.BOOTSTRAPPING
        project.error = None
        await self._save_project(project)

        logger.info(f"Starting bootstrap for project {project_id}")

        try:
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

            # Collect bootstrap data from message stream
            # NOTE: Claude Agent SDK strips custom top-level keys from tool responses.
            # Bootstrap data is embedded as JSON in content blocks with a marker prefix.
            #
            # Per SDK docs (04_API_REFERENCE.md):
            # - ResultMessage does NOT have tool_results (only result, num_turns, etc.)
            # - Tool results are in AssistantMessage.content as ToolResultBlock objects
            # - ToolResultBlock.content contains the actual tool output
            bootstrap_data: dict[str, Any] = {}

            def _collect_bootstrap_step(
                content: str | list[Any] | None, source: str = ""
            ) -> None:
                """Extract bootstrap step data from tool result content."""
                payload = _extract_marked_content(
                    content, BOOTSTRAP_DATA_MARKER, source
                )
                if payload:
                    step = payload.get("step")
                    data = payload.get("data")
                    if step and data is not None:
                        bootstrap_data[step] = data
                        logger.info(f"Collected bootstrap step: {step} ({source})")

            # Run Claude to perform bootstrap analysis (with concurrency limit)
            async with self._claude_semaphore:
                async with ClaudeSDKClient(options) as client:
                    await client.query(prompt)

                    message_count = 0
                    # Process messages and collect bootstrap data from content blocks
                    async for message in client.receive_response():
                        message_count += 1
                        msg_type = type(message).__name__
                        logger.debug(f"Message #{message_count}: {msg_type}")

                        if isinstance(message, ResultMessage):
                            if message.is_error:
                                raise RuntimeError(
                                    f"Bootstrap agent error: {message.result}"
                                )
                            logger.info(
                                f"Bootstrap completed in {message.num_turns} turns, "
                                f"cost: ${message.total_cost_usd or 0:.4f}"
                            )
                            # Log ResultMessage attributes for debugging
                            logger.debug(
                                f"ResultMessage attrs: {[a for a in dir(message) if not a.startswith('_')]}"
                            )

                        elif isinstance(message, UserMessage):
                            # Tool results are in UserMessage.content as ToolResultBlock
                            # (SDK sends tool results as UserMessage, simulating user response)
                            content_blocks = getattr(message, "content", None) or []
                            logger.debug(
                                f"UserMessage has {len(content_blocks)} content blocks"
                            )

                            for idx, block in enumerate(content_blocks):
                                block_type = getattr(block, "type", None)
                                block_class = type(block).__name__
                                logger.debug(
                                    f"  Block[{idx}]: type={block_type}, "
                                    f"class={block_class}"
                                )

                                # ToolResultBlock contains the tool output
                                if block_class == "ToolResultBlock":
                                    tool_content = getattr(block, "content", None)
                                    logger.debug(
                                        f"    ToolResult content type: {type(tool_content)}, "
                                        f"preview: {str(tool_content)[:200] if tool_content else 'None'}..."
                                    )
                                    _collect_bootstrap_step(
                                        tool_content, f"UserMsg.block[{idx}]"
                                    )

                    logger.info(
                        f"Processed {message_count} messages, "
                        f"collected {len(bootstrap_data)} bootstrap steps"
                    )

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

            # Note: bootstrap_data (local dict) is automatically garbage collected.
            # Project state is restored to CREATED, allowing retry.
            logger.error(
                f"Bootstrap failed for project {project_id}: {e}. "
                f"State restored to CREATED, partial data cleaned up."
            )
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

        def _collect_extraction_result(
            content: str | list[Any] | None, source: str = ""
        ) -> None:
            """Extract and validate extraction result from tool result content."""
            nonlocal extraction_result
            payload = _extract_marked_content(content, EXTRACTION_DATA_MARKER, source)
            if payload:
                try:
                    extraction_result = ExtractionResult.model_validate(payload)
                    logger.info(f"Extracted extraction result ({source})")
                except Exception as e:
                    logger.warning(f"Failed to validate extraction result: {e}")

        try:
            # Run extraction with concurrency limit
            async with self._claude_semaphore:
                async with ClaudeSDKClient(options) as client:
                    await client.query(prompt)

                    message_count = 0
                    # Process messages - tool results are in UserMessage.content
                    async for message in client.receive_response():
                        message_count += 1

                        if isinstance(message, ResultMessage):
                            if message.is_error:
                                raise RuntimeError(
                                    f"Extraction agent error: {message.result}"
                                )
                            logger.info(
                                f"Extraction completed in {message.num_turns} turns, "
                                f"cost: ${message.total_cost_usd or 0:.4f}"
                            )

                        elif isinstance(message, UserMessage):
                            # Tool results are in UserMessage.content as ToolResultBlock
                            # (SDK sends tool results as UserMessage)
                            content_blocks = getattr(message, "content", None) or []
                            for idx, block in enumerate(content_blocks):
                                block_class = type(block).__name__
                                if block_class == "ToolResultBlock":
                                    tool_content = getattr(block, "content", None)
                                    _collect_extraction_result(
                                        tool_content, f"UserMsg.block[{idx}]"
                                    )

                    logger.debug(f"Processed {message_count} extraction messages")

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
        export_format: str = "graphml",
    ) -> Path | None:
        """
        Export a project's knowledge graph to file.

        Supports GraphML, JSON, and CSV formats. CSV export creates a ZIP
        file containing nodes.csv and edges.csv.

        Args:
            project_id: ID of the project to export
            export_format: Export format - "graphml", "json", or "csv"

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

        output_file = export_path / f"{project_id}.{export_format}"

        if export_format == "graphml":
            export_graphml(kb, output_file)
        elif export_format == "csv":
            output_file = self._export_csv(kb, project_id, export_path)
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

    def _export_csv(
        self, kb: KnowledgeBase, project_id: str, export_path: Path
    ) -> Path:
        """
        Export knowledge base to CSV format inside a ZIP file.

        Creates a ZIP file containing nodes.csv and edges.csv.

        Args:
            kb: KnowledgeBase to export
            project_id: Project identifier for filename
            export_path: Directory to write export file

        Returns:
            Path to the created ZIP file
        """
        zip_file = export_path / f"{project_id}.csv.zip"

        with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zf:
            # Export nodes.csv
            nodes_csv = self._create_nodes_csv(kb)
            zf.writestr("nodes.csv", nodes_csv)

            # Export edges.csv
            edges_csv = self._create_edges_csv(kb)
            zf.writestr("edges.csv", edges_csv)

        return zip_file

    def _create_nodes_csv(self, kb: KnowledgeBase) -> str:
        """
        Create CSV content for nodes.

        Generates a CSV string with the following columns:
        - id: Unique node identifier (UUID)
        - label: Display name for the node
        - entity_type: Type category (Person, Organization, etc.)
        - aliases: Semicolon-separated alternative names
        - description: Node description text
        - source_ids: Semicolon-separated source video IDs

        Args:
            kb: KnowledgeBase to export nodes from

        Returns:
            CSV-formatted string with header row and node data
        """
        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(
            ["id", "label", "entity_type", "aliases", "description", "source_ids"]
        )

        # Write node rows
        for node in kb._nodes.values():
            writer.writerow(
                [
                    node.id,
                    node.label,
                    node.entity_type,
                    ";".join(node.aliases) if node.aliases else "",
                    node.description or "",
                    ";".join(node.source_ids) if node.source_ids else "",
                ]
            )

        return output.getvalue()

    def _create_edges_csv(self, kb: KnowledgeBase) -> str:
        """
        Create CSV content for edges.

        Generates a CSV string with the following columns:
        - id: Unique edge identifier (UUID)
        - source_node_id: ID of the source node
        - target_node_id: ID of the target node
        - relationship_type: Primary relationship type
        - relationship_types: Semicolon-separated all relationship types
        - source_ids: Semicolon-separated source video IDs

        Args:
            kb: KnowledgeBase to export edges from

        Returns:
            CSV-formatted string with header row and edge data
        """
        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(
            [
                "id",
                "source_node_id",
                "target_node_id",
                "relationship_type",
                "relationship_types",
                "source_ids",
            ]
        )

        # Write edge rows
        for edge in kb._edges.values():
            rel_types = edge.get_relationship_types()
            primary_type = rel_types[0] if rel_types else ""
            source_ids = set()
            for rel in edge.relationships:
                source_ids.add(rel.source_id)

            writer.writerow(
                [
                    edge.id,
                    edge.source_node_id,
                    edge.target_node_id,
                    primary_type,
                    ";".join(rel_types),
                    ";".join(sorted(source_ids)),
                ]
            )

        return output.getvalue()

    async def batch_export_graphs(
        self, project_ids: list[str], export_format: str = "graphml"
    ) -> Path | None:
        """
        Export multiple projects to a single ZIP file.

        Each project gets its own subfolder named by project ID.
        Invalid or missing projects are skipped with a warning.

        Args:
            project_ids: List of project IDs to export
            export_format: Export format - "graphml", "json", or "csv"

        Returns:
            Path to the ZIP file, or None if no projects could be exported
        """
        if not project_ids:
            return None

        # Create exports directory
        export_path = self.data_path / "exports"
        export_path.mkdir(parents=True, exist_ok=True)

        # Create batch export ZIP
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        export_timestamp_iso = datetime.now(timezone.utc).isoformat()
        zip_file = export_path / f"batch_export_{timestamp}.zip"

        exported_count = 0
        exported_projects: list[dict[str, str]] = []

        with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for project_id in project_ids:
                try:
                    project = await self.get_project(project_id)
                    if not project or not project.kb_id:
                        logger.warning(
                            f"Skipping project {project_id}: no graph data"
                        )
                        continue

                    kb = load_knowledge_base(self.kb_path / project.kb_id)
                    if not kb:
                        logger.warning(
                            f"Skipping project {project_id}: KB not found"
                        )
                        continue

                    # Export based on format
                    if export_format == "graphml":
                        content = self._create_graphml_content(kb)
                        zf.writestr(
                            f"{project_id}/{project_id}.graphml", content
                        )
                    elif export_format == "csv":
                        zf.writestr(
                            f"{project_id}/nodes.csv", self._create_nodes_csv(kb)
                        )
                        zf.writestr(
                            f"{project_id}/edges.csv", self._create_edges_csv(kb)
                        )
                    else:  # json
                        data = {
                            "nodes": [n.model_dump() for n in kb._nodes.values()],
                            "edges": [e.model_dump() for e in kb._edges.values()],
                            "sources": [
                                s.model_dump() for s in kb._sources.values()
                            ],
                        }
                        zf.writestr(
                            f"{project_id}/{project_id}.json",
                            json.dumps(data, indent=2, default=str),
                        )

                    exported_count += 1
                    exported_projects.append({
                        "project_id": project_id,
                        "name": project.name,
                    })
                    logger.info(f"Added project {project_id} to batch export")

                except Exception as e:
                    logger.error(
                        f"Error exporting project {project_id}: {e}", exc_info=True
                    )
                    continue

            # Add manifest.json with export metadata
            if exported_count > 0:
                manifest = {
                    "export_timestamp": export_timestamp_iso,
                    "format": export_format,
                    "format_version": "1.0",
                    "project_count": exported_count,
                    "projects": exported_projects,
                }
                zf.writestr(
                    "manifest.json",
                    json.dumps(manifest, indent=2),
                )

        if exported_count == 0:
            # Remove empty ZIP file
            zip_file.unlink()
            return None

        logger.info(
            f"Batch exported {exported_count} projects to {zip_file.name}"
        )
        return zip_file

    def _create_graphml_content(self, kb: KnowledgeBase) -> str:
        """Create GraphML content as string."""
        # Use a temporary file to generate GraphML
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".graphml", delete=False
        ) as tmp:
            tmp_path = Path(tmp.name)

        try:
            export_graphml(kb, tmp_path)
            content = tmp_path.read_text()
            return content
        finally:
            tmp_path.unlink()

    async def cleanup_old_exports(self) -> int:
        """
        Remove export files older than the configured TTL.

        Called periodically to prevent disk space buildup from
        old export files. Uses APP_EXPORT_TTL_HOURS setting.

        Returns:
            Number of files deleted
        """
        settings = get_settings()
        export_path = self.data_path / "exports"

        if not export_path.exists():
            return 0

        ttl_seconds = settings.export_ttl_hours * 3600
        now = datetime.now(timezone.utc).timestamp()
        deleted_count = 0

        for file_path in export_path.iterdir():
            if not file_path.is_file():
                continue

            try:
                file_age = now - file_path.stat().st_mtime
                if file_age > ttl_seconds:
                    file_path.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted old export: {file_path.name}")
            except OSError as e:
                logger.warning(f"Failed to delete old export {file_path}: {e}")

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old export files")

        return deleted_count

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
