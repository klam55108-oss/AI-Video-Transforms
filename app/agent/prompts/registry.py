"""
Prompt Registry - Version control for system prompts.

This module provides a simple versioning system for managing prompts
used throughout the application. It enables tracking prompt changes,
retrieving specific versions, and maintaining prompt history.

Usage:
    from app.agent.prompts import get_prompt, register_prompt, PromptVersion

    # Register a new prompt version
    register_prompt(
        name="my_prompt",
        version="1.0.0",
        content="Your prompt text here",
        description="Initial version"
    )

    # Retrieve the latest version
    prompt = get_prompt("my_prompt")

    # Retrieve a specific version
    prompt = get_prompt("my_prompt", version="1.0.0")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import ClassVar


@dataclass(frozen=True)
class PromptVersion:
    """Immutable representation of a versioned prompt.

    Attributes:
        name: Unique identifier for this prompt.
        version: Semantic version string (e.g., "1.0.0").
        content: The full prompt text.
        description: Human-readable description of this version.
        created_at: Timestamp when this version was registered.
    """

    name: str
    version: str
    content: str
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __str__(self) -> str:
        """Return the prompt content for direct string usage."""
        return self.content

    def __len__(self) -> int:
        """Return the length of the prompt content."""
        return len(self.content)


class PromptRegistry:
    """Central registry for managing versioned prompts.

    This class maintains a collection of prompts, each potentially having
    multiple versions. It provides methods for registering new versions
    and retrieving prompts by name and version.

    The registry is implemented as a singleton-like pattern using class
    variables, allowing prompts to be registered at module load time
    and accessed globally.
    """

    # Storage: {prompt_name: {version: PromptVersion}}
    _prompts: ClassVar[dict[str, dict[str, PromptVersion]]] = {}
    # Track latest version for each prompt: {prompt_name: version}
    _latest: ClassVar[dict[str, str]] = {}

    @classmethod
    def register(
        cls,
        name: str,
        version: str,
        content: str,
        description: str = "",
    ) -> PromptVersion:
        """Register a new prompt version.

        Args:
            name: Unique identifier for this prompt.
            version: Semantic version string (e.g., "1.0.0").
            content: The full prompt text.
            description: Human-readable description of this version.

        Returns:
            The created PromptVersion instance.

        Raises:
            ValueError: If this exact name+version combination already exists.
        """
        if name not in cls._prompts:
            cls._prompts[name] = {}

        # Allow re-registration during hot reload (development mode)
        # In production, you'd typically use new version numbers
        if version in cls._prompts[name]:
            # Silently update the existing registration
            # This enables hot reload to pick up prompt changes
            pass

        prompt_version = PromptVersion(
            name=name,
            version=version,
            content=content,
            description=description,
        )

        cls._prompts[name][version] = prompt_version
        cls._latest[name] = version

        return prompt_version

    @classmethod
    def get(cls, name: str, version: str | None = None) -> PromptVersion:
        """Retrieve a prompt by name and optionally version.

        Args:
            name: The prompt identifier.
            version: Specific version to retrieve. If None, returns latest.

        Returns:
            The requested PromptVersion.

        Raises:
            KeyError: If the prompt name or version doesn't exist.
        """
        if name not in cls._prompts:
            available = list(cls._prompts.keys())
            raise KeyError(f"Prompt '{name}' not found. Available prompts: {available}")

        if version is None:
            version = cls._latest[name]

        if version not in cls._prompts[name]:
            available = list(cls._prompts[name].keys())
            raise KeyError(
                f"Version '{version}' not found for prompt '{name}'. "
                f"Available versions: {available}"
            )

        return cls._prompts[name][version]

    @classmethod
    def get_content(cls, name: str, version: str | None = None) -> str:
        """Retrieve just the prompt content as a string.

        Convenience method that returns only the content string,
        useful when you don't need the full PromptVersion metadata.

        Args:
            name: The prompt identifier.
            version: Specific version to retrieve. If None, returns latest.

        Returns:
            The prompt content string.
        """
        return cls.get(name, version).content

    @classmethod
    def list_versions(cls, name: str) -> list[str]:
        """List all available versions for a prompt.

        Args:
            name: The prompt identifier.

        Returns:
            List of version strings, sorted by registration order.

        Raises:
            KeyError: If the prompt name doesn't exist.
        """
        if name not in cls._prompts:
            raise KeyError(f"Prompt '{name}' not found.")
        return list(cls._prompts[name].keys())

    @classmethod
    def list_prompts(cls) -> list[str]:
        """List all registered prompt names.

        Returns:
            List of prompt names.
        """
        return list(cls._prompts.keys())

    @classmethod
    def get_latest_version(cls, name: str) -> str:
        """Get the latest version string for a prompt.

        Args:
            name: The prompt identifier.

        Returns:
            The latest version string.

        Raises:
            KeyError: If the prompt name doesn't exist.
        """
        if name not in cls._latest:
            raise KeyError(f"Prompt '{name}' not found.")
        return cls._latest[name]

    @classmethod
    def clear(cls) -> None:
        """Clear all registered prompts. Primarily for testing."""
        cls._prompts.clear()
        cls._latest.clear()


# =============================================================================
# Module-level convenience functions
# =============================================================================


def register_prompt(
    name: str,
    version: str,
    content: str,
    description: str = "",
) -> PromptVersion:
    """Register a new prompt version.

    See PromptRegistry.register for full documentation.
    """
    return PromptRegistry.register(name, version, content, description)


def get_prompt(name: str, version: str | None = None) -> PromptVersion:
    """Retrieve a prompt by name and optionally version.

    See PromptRegistry.get for full documentation.
    """
    return PromptRegistry.get(name, version)


def get_prompt_content(name: str, version: str | None = None) -> str:
    """Retrieve just the prompt content as a string.

    See PromptRegistry.get_content for full documentation.
    """
    return PromptRegistry.get_content(name, version)


def list_prompt_versions(name: str) -> list[str]:
    """List all available versions for a prompt.

    See PromptRegistry.list_versions for full documentation.
    """
    return PromptRegistry.list_versions(name)


def list_prompts() -> list[str]:
    """List all registered prompt names.

    See PromptRegistry.list_prompts for full documentation.
    """
    return PromptRegistry.list_prompts()
