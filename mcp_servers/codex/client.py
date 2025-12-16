"""
GPT-5.2 async client using OpenAI Responses API.

This client wraps the OpenAI Responses API specifically optimized for
GPT-5.2 with high reasoning effort for complex coding tasks.

GPT-5.2 is OpenAI's flagship model for coding and agentic tasks:
- 400,000 context window
- 128,000 max output tokens
- Aug 2025 knowledge cutoff
- Reasoning effort: none, low, medium, high, xhigh

Key features:
- Uses Responses API (not Chat Completions) for chain-of-thought support
- High reasoning effort by default for thorough analysis
- Configurable reasoning effort per request
- Automatic retry with exponential backoff
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError

# Load environment variables from .env file (project root)
_MODULE_DIR = Path(__file__).parent.resolve()
_PROJECT_ROOT = _MODULE_DIR.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"

if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)

DEFAULT_MODEL = "gpt-5.2"
DEFAULT_TIMEOUT = 300.0  # 5 minutes for complex analysis
MAX_OUTPUT_CHARS = 100_000
MAX_RETRIES = 3
RETRY_DELAY = 1.0


class ReasoningEffort(str, Enum):
    """Reasoning effort levels for GPT-5.2.

    Note: GPT-5.2 defaults to 'none' reasoning, but we use 'high' as default
    for thorough analysis in our tools.
    """

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


@dataclass
class CodexResponse:
    """Response from GPT-5.2."""

    success: bool
    output: str
    reasoning_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    model: str = DEFAULT_MODEL


class CodexClient:
    """
    Async client for GPT-5.2 via OpenAI Responses API.

    This client is designed for high-reasoning coding tasks:
    - Code analysis and review
    - Bug detection and fixing
    - Architectural analysis

    GPT-5.2 features:
    - 400K context window for large codebases
    - Improved instruction following and accuracy
    - Better code generation, especially frontend UI
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        default_reasoning: ReasoningEffort = ReasoningEffort.HIGH,
    ):
        self.model = model
        self.default_reasoning = default_reasoning
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        """Lazy-initialize the OpenAI client."""
        if self._client is None:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY environment variable is required. "
                    "Set it in .mcp.json env section or export it."
                )
            self._client = AsyncOpenAI(api_key=api_key)
        return self._client

    def is_available(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(os.environ.get("OPENAI_API_KEY"))

    async def query(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        reasoning_effort: ReasoningEffort | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        model: str | None = None,
    ) -> CodexResponse:
        """
        Execute a query via GPT-5.2 Responses API.

        Args:
            prompt: The user prompt/question
            system_prompt: Optional system instructions
            reasoning_effort: Override default reasoning effort
            timeout: Request timeout in seconds
            model: Override default model

        Returns:
            CodexResponse with the model's output
        """
        if not self.is_available():
            return CodexResponse(
                success=False,
                output="",
                error="OPENAI_API_KEY not configured. Add it to .mcp.json env section.",
            )

        effort = reasoning_effort or self.default_reasoning
        model = model or self.model

        # Build input - Responses API uses 'input' not 'messages'
        input_content: list[dict[str, Any]] = []

        if system_prompt:
            input_content.append(
                {
                    "role": "developer",
                    "content": system_prompt,
                }
            )

        input_content.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        # Retry logic with exponential backoff
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await asyncio.wait_for(
                    self._make_request(input_content, effort, model),
                    timeout=timeout,
                )
                return response
            except (APITimeoutError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (2**attempt))
            except RateLimitError as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (2**attempt) * 2)
            except APIError as e:
                return CodexResponse(
                    success=False,
                    output="",
                    error=f"API Error: {e.message}",
                    model=model,
                )
            except Exception as e:
                return CodexResponse(
                    success=False,
                    output="",
                    error=f"Unexpected error: {str(e)}",
                    model=model,
                )

        return CodexResponse(
            success=False,
            output="",
            error=f"Request failed after {MAX_RETRIES} retries: {str(last_error)}",
            model=model,
        )

    async def _make_request(
        self,
        input_content: list[dict[str, Any]],
        effort: ReasoningEffort,
        model: str,
    ) -> CodexResponse:
        """Make the actual API request."""
        # OpenAI SDK types don't fully match Responses API at runtime
        response = await self.client.responses.create(  # type: ignore[call-overload]
            model=model,
            input=input_content,
            reasoning={"effort": effort.value},
        )

        # Extract output text from response
        output_text = ""
        if hasattr(response, "output_text"):
            output_text = response.output_text or ""
        elif hasattr(response, "output"):
            # Handle structured output
            for item in response.output:
                if hasattr(item, "text"):
                    output_text += item.text
                elif hasattr(item, "content"):
                    output_text += str(item.content)

        # Truncate if too long
        if len(output_text) > MAX_OUTPUT_CHARS:
            output_text = output_text[:MAX_OUTPUT_CHARS] + "\n\n[Output truncated]"

        # Extract token usage
        reasoning_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage") and response.usage:
            reasoning_tokens = getattr(response.usage, "reasoning_tokens", 0) or 0
            output_tokens = getattr(response.usage, "output_tokens", 0) or 0

        return CodexResponse(
            success=True,
            output=output_text,
            reasoning_tokens=reasoning_tokens,
            output_tokens=output_tokens,
            model=model,
        )


# Lazy singleton
_client: CodexClient | None = None


def get_client() -> CodexClient:
    """Get or create the Codex client singleton."""
    global _client
    if _client is None:
        _client = CodexClient()
    return _client


def reset_client() -> None:
    """Reset the singleton client (for testing)."""
    global _client
    _client = None
