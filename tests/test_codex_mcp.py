"""
Tests for mcp_servers/codex/ module.

Covers:
- Path safety validation
- File filtering logic
- File collection with traversal protection
- Client singleton management
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mcp_servers.codex.server import (
    _is_safe_path,
    _should_include_file,
    _collect_files,
    _read_file_safe,
    ALLOWED_EXTENSIONS,
)
from mcp_servers.codex.client import (
    CodexClient,
    CodexResponse,
    ReasoningEffort,
    get_client,
    reset_client,
)


class TestPathSafety:
    """Tests for _is_safe_path function."""

    def test_blocks_etc(self) -> None:
        assert not _is_safe_path(Path("/etc/passwd"))

    def test_blocks_usr(self) -> None:
        assert not _is_safe_path(Path("/usr/bin/python"))

    def test_blocks_bin(self) -> None:
        assert not _is_safe_path(Path("/bin/bash"))

    def test_blocks_sbin(self) -> None:
        assert not _is_safe_path(Path("/sbin/init"))

    def test_blocks_var(self) -> None:
        assert not _is_safe_path(Path("/var/log/syslog"))

    def test_blocks_root(self) -> None:
        assert not _is_safe_path(Path("/root/.bashrc"))

    def test_allows_home_paths(self) -> None:
        assert _is_safe_path(Path("/home/user/project/app/main.py"))

    def test_allows_tmp_paths(self) -> None:
        assert _is_safe_path(Path("/tmp/test_file.py"))

    def test_allows_relative_paths(self) -> None:
        # Relative paths get resolved, but if they resolve to safe location
        assert _is_safe_path(Path("app/main.py").resolve())


class TestFileFiltering:
    """Tests for _should_include_file function."""

    def test_excludes_pycache(self) -> None:
        assert not _should_include_file(Path("app/__pycache__/foo.pyc"))

    def test_excludes_node_modules(self) -> None:
        assert not _should_include_file(Path("node_modules/lodash/index.js"))

    def test_excludes_git_directory(self) -> None:
        assert not _should_include_file(Path(".git/config"))

    def test_excludes_hidden_files(self) -> None:
        assert not _should_include_file(Path(".hidden_file.txt"))

    def test_excludes_env_files_security(self) -> None:
        """Security: .env files should NOT be included to prevent secret exposure."""
        assert not _should_include_file(Path(".env"))
        assert not _should_include_file(Path("config/.env"))
        assert not _should_include_file(Path(".env.local"))

    def test_includes_gitignore(self) -> None:
        assert _should_include_file(Path(".gitignore"))

    def test_includes_python_files(self) -> None:
        assert _should_include_file(Path("app/main.py"))

    def test_includes_typescript_files(self) -> None:
        assert _should_include_file(Path("src/index.ts"))

    def test_includes_javascript_files(self) -> None:
        assert _should_include_file(Path("lib/utils.js"))

    def test_includes_json_files(self) -> None:
        assert _should_include_file(Path("package.json"))

    def test_includes_markdown_files(self) -> None:
        assert _should_include_file(Path("README.md"))

    def test_includes_dockerfile(self) -> None:
        assert _should_include_file(Path("Dockerfile"))

    def test_excludes_unknown_extensions(self) -> None:
        assert not _should_include_file(Path("data.xyz"))
        assert not _should_include_file(Path("binary.exe"))


class TestAllowedExtensions:
    """Tests for ALLOWED_EXTENSIONS constant."""

    def test_env_not_in_allowed_extensions(self) -> None:
        """Security: .env should NOT be in allowed extensions."""
        assert ".env" not in ALLOWED_EXTENSIONS

    def test_common_code_extensions_present(self) -> None:
        expected = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs"}
        assert expected.issubset(ALLOWED_EXTENSIONS)

    def test_config_extensions_present(self) -> None:
        expected = {".json", ".yaml", ".yml", ".toml"}
        assert expected.issubset(ALLOWED_EXTENSIONS)


class TestFileCollection:
    """Tests for _collect_files function with path traversal protection."""

    def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        """Path traversal via ../ should return empty dict."""
        # Create a file outside the "project root"
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        (outside_dir / "secret.py").write_text("SECRET = 'password'")

        project_root = tmp_path / "project"
        project_root.mkdir()

        # Try to access file outside project via traversal
        result = _collect_files("../outside/secret.py", base_path=project_root)
        assert result == {}

    def test_collects_single_file(self, tmp_path: Path) -> None:
        """Should collect a single file when path points to file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        result = _collect_files(str(test_file), base_path=tmp_path)
        assert len(result) == 1
        assert "print('hello')" in list(result.values())[0]

    def test_collects_directory_files(self, tmp_path: Path) -> None:
        """Should collect all matching files in directory."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main")
        (src_dir / "utils.py").write_text("# utils")

        result = _collect_files("src", base_path=tmp_path)
        assert len(result) == 2

    def test_filters_by_extension(self, tmp_path: Path) -> None:
        """Should only include allowed file extensions."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# python")
        (src_dir / "data.xyz").write_text("unknown")

        result = _collect_files("src", base_path=tmp_path)
        assert len(result) == 1
        assert any("main.py" in k for k in result.keys())

    def test_excludes_pycache_in_directory(self, tmp_path: Path) -> None:
        """Should skip __pycache__ directories."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main")

        cache_dir = src_dir / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "main.cpython-311.pyc").write_text("bytecode")

        result = _collect_files("src", base_path=tmp_path)
        assert len(result) == 1
        assert not any("__pycache__" in k for k in result.keys())


class TestReadFileSafe:
    """Tests for _read_file_safe function."""

    def test_reads_existing_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("content")
        result = _read_file_safe(test_file)
        assert result == "content"

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        result = _read_file_safe(tmp_path / "nonexistent.py")
        assert result is None

    def test_returns_none_for_directory(self, tmp_path: Path) -> None:
        result = _read_file_safe(tmp_path)
        assert result is None

    def test_returns_message_for_large_file(self, tmp_path: Path) -> None:
        large_file = tmp_path / "large.py"
        large_file.write_text("x" * 1_000_000)  # 1MB
        result = _read_file_safe(large_file, max_size=500_000)
        assert result is not None
        assert "File too large" in result

    def test_blocks_unsafe_paths(self) -> None:
        result = _read_file_safe(Path("/etc/passwd"))
        assert result is None


class TestCodexClient:
    """Tests for CodexClient class."""

    def test_is_available_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        client = CodexClient()
        assert not client.is_available()

    def test_is_available_with_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        client = CodexClient()
        assert client.is_available()

    def test_default_model(self) -> None:
        client = CodexClient()
        assert client.model == "gpt-5.1-codex-max"

    def test_default_reasoning_effort(self) -> None:
        client = CodexClient()
        assert client.default_reasoning == ReasoningEffort.HIGH

    def test_custom_model(self) -> None:
        client = CodexClient(model="gpt-5.1-codex-mini")
        assert client.model == "gpt-5.1-codex-mini"


class TestCodexResponse:
    """Tests for CodexResponse dataclass."""

    def test_success_response(self) -> None:
        response = CodexResponse(
            success=True,
            output="Hello world",
            reasoning_tokens=100,
            output_tokens=50,
        )
        assert response.success
        assert response.output == "Hello world"
        assert response.error is None

    def test_error_response(self) -> None:
        response = CodexResponse(
            success=False,
            output="",
            error="API key invalid",
        )
        assert not response.success
        assert response.error == "API key invalid"


class TestSingletonManagement:
    """Tests for singleton client management."""

    def test_get_client_returns_same_instance(self) -> None:
        reset_client()  # Start fresh
        client1 = get_client()
        client2 = get_client()
        assert client1 is client2

    def test_reset_client_clears_singleton(self) -> None:
        reset_client()
        client1 = get_client()
        reset_client()
        client2 = get_client()
        assert client1 is not client2


class TestReasoningEffort:
    """Tests for ReasoningEffort enum."""

    def test_all_levels_defined(self) -> None:
        levels = [e.value for e in ReasoningEffort]
        assert "none" in levels
        assert "low" in levels
        assert "medium" in levels
        assert "high" in levels
        assert "xhigh" in levels

    def test_string_values(self) -> None:
        assert ReasoningEffort.HIGH.value == "high"
        assert ReasoningEffort.XHIGH.value == "xhigh"
