"""
Gemini 3 Flash async client using Google Gen AI SDK.

This client wraps the Google Gen AI SDK specifically optimized for
Gemini 3 Flash with configurable thinking levels for complex coding tasks.

Gemini 3 Flash is Google's flagship model for speed at frontier intelligence:
- 1,000,000 token context window
- 64,000 max output tokens
- Jan 2025 knowledge cutoff
- Thinking levels: minimal, low, medium, high

Key features:
- Uses google-genai SDK with async support
- Configurable thinking level per request
- Automatic retry with exponential backoff
- Pro-level intelligence at Flash pricing ($0.50/1M input, $3/1M output)
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load environment variables from .env file (project root)
_MODULE_DIR = Path(__file__).parent.resolve()
_PROJECT_ROOT = _MODULE_DIR.parents[
    4
]  # .claude/skills/querying-gemini/scripts/_lib -> project root
_ENV_FILE = _PROJECT_ROOT / ".env"

if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)

DEFAULT_MODEL = "gemini-3-flash-preview"
DEFAULT_TIMEOUT = 300.0  # 5 minutes for complex analysis
MAX_OUTPUT_CHARS = 100_000
MAX_RETRIES = 3
RETRY_DELAY = 1.0


class ThinkingLevel(str, Enum):
    """Thinking levels for Gemini 3 Flash.

    Note: Gemini 3 Flash supports more granular thinking levels than Pro.
    - minimal: matches "no thinking" for most queries
    - low: minimizes latency and cost
    - medium: balanced thinking for most tasks
    - high: maximizes reasoning depth (default)
    """

    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class GeminiResponse:
    """Response from Gemini 3 Flash."""

    success: bool
    output: str
    prompt_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    model: str = DEFAULT_MODEL


class GeminiClient:
    """
    Async client for Gemini 3 Flash via Google Gen AI SDK.

    This client is designed for high-reasoning coding tasks:
    - Code analysis and review
    - Bug detection and fixing
    - Architectural analysis
    - Code generation

    Gemini 3 Flash features:
    - 1M context window for large codebases
    - Pro-level intelligence at Flash speed
    - Superior visual and spatial reasoning
    - Configurable thinking levels
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        default_thinking: ThinkingLevel = ThinkingLevel.HIGH,
    ):
        self.model = model
        self.default_thinking = default_thinking
        self._client: Any | None = None

    @property
    def client(self) -> Any:
        """Lazy-initialize the Google Gen AI client."""
        if self._client is None:
            try:
                from google import genai
            except ImportError as e:
                raise ImportError(
                    "google-genai package is required. Install with: pip install google-genai"
                ) from e

            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get(
                "GOOGLE_API_KEY"
            )
            if not api_key:
                raise ValueError(
                    "GEMINI_API_KEY or GOOGLE_API_KEY environment variable is required. "
                    "Set it in .env or export it."
                )
            self._client = genai.Client(api_key=api_key)
        return self._client

    def is_available(self) -> bool:
        """Check if Google API key is configured."""
        return bool(
            os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        )

    async def query(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        thinking_level: ThinkingLevel | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        model: str | None = None,
    ) -> GeminiResponse:
        """
        Execute a query via Gemini 3 Flash.

        Args:
            prompt: The user prompt/question
            system_prompt: Optional system instructions
            thinking_level: Override default thinking level
            timeout: Request timeout in seconds
            model: Override default model

        Returns:
            GeminiResponse with the model's output
        """
        if not self.is_available():
            return GeminiResponse(
                success=False,
                output="",
                error="GEMINI_API_KEY or GOOGLE_API_KEY not configured. Add it to .env file.",
            )

        level = thinking_level or self.default_thinking
        model = model or self.model

        # Retry logic with exponential backoff
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await asyncio.wait_for(
                    self._make_request(prompt, system_prompt, level, model),
                    timeout=timeout,
                )
                return response
            except asyncio.TimeoutError as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (2**attempt))
            except Exception as e:
                # Check for rate limit errors
                error_str = str(e).lower()
                if "rate" in error_str and "limit" in error_str:
                    last_error = e
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY * (2**attempt) * 2)
                    continue
                # Other API errors
                return GeminiResponse(
                    success=False,
                    output="",
                    error=f"API Error: {str(e)}",
                    model=model,
                )

        return GeminiResponse(
            success=False,
            output="",
            error=f"Request failed after {MAX_RETRIES} retries: {str(last_error)}",
            model=model,
        )

    async def _make_request(
        self,
        prompt: str,
        system_prompt: str | None,
        level: ThinkingLevel,
        model: str,
    ) -> GeminiResponse:
        """Make the actual API request."""
        from google.genai import types

        # Build config with thinking level
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level=level.value),
            system_instruction=system_prompt if system_prompt else None,
        )

        # Use async generate_content
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=model,
            contents=prompt,
            config=config,
        )

        # Extract output text from response
        output_text = ""
        if hasattr(response, "text"):
            output_text = response.text or ""
        elif hasattr(response, "candidates") and response.candidates:
            # Handle structured candidate response
            for candidate in response.candidates:
                if hasattr(candidate, "content") and candidate.content:
                    for part in candidate.content.parts:
                        if hasattr(part, "text"):
                            output_text += part.text

        # Truncate if too long
        if len(output_text) > MAX_OUTPUT_CHARS:
            output_text = output_text[:MAX_OUTPUT_CHARS] + "\n\n[Output truncated]"

        # Extract token usage
        prompt_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            output_tokens = (
                getattr(response.usage_metadata, "candidates_token_count", 0) or 0
            )

        return GeminiResponse(
            success=True,
            output=output_text,
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            model=model,
        )


# Lazy singleton
_client: GeminiClient | None = None


def get_client() -> GeminiClient:
    """Get or create the Gemini 3 Flash client singleton."""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client


def reset_client() -> None:
    """Reset the singleton client (for testing)."""
    global _client
    _client = None
