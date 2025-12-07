"""
Gemini CLI async subprocess wrapper.

Wraps: gemini --approval-mode yolo --model gemini-3-pro-preview

Strategy for GEMINI.md context:
- cwd is set to mcp_servers/gemini/ so Gemini CLI finds GEMINI.md there
- --include-directories adds the project root for full file visibility
- A PostToolUse hook handles moving generated GEMINI.md to mcp_servers/gemini/
"""

from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MODEL = "gemini-3-pro-preview"
# Directory containing this module - used as cwd for GEMINI.md discovery
_MODULE_DIR = Path(__file__).parent.resolve()
# Project root for --include-directories
_PROJECT_ROOT = _MODULE_DIR.parent.parent
DEFAULT_TIMEOUT = 120.0
MAX_OUTPUT_CHARS = 80_000

GEMINI_SEARCH_PATHS = [
    "gemini",
    Path.home() / ".npm-global" / "bin" / "gemini",
    Path.home() / ".local" / "bin" / "gemini",
    Path("/usr/local/bin/gemini"),
]


def find_gemini_executable() -> str | None:
    """Find the gemini CLI executable."""
    result = shutil.which("gemini")
    if result:
        return result
    for path in GEMINI_SEARCH_PATHS:
        if isinstance(path, Path) and path.exists():
            return str(path)
    return None


@dataclass
class GeminiResponse:
    """Response from Gemini CLI."""

    success: bool
    output: str
    error: str | None = None


class GeminiClient:
    """Async wrapper for Gemini CLI."""

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.executable = find_gemini_executable()

    def is_available(self) -> bool:
        """Check if Gemini CLI is available."""
        return self.executable is not None

    async def query(
        self,
        prompt: str,
        model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> GeminiResponse:
        """Execute a query via Gemini CLI."""
        if not self.executable:
            return GeminiResponse(
                success=False,
                output="",
                error="Gemini CLI not found. Install: npm install -g @anthropic-ai/gemini-cli",
            )

        model = model or self.model
        cmd = [
            self.executable,
            "--approval-mode",
            "yolo",
            "--model",
            model,
            "--include-directories",
            str(_PROJECT_ROOT),  # Full project visibility
            prompt,
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
                cwd=_MODULE_DIR,  # Run from mcp_servers/gemini/ to find GEMINI.md
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            if process.returncode != 0:
                return GeminiResponse(
                    success=False,
                    output="",
                    error=stderr.decode().strip() or f"Exit code {process.returncode}",
                )

            output = stdout.decode().strip()
            if len(output) > MAX_OUTPUT_CHARS:
                output = output[:MAX_OUTPUT_CHARS] + "\n[Output truncated]"

            return GeminiResponse(success=True, output=output)

        except asyncio.TimeoutError:
            return GeminiResponse(
                success=False, output="", error=f"Timeout after {timeout}s"
            )
        except Exception as e:
            return GeminiResponse(success=False, output="", error=str(e))


# Lazy singleton
_client: GeminiClient | None = None


def get_client() -> GeminiClient:
    """Get or create the Gemini client singleton."""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
