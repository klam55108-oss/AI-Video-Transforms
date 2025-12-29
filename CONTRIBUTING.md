# Contributing to CognivAgent

Thank you for your interest in contributing to CognivAgent! This document provides guidelines and instructions for contributing.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Contributions](#making-contributions)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)

---

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment. Please:

- Be respectful of differing viewpoints and experiences
- Accept constructive criticism gracefully
- Focus on what's best for the community
- Show empathy towards other community members

---

## Getting Started

### Good First Issues

New contributors should look for issues labeled:

- `good first issue` - Simple, well-defined tasks
- `help wanted` - Issues where we need community help
- `documentation` - Documentation improvements

### Areas We Need Help

| Area | Difficulty | Description |
|------|------------|-------------|
| Documentation | Easy | Improve guides, add examples |
| Testing | Medium | Increase test coverage |
| Frontend | Medium | UI/UX improvements |
| Features | Hard | New functionality |
| Performance | Hard | Optimization work |

---

## Development Setup

### Prerequisites

- Python 3.11+
- uv (Python package manager)
- FFmpeg 4.0+
- Git 2.30+

### Setup Steps

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/agent-video-to-data.git
cd agent-video-to-data

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Add your API keys to .env

# Verify setup
uv run pytest --co -q  # List tests
uv run python -m app.main  # Start server
```

### API Keys

You'll need:
- `ANTHROPIC_API_KEY` from [Anthropic Console](https://console.anthropic.com/)
- `OPENAI_API_KEY` from [OpenAI Platform](https://platform.openai.com/)

---

## Making Contributions

### 1. Find or Create an Issue

- Check [existing issues](https://github.com/costiash/agent-video-to-data/issues)
- For new features, create an issue first to discuss
- For bugs, provide reproduction steps

### 2. Create a Branch

```bash
# Update main
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### Branch Naming

| Type | Format | Example |
|------|--------|---------|
| Feature | `feature/description` | `feature/add-srt-export` |
| Bug fix | `fix/issue-description` | `fix/transcript-upload` |
| Docs | `docs/what-changed` | `docs/api-reference` |
| Refactor | `refactor/what-changed` | `refactor/kg-service` |

### 3. Make Changes

- Follow [coding standards](#coding-standards)
- Write tests for new functionality
- Update documentation as needed

### 4. Test Your Changes

```bash
# Run all tests
uv run pytest

# Type checking
uv run mypy .

# Linting
uv run ruff check .
uv run ruff format .
```

### 5. Commit

```bash
git add .
git commit -m "feat(kg): add entity merge functionality"
```

#### Commit Message Format

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `style` - Formatting
- `refactor` - Code restructuring
- `test` - Adding tests
- `chore` - Maintenance

**Examples:**
```
feat(transcription): add SRT export format
fix(kg): prevent duplicate entity creation
docs(api): add rate limiting documentation
test(services): add session timeout tests
```

---

## Pull Request Process

### 1. Push Your Branch

```bash
git push origin feature/your-feature-name
```

### 2. Create Pull Request

- Go to [Pull Requests](https://github.com/costiash/agent-video-to-data/pulls)
- Click "New Pull Request"
- Select your branch
- Fill out the template

### 3. PR Template

```markdown
## Summary
Brief description of changes

## Related Issue
Closes #123

## Changes
- Added X
- Fixed Y
- Updated Z

## Testing
How to test these changes

## Screenshots (if applicable)
[Add screenshots for UI changes]

## Checklist
- [ ] Tests pass (`uv run pytest`)
- [ ] Types check (`uv run mypy .`)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] Documentation updated
- [ ] No sensitive data committed
```

### 4. Review Process

- Maintainers will review within 48 hours
- Address feedback with additional commits
- Once approved, a maintainer will merge

### 5. After Merge

```bash
git checkout main
git pull origin main
git branch -d feature/your-feature-name
```

---

## Coding Standards

### Python Style

```python
# ✅ Modern type annotations
def get_project(project_id: str) -> KGProject | None:
    ...

# ✅ Use pathlib for paths
from pathlib import Path
data_dir = Path("data")

# ✅ Async for I/O operations
async def fetch_data(url: str) -> dict[str, Any]:
    ...

# ✅ Google-style docstrings
def process(data: bytes, options: dict[str, Any]) -> str:
    """Process data and return result.

    Args:
        data: Input bytes to process.
        options: Processing options.

    Returns:
        Processed string output.

    Raises:
        ValueError: If data is empty.
    """
```

### Import Order

```python
# 1. Future imports
from __future__ import annotations

# 2. Standard library
import asyncio
from pathlib import Path

# 3. Third-party
from fastapi import Depends
from pydantic import BaseModel

# 4. Local imports
from app.core.config import get_settings
```

### Error Handling

```python
# ✅ Specific exceptions
try:
    result = await process()
except FileNotFoundError as e:
    logger.error(f"File not found: {e}")
    raise HTTPException(status_code=404, detail=str(e))

# ❌ Bare exceptions
except Exception:
    raise  # Too broad!
```

### MCP Tools

```python
# ✅ Always return structured responses
async def my_tool(args: dict[str, Any]) -> dict[str, Any]:
    try:
        result = await process(args)
        return {"content": [{"type": "text", "text": result}]}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

---

## Testing

### Running Tests

```bash
# All tests
uv run pytest

# Verbose
uv run pytest -v

# Specific file
uv run pytest tests/test_kg_service.py

# With coverage
uv run pytest --cov=app --cov-report=html
```

### Writing Tests

```python
import pytest
from app.services.kg_service import KnowledgeGraphService

class TestCreateProject:
    """Tests for KGService.create_project()"""

    @pytest.mark.asyncio
    async def test_creates_with_valid_name(self, kg_service):
        project = await kg_service.create_project("Test Project")
        assert project.name == "Test Project"
        assert project.state == ProjectState.CREATED

    @pytest.mark.asyncio
    async def test_rejects_empty_name(self, kg_service):
        with pytest.raises(ValueError):
            await kg_service.create_project("")
```

### Test Requirements

- All new features must have tests
- Bug fixes should include regression tests
- Maintain or improve coverage
- Tests must pass before merge

---

## Documentation

### When to Update Docs

- New features or API endpoints
- Changed behavior
- New configuration options
- Bug workarounds

### Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | Project overview |
| `CLAUDE.md` | Development guidelines |
| `guides/*.md` | User guides |
| `CONTRIBUTING.md` | This file |

### Docstrings

All public functions should have docstrings:

```python
def extract_entities(
    transcript: str,
    domain_profile: DomainProfile,
) -> list[Entity]:
    """Extract entities from transcript using domain profile.

    Args:
        transcript: Text content to analyze.
        domain_profile: Domain configuration for extraction.

    Returns:
        List of extracted entities with types and properties.

    Raises:
        ValueError: If transcript is empty.
        ExtractionError: If extraction fails.
    """
```

---

## Questions?

- **Issues**: [GitHub Issues](https://github.com/costiash/agent-video-to-data/issues) — For bugs, features, and questions
- **Documentation**: [Guides](https://github.com/costiash/agent-video-to-data/tree/main/guides) — Comprehensive documentation

---

## Thank You!

Every contribution makes CognivAgent better. We appreciate your time and effort!

---

<div align="center">

**Happy contributing!**

</div>
