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
import time
import zipfile
from collections import OrderedDict
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    UserMessage,
)

from app.core.config import get_settings
from app.models.audit import AuditEventType

if TYPE_CHECKING:
    from app.services.audit_service import AuditService
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
from app.kg.models import Node, Source, SourceType
from app.kg.persistence import export_graphml, load_knowledge_base, save_knowledge_base
from app.kg.prompts.bootstrap_prompt import BOOTSTRAP_SYSTEM_PROMPT
from app.kg.prompts.templates import generate_extraction_prompt
from app.kg.resolution import MergeHistory, ResolutionCandidate, ResolutionConfig
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

    def __init__(
        self,
        data_path: Path,
        audit_service: AuditService | None = None,
    ) -> None:
        """
        Initialize Knowledge Graph Service.

        Args:
            data_path: Base directory for data storage (e.g., Path("data"))
            audit_service: Optional audit service for logging resolution events
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

        # Per-merge locks to prevent concurrent merges on the same node pair
        self._pending_merges: dict[str, asyncio.Lock] = {}

        # Bootstrap MCP server (created once, reused)
        self._bootstrap_server = create_bootstrap_mcp_server()

        # Extraction MCP server (created once, reused)
        self._extraction_server = create_extraction_mcp_server()

        # Optional audit service for resolution event logging
        self._audit_service = audit_service

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
        transcript_id: str | None = None,
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
            transcript_id: Optional transcript ID for evidence linking (from save_transcript).
                           If not provided, auto-detection by title is attempted.

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

        # Add source to KB with transcript_id for evidence linking
        # Auto-detect transcript_id if not provided by matching the title against saved transcripts
        logger.debug(
            f"Evidence linking setup: transcript_id={transcript_id!r}, title={title!r}"
        )

        resolved_transcript_id = transcript_id
        if not resolved_transcript_id and title:
            resolved_transcript_id = self._find_transcript_by_title(title)
            if resolved_transcript_id:
                logger.debug(
                    f"Auto-detected transcript_id='{resolved_transcript_id}' for '{title}'"
                )
            else:
                logger.debug(f"Could not auto-detect transcript_id for title '{title}'")

        source_metadata: dict[str, Any] = {}
        if resolved_transcript_id:
            source_metadata["transcript_id"] = resolved_transcript_id
            logger.debug(f"Set source.metadata['transcript_id'] = {resolved_transcript_id}")
        else:
            logger.warning("No transcript_id resolved - evidence linking will not work")

        source = Source(
            id=source_id, title=title, source_type=SourceType.VIDEO, metadata=source_metadata
        )
        logger.debug(
            f"Created Source: id={source.id}, title={source.title}, metadata={source.metadata}"
        )
        kb.add_source(source)

        # Apply extraction results to KB
        newly_added_nodes = self._apply_extraction_to_kb(kb, extraction_result, source_id)

        # Proactive entity resolution for newly added nodes
        auto_merge_count = 0
        review_count = 0
        config = project.resolution_config

        for new_node in newly_added_nodes:
            # Check if new node still exists (may have been merged already)
            if kb.get_node(new_node.id) is None:
                continue

            candidates = kb.find_candidates_for_node(new_node, config)
            for candidate in candidates:
                # Skip if either node no longer exists
                if kb.get_node(candidate.node_a_id) is None:
                    continue
                if kb.get_node(candidate.node_b_id) is None:
                    continue

                if candidate.confidence >= config.auto_merge_threshold:
                    # Auto-merge high confidence matches
                    try:
                        # new_node.id is node_a_id, merge it into the existing node
                        history = kb.merge_nodes(
                            survivor_id=candidate.node_b_id,
                            merged_id=candidate.node_a_id,
                            merge_type="auto",
                        )
                        history.confidence = candidate.confidence
                        project.merge_history.append(history)
                        auto_merge_count += 1
                        logger.debug(
                            f"Auto-merged new node {new_node.label} into existing "
                            f"node {candidate.node_b_id} (confidence: {candidate.confidence:.2f})"
                        )
                        # Node was merged, stop looking for more candidates
                        break
                    except ValueError:
                        # Node disappeared during processing
                        continue
                elif candidate.confidence >= config.review_threshold:
                    # Queue for user review (avoid duplicates)
                    already_pending = any(
                        pm.node_a_id == candidate.node_a_id
                        and pm.node_b_id == candidate.node_b_id
                        for pm in project.pending_merges
                    )
                    if not already_pending:
                        project.pending_merges.append(candidate)
                        review_count += 1

        if auto_merge_count > 0 or review_count > 0:
            logger.info(
                f"Proactive resolution: {auto_merge_count} auto-merges, "
                f"{review_count} candidates queued for review"
            )

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
    ) -> list[Node]:
        """
        Apply extraction results to a knowledge base.

        Creates or updates nodes for each entity and adds relationships
        between them. Handles alias merging for existing entities.

        Args:
            kb: KnowledgeBase to update
            result: ExtractionResult containing entities and relationships
            source_id: ID of the source for provenance tracking

        Returns:
            List of newly created Node objects (for resolution check)
        """
        newly_added_nodes: list[Node] = []

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

            if created:
                newly_added_nodes.append(node)

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

        return newly_added_nodes

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

    def _find_transcript_by_title(self, search_title: str) -> str | None:
        """
        Find a saved transcript by matching its title.

        Uses the title field stored in transcript metadata during save_transcript.
        Supports exact match and fuzzy substring matching.

        Args:
            search_title: Title to search for (e.g., "The Search")

        Returns:
            Transcript ID if found, None otherwise
        """
        from app.services import get_services

        logger.debug(f"Searching for transcript by title: {search_title!r}")

        if not search_title or not search_title.strip():
            return None

        try:
            storage = get_services().storage
            transcripts = storage.list_transcripts()

            logger.debug(f"Searching {len(transcripts)} transcripts for title match")

            search_normalized = search_title.strip().lower()

            # First pass: exact match on title field
            for t in transcripts:
                if t.title and t.title.strip().lower() == search_normalized:
                    logger.debug(f"Exact title match found: id={t.id}")
                    return t.id

            # Second pass: fuzzy match (one contains the other)
            for t in transcripts:
                if t.title:
                    saved_normalized = t.title.strip().lower()
                    if search_normalized in saved_normalized or saved_normalized in search_normalized:
                        logger.debug(f"Fuzzy title match found: id={t.id}")
                        return t.id

            logger.debug("No title match found")
            return None
        except Exception as e:
            logger.warning(f"Failed to search transcripts by title: {e}")
            return None

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
                        logger.warning(f"Skipping project {project_id}: no graph data")
                        continue

                    kb = load_knowledge_base(self.kb_path / project.kb_id)
                    if not kb:
                        logger.warning(f"Skipping project {project_id}: KB not found")
                        continue

                    # Export based on format
                    if export_format == "graphml":
                        content = self._create_graphml_content(kb)
                        zf.writestr(f"{project_id}/{project_id}.graphml", content)
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
                            "sources": [s.model_dump() for s in kb._sources.values()],
                        }
                        zf.writestr(
                            f"{project_id}/{project_id}.json",
                            json.dumps(data, indent=2, default=str),
                        )

                    exported_count += 1
                    exported_projects.append(
                        {
                            "project_id": project_id,
                            "name": project.name,
                        }
                    )
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

        logger.info(f"Batch exported {exported_count} projects to {zip_file.name}")
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

    async def get_knowledge_base(self, project_id: str) -> KnowledgeBase | None:
        """
        Get the knowledge base for a project.

        Loads the KnowledgeBase from disk if it exists. Used for
        insight queries and graph analysis operations.

        Args:
            project_id: ID of the project

        Returns:
            KnowledgeBase if found, None otherwise
        """
        project = await self.get_project(project_id)
        if not project or not project.kb_id:
            return None

        return load_knowledge_base(self.kb_path / project.kb_id)

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

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ENTITY RESOLUTION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def scan_for_duplicates(
        self,
        project_id: str,
        config: ResolutionConfig | None = None,
    ) -> list[ResolutionCandidate]:
        """
        On-demand batch scan for duplicate entities in a project.

        Scans the project's knowledge base for potential duplicate entities
        using the EntityMatcher algorithm. Returns candidates sorted by
        confidence (highest first).

        Args:
            project_id: Target project ID
            config: Optional ResolutionConfig to override project defaults

        Returns:
            List of ResolutionCandidate objects sorted by confidence (desc)

        Raises:
            ValueError: If project not found or has no knowledge base
        """
        # Check feature flag
        settings = get_settings()
        if not settings.entity_resolution_enabled:
            logger.info(f"Resolution disabled for project {project_id}")
            return []

        start_time = time.perf_counter()

        project = await self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        if not project.kb_id:
            raise ValueError(f"Project {project_id} has no knowledge base")

        kb = load_knowledge_base(self.kb_path / project.kb_id)
        if not kb:
            raise ValueError(f"Knowledge base not found for project {project_id}")

        # Use provided config or project's default
        resolution_config = config or project.resolution_config
        candidates = kb.find_resolution_candidates(resolution_config)

        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            f"Resolution scan complete: project={project_id} "
            f"candidates={len(candidates)} duration_ms={duration_ms:.1f}"
        )

        # Emit audit event if service available
        if self._audit_service:
            await self._audit_service.log_resolution_event(
                event_type=AuditEventType.RESOLUTION_SCAN_COMPLETE,
                project_id=project_id,
                candidates_found=len(candidates),
                scan_duration_ms=duration_ms,
            )

        return candidates

    async def _find_merge_by_request_id(
        self, project_id: str, request_id: str
    ) -> MergeHistory | None:
        """
        Find existing merge by idempotency key.

        Searches the project's merge history for a merge with the
        matching request_id.

        Args:
            project_id: Target project ID
            request_id: The idempotency key to search for

        Returns:
            MergeHistory if found, None otherwise
        """
        project = await self.get_project(project_id)
        if not project:
            return None
        for history in project.merge_history:
            if history.request_id == request_id:
                return history
        return None

    def _capture_edges_state(
        self, project: KGProject, node_id: str
    ) -> list[dict[str, Any]]:
        """
        Capture edges for a node before merge (for rollback).

        Loads the knowledge base and retrieves all edges connected
        to the specified node.

        Args:
            project: The KGProject containing the knowledge base
            node_id: ID of the node to capture edges for

        Returns:
            List of edge dictionaries serialized via model_dump()
        """
        if not project.kb_id:
            return []

        kb = load_knowledge_base(self.kb_path / project.kb_id)
        if not kb:
            return []

        edges = kb.get_edges_for_node(node_id)
        return [edge.model_dump() for edge in edges]

    async def merge_entities(
        self,
        project_id: str,
        survivor_id: str,
        merged_id: str,
        merge_type: str = "user",
        session_id: str | None = None,
        request_id: str | None = None,
        confidence: float = 1.0,
    ) -> MergeHistory:
        """
        Execute merge with idempotency and safety controls.

        Merges two entities in the knowledge base, with the survivor node
        absorbing the merged node's aliases, edges, and properties. Includes
        idempotency checks and pre-merge state capture for rollback support.

        Args:
            project_id: Target project ID
            survivor_id: ID of node to keep
            merged_id: ID of node to merge into survivor
            merge_type: How merge was triggered (auto, user, agent)
            session_id: Optional session ID for agent merges
            request_id: Optional idempotency key for duplicate detection
            confidence: Confidence score for this merge (0.0-1.0)

        Returns:
            MergeHistory record with audit information and safety data

        Raises:
            ValueError: If project not found, no KB, or invalid node IDs
        """
        # Check idempotency - return existing result if request_id matches
        if request_id:
            existing = await self._find_merge_by_request_id(project_id, request_id)
            if existing:
                logger.info(f"Idempotent merge: returning existing {existing.id}")
                return existing

        # Acquire per-node lock to prevent concurrent merges
        lock_key = f"{project_id}:{survivor_id}:{merged_id}"
        if lock_key not in self._pending_merges:
            self._pending_merges[lock_key] = asyncio.Lock()

        async with self._pending_merges[lock_key]:
            project = await self.get_project(project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")

            if not project.kb_id:
                raise ValueError(f"Project {project_id} has no knowledge base")

            kb = load_knowledge_base(self.kb_path / project.kb_id)
            if not kb:
                raise ValueError(f"Knowledge base not found for project {project_id}")

            # Get nodes
            survivor = kb.get_node(survivor_id)
            merged = kb.get_node(merged_id)

            if not survivor or not merged:
                raise ValueError("One or both nodes not found")

            # Capture pre-merge state for rollback
            pre_merge_state = {
                "survivor": survivor.model_dump(),
                "merged": merged.model_dump(),
                "edges": self._capture_edges_state(project, merged_id),
            }
            survivor_label_before = survivor.label
            survivor_aliases_before = list(survivor.aliases)
            edges_redirected = len(pre_merge_state["edges"])

            # Execute the merge in the KB
            history = kb.merge_nodes(
                survivor_id=survivor_id,
                merged_id=merged_id,
                merge_type=merge_type,
                merged_by=session_id,
            )

            # Attach safety data
            history.request_id = request_id
            history.pre_merge_state = pre_merge_state
            history.survivor_label_before = survivor_label_before
            history.survivor_aliases_before = survivor_aliases_before
            history.edges_redirected = edges_redirected
            history.confidence = confidence

            # Append to project's merge history
            project.merge_history.append(history)

            # Remove any pending merges involving the merged node
            project.pending_merges = [
                pm
                for pm in project.pending_merges
                if pm.node_a_id != merged_id and pm.node_b_id != merged_id
            ]

            # Update project stats
            stats = kb.stats()
            project.thing_count = stats["node_count"]
            project.connection_count = stats["edge_count"]
            project.updated_at = _utc_now()

            # Save KB and project
            save_knowledge_base(kb, self.kb_path)
            await self._save_project(project)

            # Clean up lock
            self._pending_merges.pop(lock_key, None)

            logger.info(
                f"Merged entities in project {project_id}: "
                f"{merged_id} -> {survivor_id} (type: {merge_type})"
            )

            return history

    async def check_merge_conflicts(
        self,
        project_id: str,
        candidate_id: str,
    ) -> dict[str, Any]:
        """
        Check if a merge candidate has conflicts.

        Detects potential issues that might make a merge problematic:
        1. Node was already merged (doesn't exist)
        2. Candidate involves high-relationship nodes (>10 edges)

        Args:
            project_id: Target project ID
            candidate_id: ID of the resolution candidate to check

        Returns:
            Dict with conflict status:
            - conflict: True if merge cannot proceed
            - warning: True if merge is risky but possible
            - reason: Explanation of the conflict or warning
        """
        project = await self.get_project(project_id)
        if not project:
            return {"conflict": True, "reason": "Project not found"}

        # Find candidate
        candidate = None
        for c in project.pending_merges:
            if c.id == candidate_id:
                candidate = c
                break

        if not candidate:
            return {"conflict": True, "reason": "Candidate not found"}

        if not project.kb_id:
            return {"conflict": True, "reason": "No knowledge base"}

        kb = load_knowledge_base(self.kb_path / project.kb_id)
        if not kb:
            return {"conflict": True, "reason": "Knowledge base not found"}

        node_a = kb.get_node(candidate.node_a_id)
        node_b = kb.get_node(candidate.node_b_id)

        if not node_a or not node_b:
            return {"conflict": True, "reason": "Node was already merged"}

        # Check relationship count
        edges_a = len(kb.get_edges_for_node(candidate.node_a_id))
        edges_b = len(kb.get_edges_for_node(candidate.node_b_id))

        if edges_a + edges_b > 10:
            return {
                "conflict": False,
                "warning": True,
                "reason": f"High-impact merge: {edges_a + edges_b} relationships affected",
            }

        return {"conflict": False, "warning": False}

    async def review_merge_candidate(
        self,
        project_id: str,
        candidate_id: str,
        approved: bool,
        session_id: str | None = None,
    ) -> ResolutionCandidate | MergeHistory:
        """
        Approve or reject a pending merge candidate.

        If approved, executes the merge and returns a MergeHistory record.
        If rejected, updates the candidate status and returns it.

        Args:
            project_id: Target project ID
            candidate_id: 8-character candidate identifier
            approved: True to merge, False to reject
            session_id: Optional session ID for agent approvals

        Returns:
            MergeHistory if approved, ResolutionCandidate if rejected

        Raises:
            ValueError: If project not found or candidate not in pending list
        """
        project = await self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Find candidate in pending merges
        candidate: ResolutionCandidate | None = None
        candidate_idx: int = -1
        for idx, pm in enumerate(project.pending_merges):
            if pm.id == candidate_id:
                candidate = pm
                candidate_idx = idx
                break

        if candidate is None:
            raise ValueError(f"Candidate {candidate_id} not found in pending merges")

        # Remove from pending list
        project.pending_merges.pop(candidate_idx)

        if approved:
            # Execute the merge
            history = await self.merge_entities(
                project_id=project_id,
                survivor_id=candidate.node_a_id,
                merged_id=candidate.node_b_id,
                merge_type="user",
                session_id=session_id,
            )
            # Update confidence from candidate
            history.confidence = candidate.confidence

            logger.info(
                f"Approved merge candidate {candidate_id} in project {project_id}"
            )
            return history
        else:
            # Mark as rejected
            candidate.status = "rejected"
            project.updated_at = _utc_now()
            await self._save_project(project)

            logger.info(
                f"Rejected merge candidate {candidate_id} in project {project_id}"
            )
            return candidate

    async def get_pending_merges(
        self,
        project_id: str,
    ) -> list[ResolutionCandidate]:
        """
        Get all pending merge candidates for a project.

        Returns the list of resolution candidates that are awaiting
        user review (not yet approved or rejected).

        Args:
            project_id: Target project ID

        Returns:
            List of pending ResolutionCandidate objects
        """
        project = await self.get_project(project_id)
        if not project:
            return []

        return project.pending_merges

    async def get_merge_history(
        self,
        project_id: str,
    ) -> list[MergeHistory]:
        """
        Get merge audit trail for a project.

        Returns the complete history of all merges that have been
        executed on this project, ordered by merge time.

        Args:
            project_id: Target project ID

        Returns:
            List of MergeHistory records
        """
        project = await self.get_project(project_id)
        if not project:
            return []

        return project.merge_history

    async def compare_entities_semantic(
        self,
        project_id: str,
        node_a_id: str,
        node_b_id: str,
    ) -> dict[str, Any]:
        """
        Compare two entities using basic similarity metrics.

        Provides a comparison summary including label similarity,
        alias overlap, type matching, and shared neighbors.

        Note: Full semantic comparison via Claude is a future enhancement.
        This stub returns basic comparison data.

        Args:
            project_id: Target project ID
            node_a_id: ID of first node to compare
            node_b_id: ID of second node to compare

        Returns:
            Dict with comparison data including similarity scores

        Raises:
            ValueError: If project not found, no KB, or invalid node IDs
        """
        project = await self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        if not project.kb_id:
            raise ValueError(f"Project {project_id} has no knowledge base")

        kb = load_knowledge_base(self.kb_path / project.kb_id)
        if not kb:
            raise ValueError(f"Knowledge base not found for project {project_id}")

        node_a = kb.get_node(node_a_id)
        node_b = kb.get_node(node_b_id)

        if not node_a:
            raise ValueError(f"Node {node_a_id} not found")
        if not node_b:
            raise ValueError(f"Node {node_b_id} not found")

        # Use EntityMatcher to compute similarity
        from app.kg.resolution import EntityMatcher

        matcher = EntityMatcher(project.resolution_config)
        confidence, signals = matcher.compute_similarity(node_a, node_b, kb)

        # Get shared neighbors
        neighbors_a = {n.id for n in kb.get_neighbors(node_a_id)}
        neighbors_b = {n.id for n in kb.get_neighbors(node_b_id)}
        shared_neighbors = neighbors_a & neighbors_b
        shared_neighbor_labels: list[str] = []
        for nid in shared_neighbors:
            neighbor_node = kb.get_node(nid)
            if neighbor_node:
                shared_neighbor_labels.append(neighbor_node.label)

        return {
            "node_a": {
                "id": node_a.id,
                "label": node_a.label,
                "entity_type": node_a.entity_type,
                "aliases": list(node_a.aliases),
            },
            "node_b": {
                "id": node_b.id,
                "label": node_b.label,
                "entity_type": node_b.entity_type,
                "aliases": list(node_b.aliases),
            },
            "confidence": confidence,
            "signals": signals,
            "shared_neighbors": shared_neighbor_labels,
            "same_type": node_a.entity_type == node_b.entity_type,
        }
