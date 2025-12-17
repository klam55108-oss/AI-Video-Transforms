# Changelog

All notable changes to this project are documented in this file.

---

## [Unreleased] - 2025-12-17

### MVP Enhancement Phase: From POC to Production-Ready

This release transforms the proof-of-concept into a production-ready MVP with Docker deployment, async job processing, unified error handling, and a full-featured Knowledge Graph visualization interface.

---

## P0-1: Docker Deployment

### Added

- **Dockerfile** - Multi-stage build with Python 3.11-slim base
  - Non-root user (`agent`, UID 1000) for security
  - FFmpeg and system dependencies
  - uv package manager for fast installs
  - Health check endpoint integration

- **docker-compose.yml** - Service orchestration
  - Volume mounting for data persistence
  - Environment variable passthrough
  - Automatic restart policy
  - Health check configuration

- **.dockerignore** - Build optimization
  - Excludes tests, caches, virtual environments
  - Reduces image size and build time

- **DOCKER.md** - Comprehensive deployment guide
  - Quick start instructions
  - Manual build and run commands
  - Production deployment recommendations
  - Troubleshooting guide

### Technical Details

| Component | Size | Purpose |
|-----------|------|---------|
| Base image | ~50MB | Python 3.11-slim |
| System deps | ~100MB | FFmpeg, curl |
| Python deps | ~200MB | Production packages |
| **Final** | **~400MB** | Optimized build |

---

## P0-2: Job Queue System (In-Memory)

### Added

#### Data Models (`app/models/jobs.py`)

- **JobType** - Enum: `TRANSCRIPTION`, `BOOTSTRAP`, `EXTRACTION`
- **JobStatus** - Enum: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`
- **JobStage** - Progress tracking: `QUEUED`, `DOWNLOADING`, `EXTRACTING_AUDIO`, `TRANSCRIBING`, `PROCESSING`, `FINALIZING`
- **Job** - Dataclass with full lifecycle tracking

#### Service Layer (`app/services/job_queue_service.py`)

```python
class JobQueueService:
    """In-memory job queue with background processing."""

    # Features:
    # - Thread-safe storage (asyncio.Lock)
    # - Queue-based dispatch (asyncio.Queue)
    # - Configurable concurrency (Semaphore)
    # - Background worker pool (2 workers default)
    # - Progress tracking API
    # - Graceful shutdown
```

#### API Endpoints (`app/api/routers/jobs.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jobs/{job_id}` | GET | Get job status with progress |
| `/jobs` | GET | List jobs (filter by status/type) |
| `/jobs/{job_id}` | DELETE | Cancel pending/running jobs |

#### Configuration (`app/core/config.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_JOB_MAX_CONCURRENT` | `2` | Max concurrent job execution |
| `APP_JOB_POLL_INTERVAL_MS` | `1000` | Frontend polling interval |

#### Testing (`tests/test_job_queue.py`)

- **20 new tests** covering:
  - Job model serialization
  - Job lifecycle (create, retrieve, list, cancel)
  - Progress updates
  - Concurrent job limit enforcement
  - Graceful shutdown
  - API endpoint integration

---

## P0-3: Unified Error Schema

### Added

#### Error Models (`app/models/errors.py`)

**ErrorCode Enum** - Standardized error codes:

```python
# Transcription errors
DOWNLOAD_FAILED, FFMPEG_NOT_FOUND, TRANSCRIPTION_FAILED, TRANSCRIPTION_TIMEOUT

# Knowledge Graph errors
BOOTSTRAP_FAILED, EXTRACTION_FAILED, PROJECT_NOT_FOUND, INVALID_PROJECT_STATE

# Session errors
SESSION_NOT_FOUND, SESSION_EXPIRED, SESSION_CLOSED

# Resource errors
RESOURCE_NOT_FOUND, FILE_NOT_FOUND

# Validation errors
VALIDATION_ERROR, INVALID_FORMAT

# System errors
RATE_LIMITED, SERVICE_UNAVAILABLE, REQUEST_TIMEOUT, INTERNAL_ERROR
```

**APIError Dataclass**:

```python
@dataclass
class APIError:
    code: ErrorCode          # Standardized error code
    message: str             # Human-readable message
    detail: str | None       # Technical details (debugging)
    hint: str | None         # Actionable suggestion
    retryable: bool          # Should client retry?
```

**Predefined Error Factories**:

- `transcription_timeout_error()`
- `ffmpeg_not_found_error()`
- `project_not_found_error()`
- `invalid_project_state_error()`
- `session_not_found_error()`
- `session_expired_error()`
- `validation_error()`
- `service_unavailable_error()`
- `request_timeout_error()`
- `internal_error()`
- `file_not_found_error()`

#### Frontend Integration (`app/static/script.js`)

Enhanced `handleKGApiError()`:
- Parses unified error schema
- Extracts code, message, detail, hint, retryable
- Backward compatible with legacy format

Enhanced `showToast()`:
- Displays hints for actionable errors
- "Copy Debug Info" button for error debugging
- Extended display time for errors with hints (6s vs 4s)

#### Testing (`tests/test_error_schema.py`)

- APIError serialization tests
- ErrorCode enum coverage
- Error factory tests

---

## P0-4: Knowledge Graph Graph-Data Endpoint

### Added

#### API Endpoint (`app/api/routers/kg.py`)

```http
GET /kg/projects/{project_id}/graph-data
```

Returns Cytoscape.js-compatible graph data:

```json
{
  "nodes": [
    {
      "data": {
        "id": "node-123",
        "label": "Entity Name",
        "type": "Person",
        "description": "...",
        "aliases": ["alias1", "alias2"]
      }
    }
  ],
  "edges": [
    {
      "data": {
        "id": "edge-456",
        "source": "node-123",
        "target": "node-789",
        "label": "works_for",
        "relationship_type": "works_for",
        "relationship_types": ["works_for", "employed_by"]
      }
    }
  ]
}
```

#### Testing (`tests/test_kg_api.py`)

- Graph data endpoint tests
- Empty graph handling
- Node/edge format validation

---

## Knowledge Graph Visualization UI

### Added

#### Cytoscape.js Integration (`app/templates/index.html`, `app/static/script.js`)

- **Graph rendering** with force-directed layout (cose algorithm)
- **Node styling** based on entity type with color coding
- **Node sizing** based on connection degree (more connected = larger)
- **Edge styling** with relationship labels on hover/selection
- **Smooth animations** for layout transitions

#### Entity Type Colors

| Type | Color |
|------|-------|
| Person, Character | `#3b82f6` (Blue) |
| Organization, Group | `#10b981` (Green) |
| Event | `#f59e0b` (Amber) |
| Location, Place | `#ef4444` (Red) |
| Concept, Theme | `#8b5cf6` (Purple) |
| Technology | `#06b6d4` (Cyan) |
| Product, Object | `#ec4899` (Pink) |
| Default | `#64748b` (Slate) |

#### Graph Search Functionality

- **Real-time search** with debouncing (150ms)
- **Keyboard navigation** (Arrow keys, Enter, Escape)
- **Search highlighting** - Matching nodes highlighted, others dimmed
- **Click-to-navigate** - Select search result to zoom to node

#### Entity Type Legend

- **Interactive filtering** - Click type to highlight matching nodes
- **Entity counts** - Shows count per type
- **"Show All" reset** - Clears active filter
- **Sorted by count** - Most frequent types first

#### Node Inspector Panel

- **Slide-in panel** on node selection
- **Node details**: Label, type, description, aliases
- **Connections list**: Related nodes with relationship types
- **Click-to-navigate**: Click connection to select that node
- **Scrollable content** for nodes with many connections

#### Layout Options (Header Controls)

| Layout | Description |
|--------|-------------|
| Force-directed | Physics-based (cose algorithm) |
| Grid | Aligned rows and columns |
| Circle | Circular arrangement |
| Hierarchical | Tree structure (breadthfirst) |

#### View Controls

- **Fit to view** (`fitGraphView()`) - Fit all nodes in viewport
- **Reset view** (`resetGraphView()`) - Reset to default layout

#### Collapsible Sidebar

- **Desktop collapse button** in sidebar header
- **Smooth animation** (0.3s transition)
- **Expand button** in header when collapsed
- **State-aware UI** updates (body class toggle)

#### View Toggle (List/Graph)

- **List view** - Chat interface (default)
- **Graph view** - Cytoscape visualization
- **State persistence** - Remembers preference in localStorage
- **Header title update** - Changes based on active view

### CSS Additions (`app/static/style.css`)

- **936 new lines** of graph visualization styles
- Collapsible sidebar styles
- Header dropdown and control button styles
- Graph search bar and results dropdown
- Entity type legend with interactive items
- Inspector panel with slide-in animation
- Dark/light theme support throughout

---

## UI Bug Fixes

### Fixed

#### Bug 1: Legend Disappearing After Inspector Close

**Root Cause**: Graph view container (`#kg-graph-view`) growing beyond parent bounds due to flexbox's default `min-height: auto`, pushing absolutely-positioned legend off-screen.

**Fix** (`app/static/style.css`):
```css
#kg-graph-view {
    min-height: 0;
    overflow: hidden;
}
#kg-graph-view > div:first-child {
    min-height: 0;
}
```

#### Bug 2: Controller Buttons Losing Functionality

**Root Cause**: Cytoscape.js wasn't being notified when container size changed (inspector panel open/close, sidebar collapse).

**Fix** (`app/static/script.js`):
```javascript
// Added ResizeObserver to notify Cytoscape of container changes
graphResizeObserver = new ResizeObserver(() => {
    if (cytoscapeInstance) {
        cytoscapeInstance.resize();
    }
});
graphResizeObserver.observe(container);
```

#### Bug 3: Inspector Panel Not Scrollable

**Root Cause**: Connections list container had `overflow: visible` instead of allowing scroll.

**Fix** (`app/static/style.css`):
```css
.inspector-connections-section {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}
.inspector-connections-section > div:last-child {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
}
```

#### Bug 4: Legend Disappearing on View Switch (List→Graph)

**Root Cause**: Cytoscape.js replaces container innerHTML when initialized, destroying search bar and legend elements that were children of `#kg-graph-container`.

**Fix** (`app/templates/index.html`):

Restructured HTML so search bar and legend are **siblings** of Cytoscape container:

```html
<!-- BEFORE: Children destroyed by Cytoscape -->
<div id="kg-graph-container">
    <div id="kg-search-container">...</div>
    <div id="kg-type-legend">...</div>
</div>

<!-- AFTER: Siblings safe from Cytoscape -->
<div class="flex-1 relative overflow-hidden min-w-0">
    <div id="kg-graph-container"><!-- Cytoscape only --></div>
    <div id="kg-search-container">...</div>
    <div id="kg-type-legend">...</div>
</div>
```

---

## Files Summary

### Created (New Files)

| File | Lines | Description |
|------|-------|-------------|
| `Dockerfile` | ~50 | Multi-stage Docker build |
| `docker-compose.yml` | ~30 | Service orchestration |
| `.dockerignore` | ~20 | Build exclusions |
| `DOCKER.md` | 216 | Deployment documentation |
| `IMPLEMENTATION_SUMMARY.md` | 124 | Job queue implementation notes |
| `app/models/errors.py` | 216 | Unified error schema |
| `app/models/jobs.py` | 87 | Job queue data models |
| `app/services/job_queue_service.py` | ~330 | Job queue service |
| `app/api/routers/jobs.py` | ~100 | Job API endpoints |
| `tests/test_error_schema.py` | ~50 | Error schema tests |
| `tests/test_job_queue.py` | ~480 | Job queue tests |

### Modified (Existing Files)

| File | +/- Lines | Summary |
|------|-----------|---------|
| `app/static/script.js` | +1406 | Graph visualization, error handling |
| `app/static/style.css` | +936 | Graph UI styles |
| `app/templates/index.html` | +143 | Graph view, controls, sidebar |
| `app/api/routers/kg.py` | +72 | Graph-data endpoint |
| `app/services/__init__.py` | +33 | JobQueueService integration |
| `app/core/config.py` | +4 | Job queue settings |
| `app/api/deps.py` | +11 | Job queue DI provider |
| `app/api/errors.py` | +88 | Error handler updates |
| `app/main.py` | +4 | Jobs router mounting |
| `app/ui/routes.py` | +1 | Job poll interval config |
| `tests/test_api_deps.py` | +23 | DI provider tests |
| `tests/test_kg_api.py` | +61 | Graph endpoint tests |

---

## Testing

```bash
# All tests passing
uv run pytest                    # 595+ tests
uv run mypy .                    # Strict mode, no errors
uv run ruff check . && ruff format .  # Clean
```

---

## Architecture Reference

```
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                        │
├───────────────────┬─────────────────────┬───────────────────────┤
│    API Layer      │   Services Layer    │     Core Layer        │
│  app/api/         │   app/services/     │   app/core/           │
│  ─────────────    │   ───────────────   │   ──────────────      │
│  8 Routers        │  SessionService     │  SessionActor         │
│  (+ jobs.py)      │  StorageService     │  Atomic Storage       │
│  Dependency Inj.  │  TranscriptionSvc   │  Cost Tracking        │
│  Error Handlers   │  KnowledgeGraphSvc  │  Config Singleton     │
│                   │  JobQueueService    │                       │
└───────────────────┴─────────────────────┴───────────────────────┘
                              │
                              ▼
        ┌───────────────────────────────────────────┐
        │    Claude Agent SDK + MCP Tools           │
        │    app/agent/ + app/kg/tools/             │
        └───────────────────────────────────────────┘
```

---

## Critical Patterns

### Cytoscape.js Container Safety

Libraries like Cytoscape.js replace container innerHTML. Keep overlay elements (search, legend) as **siblings**, not children:

```html
<div class="wrapper">
    <div id="cytoscape-container"><!-- Library owns this --></div>
    <div class="search-overlay"><!-- Safe as sibling --></div>
    <div class="legend-overlay"><!-- Safe as sibling --></div>
</div>
```

### ResizeObserver for Canvas Libraries

Canvas-based visualizations need explicit resize notification:

```javascript
const observer = new ResizeObserver(() => {
    cytoscapeInstance?.resize();
});
observer.observe(container);
```

### Flexbox Height Containment

Override `min-height: auto` to allow flex items to shrink:

```css
.flex-container {
    min-height: 0;      /* Allow shrinking */
    overflow: hidden;   /* Contain children */
}
```

---

## Previous Changes

### Claude Agent SDK Best Practices (2025-12-16)

- ResultMessage subtype handling
- Token-level cost tracking with deduplication
- Tool input schema standardization (full JSON Schema)

### Knowledge Graph System

- Complete KG workflow: Create → Bootstrap → Confirm → Extract → Export
- Domain inference from transcripts
- GraphML/JSON export

### Core Architecture

- SessionActor pattern (queue-based actor model)
- Dependency injection with FastAPI Depends()
- MCP tool pattern (structured error returns)
