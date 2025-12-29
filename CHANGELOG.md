# Changelog

All notable changes to CognivAgent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Removed debug console.log statements from job callback handling
- Fixed mypy type errors in merge safety tests
- Fixed ruff lint errors (import ordering, unused variables)

## [0.1.0] - TBD

Initial open-source release of CognivAgent.

### Added

#### Core Features
- **Video Transcription**: Local videos and YouTube URLs via OpenAI gpt-4o-transcribe
  - Automatic audio splitting for videos > 25 minutes
  - Intelligent audio compression for files exceeding 25MB limit
  - Optional language and domain vocabulary hints for specialized content
- **Knowledge Graph Extraction**: Transform transcripts into structured knowledge
  - Auto-bootstrap domain schemas from first video
  - Extract entities and relationships with source citations
  - Interactive discovery confirmation workflow
- **Entity Resolution**: Detect and merge duplicate entities
  - Multi-signal similarity matching (Jaro-Winkler, alias overlap)
  - N-gram blocking for efficient candidate filtering
  - Full merge audit trail with rollback support
- **Graph Visualization**: Interactive Cytoscape.js visualization
  - Multi-select entity type filtering
  - Full-text search across labels, aliases, descriptions
  - Node inspector with evidence/citation viewer
  - Export to GraphML (Gephi, Neo4j, yEd) and JSON

#### Infrastructure
- **Background Jobs**: Async queue with persistence and restart recovery
  - Step-by-step progress UI with stage indicators
  - Cancel/retry support with graceful shutdown
  - Job auto-continuation: completed jobs trigger agent responses
- **Audit Trail**: Security blocking and tool usage logging
  - Pre/post tool execution hooks
  - Dangerous operation detection and blocking
  - API key redaction in logs
- **Real-time Activity**: SSE-based agent activity streaming
  - Shows: thinking, tool_use, tool_result, subagent, file_save
  - Polling fallback if SSE unavailable

#### User Experience
- **Chat Interface**: Markdown rendering with XSS protection
  - Dark/light themes with semantic design tokens
  - Code syntax highlighting and copy-to-clipboard
  - Session history with restore capability
- **Transcript Library**: Save, search, and export transcripts
  - Full-text viewer with in-document search and highlighting
  - Export formats: TXT, JSON
  - Lazy loading for large transcript lists
- **3-Panel Workspace**: Resizable chat + KG visualization layout
  - Minimum width enforcement
  - Panel widths persisted to localStorage

#### Developer Experience
- **914 Tests**: Comprehensive test coverage across 39 modules
- **Strict Type Checking**: mypy with full type annotations
- **Code Quality**: ruff linting and formatting
- **Docker Support**: Multi-stage build with non-root user
- **Comprehensive Documentation**: 7 guides, 7 rule files, contributor guidelines

### Architecture
- 3-tier modular monolith: API → Services → Core
- SessionActor queue-based pattern prevents Claude SDK cancel scope errors
- 9 FastAPI routers with dependency injection
- 37 ES modules for frontend (no build step required)
- NetworkX-based knowledge graph storage

### Security
- Path validation blocks system paths (`/etc`, `/usr`, `/bin`, etc.)
- XSS protection via DOMPurify
- UUID v4 validation for all IDs
- 500MB file upload limit with extension whitelist
- No hardcoded secrets (environment-based configuration)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to submit changes.

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.
