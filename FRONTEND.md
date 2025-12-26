# Frontend Architecture

> ES Modules-based vanilla JavaScript frontend with Tailwind CSS.

## Stack

- **Tailwind CSS** via CDN (no build step)
- **Vanilla JavaScript** ES Modules
- **Jinja2** templates in `app/templates/`
- **External CDN**: Marked.js (markdown), DOMPurify (XSS), Cytoscape.js (graphs)

---

## Module Structure

```
app/static/js/
├── main.js              # Entry point - aggregates all modules
├── core/                # Shared state and utilities
│   ├── config.js        # App configuration, poll intervals
│   ├── state.js         # Centralized state object
│   └── utils.js         # Helper functions (escapeHtml, copyToClipboard)
├── ui/                  # UI components
│   ├── theme.js         # Dark/light theme toggle
│   ├── toast.js         # Toast notifications
│   ├── sidebar.js       # Sidebar collapse/expand
│   ├── header.js        # Header dropdowns
│   └── mobile.js        # Mobile navigation
├── chat/                # Chat system
│   ├── messages.js      # Message rendering with markdown
│   ├── send.js          # Message sending with retry logic
│   ├── session.js       # Session init and restoration
│   ├── status.js        # Agent status polling
│   └── activity.js      # Real-time activity streaming (SSE)
├── panels/              # Sidebar panels
│   ├── history.js       # Session history panel
│   ├── transcripts.js   # Transcript library panel
│   ├── transcript-search.js  # Transcript search filtering
│   └── transcript-viewer.js  # Full transcript modal viewer
├── jobs/                # Background job queue
│   ├── jobs.js          # Job progress UI and polling
│   └── step-progress.js # Step-by-step progress indicator
├── upload/              # File uploads
│   └── upload.js        # Video upload handling
├── audit/               # Audit trail system
│   ├── index.js         # Module aggregator
│   ├── api.js           # Audit API client
│   └── panel.js         # Audit sidebar panel UI
├── ui/                  # UI components
│   └── workspace.js     # 3-panel resizable workspace layout
└── kg/                  # Knowledge Graph visualization
    ├── index.js         # Module aggregator
    ├── api.js           # KG API client
    ├── panel.js         # KG panel management
    ├── polling.js       # Project status polling
    ├── actions.js       # Create, confirm, export actions
    ├── ui.js            # UI state updates
    ├── graph.js         # Cytoscape.js integration
    ├── search.js        # Graph search functionality
    ├── inspector.js     # Node inspector panel
    └── evidence.js      # Node evidence/citation viewer
```

---

## Module Details

### Core Modules

#### `core/config.js`
Application configuration with server-injected values.

```javascript
export const PURIFY_CONFIG = { ... };
export function getStatusPollInterval();
export function getKGPollInterval();
export function getJobPollInterval();
```

#### `core/state.js`
Centralized state object shared across all modules.

```javascript
export const state = {
    sessionId,           // UUID v4 from sessionStorage
    isProcessing,        // Chat processing state
    kgCurrentProjectId,  // Selected KG project
    cytoscapeInstance,   // Cytoscape.js graph instance
    // ... DOM element references
};

export function initDOMReferences();  // Called on DOMContentLoaded
export function resetKGState();
```

#### `core/utils.js`
Shared utility functions.

```javascript
export function escapeHtml(str);
export function copyToClipboard(text);
export function formatFileSize(bytes);
export function sleep(ms);
```

### Chat Modules

#### `chat/messages.js`
Message rendering with XSS protection.

```javascript
export function addMessage(text, sender, usage);
export function showLoading();           // Returns loadingId
export function removeLoading(id);
export function updateLoadingActivity(text);  // Real-time activity feedback
export function showEmptyState();
export function hideEmptyState();
export function scrollToBottom();
```

**Security**: All agent messages sanitized via DOMPurify before rendering.

**Activity Display**: `updateLoadingActivity()` updates the loading indicator with real-time agent activity (e.g., "🔧 Transcribing video"). Smoothly transitions from loading dots to activity text.

#### `chat/send.js`
Message sending with retry logic and job detection.

```javascript
export async function sendMessage(message, showInUI = true);
export function detectAndTrackJobs(responseText);
```

**Job Detection**: After receiving agent responses, `detectAndTrackJobs()` scans for job IDs using regex (`/job(?:\s+id)?[:\s]+([a-f0-9-]{36})/gi`). Detected jobs automatically get progress UI in chat and sidebar tracking.

**Error Handling**:
- `503` (Server Busy) → Retry with exponential backoff
- `504` (Timeout) → Show timeout message
- `422` (Validation) → Display validation error
- `410` (Session Expired) → Clear session, disable input

#### `chat/session.js`
Session initialization and restoration.

```javascript
export async function initSession();
export async function loadExistingSession();
```

**Flow**:
1. Check for existing session history
2. If exists → Restore messages with visual divider
3. If new → Fetch greeting from `/chat/init`

#### `chat/status.js`
Agent status polling.

```javascript
export function startStatusPolling();
export function stopStatusPolling();
export function updateStatus();
export function renderStatus(status);
```

**Status States**: `initializing`, `ready`, `processing`, `error`, `expired`

#### `chat/activity.js`
Real-time activity streaming via Server-Sent Events (SSE).

```javascript
export function startActivityStream(callback);  // Opens SSE connection
export function stopActivityStream();           // Closes connection
export function formatActivityText(event);      // Formats with emoji
export function getActivityIcon(type);          // Returns icon class
```

**SSE Streaming**: Connects to `/chat/activity/{session_id}` for real-time activity events. Automatically falls back to polling (`/chat/activity/{id}/current` at 1000ms intervals) if SSE fails.

**Activity Types**: `thinking`, `tool_use`, `tool_result`, `subagent`, `file_save`, `completed`

**Debouncing**: Rapid tool sequences are debounced at 150ms to prevent UI flicker. `flushPendingActivity()` ensures final state is shown when stream ends.

**Integration**: Activity stream starts when message is sent and stops when response completes. Updates loading indicator with current agent action.

### Jobs Module

#### `jobs/jobs.js`
Background job progress tracking with sidebar panel and auto-continuation.

```javascript
// Chat area progress UI
export function createJobProgressUI(jobId, title);
export function updateJobProgress(jobId, job);
export function startJobPolling(jobId);
export function stopJobPolling(jobId);

// Sidebar panel
export function toggleJobsPanel();
export function loadJobs();
export function startSidebarPolling();
export function stopSidebarPolling();

// Job actions
export function cancelJob(jobId);
export function cleanupAllJobPollers();
```

**Job Stages**: `queued`, `downloading`, `extracting_audio`, `transcribing`, `processing`, `finalizing`

**Job Statuses**: `pending`, `running`, `completed`, `failed`, `cancelled`

**Auto-Continuation**: When jobs complete, `triggerJobCompletionCallback()` sends a hidden message to the agent requesting it show results and offer next steps. This creates a seamless workflow where background jobs automatically continue the conversation.

**Race Condition Handling**: `sendMessageWhenReady()` retries callbacks at 500ms intervals (max 20 attempts) until `state.isProcessing` clears, preventing silent callback drops when jobs complete during active message processing.

#### `jobs/step-progress.js`
Step-by-step progress indicator for job stages.

```javascript
export function renderStepProgress(job);
export function getStepsForJobType(jobType);
```

**Step States**: `pending` (gray), `active` (blue pulse), `completed` (green check)

**Job Types**:
- `transcription`: queued → downloading → extracting_audio → transcribing → processing → finalizing
- `bootstrap`: queued → processing → finalizing
- `extraction`: queued → processing → finalizing

### Audit Module

#### `audit/index.js`
Aggregates and re-exports all audit module functions.

#### `audit/api.js`
Audit API client for fetching audit logs and stats.

```javascript
export const auditClient = {
    getStats(),                           // Aggregate audit statistics
    listSessions(limit),                  // Sessions with audit logs
    getSessionAuditLog(sessionId, opts),  // Detailed session audit log
};
```

**Event Types**: `pre_tool_use`, `post_tool_use`, `tool_blocked`, `session_stop`, `subagent_stop`

#### `audit/panel.js`
Audit sidebar panel with real-time event display.

```javascript
export function initAuditPanel();
export function loadAuditEvents();
export function toggleAuditPanel();
export function refreshAuditStats();
```

**Features**:
- Real-time tool usage visualization with success/failure badges
- Blocked operations highlighted with warning icons
- Tool duration timing display
- Session-filtered view with pagination
- Aggregate statistics (tools invoked, blocked, success rate)

**Event Display**: Each audit entry shows:
- Timestamp with relative time formatting
- Tool name with icon
- Success/failure status badge
- Duration in milliseconds (for completed tools)
- Block reason (for blocked operations)

### Panels Modules

#### `panels/transcript-search.js`
Real-time search filtering for transcript library.

```javascript
export function initTranscriptSearch();
export function filterTranscripts(query);
export function clearTranscriptSearch();
```

#### `panels/transcript-viewer.js`
Full transcript modal viewer with search highlighting.

```javascript
export function openTranscriptViewer(transcriptId);
export function closeTranscriptViewer();
export function highlightInViewer(searchText);
```

### Workspace Module

#### `ui/workspace.js`
3-panel resizable workspace layout manager.

```javascript
export function initWorkspace();
export function showKGPanel();
export function hideKGPanel();
export function resizePanels(chatWidth, kgWidth);
```

**Layouts**:
- `CHAT_ONLY`: Chat panel 100% width
- `CHAT_KG`: Chat + KG split (resizable divider)

**Features**:
- Drag-to-resize divider between panels
- Minimum width enforcement (300px)
- Panel widths persisted to localStorage
- Cytoscape auto-resize on drag end

### Upload Module

#### `upload/upload.js`
Video file upload handling.

```javascript
export function initFileUpload();
export async function handleFileSelect(event);
```

**Validation**:
- Max file size: 500MB
- Accepted formats: `.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.m4v`

### Knowledge Graph Modules

#### `kg/index.js`
Aggregates and re-exports all KG module functions.

#### `kg/api.js`
KG API client with unified error handling.

```javascript
export const kgClient = {
    listProjects(),
    createProject(name),
    getProject(projectId),
    getConfirmations(projectId),
    confirmDiscovery(projectId, discoveryId, confirmed),
    getGraphStats(projectId),
    exportGraph(projectId, format),        // Single project export
    batchExportProjects(projectIds, format), // Multi-project batch export
    deleteProject(projectId)
};
```

#### `kg/graph.js`
Cytoscape.js graph visualization.

```javascript
export function initKGGraph(container, graphData);
export function changeGraphLayout(layoutName);
export function fitGraphView();
export function resetGraphView();
```

#### `kg/search.js`
Graph search and filtering functionality.

```javascript
export function initGraphSearch();
export function toggleTypeFilter(type);      // Multi-select filtering
export function clearAllFilters();           // Reset all filters
export function performGraphSearch(query);   // Full-text search
export function hideSearchResults();
```

**Features**:
- Full-text search across node labels, aliases, descriptions
- Multi-select entity type filtering via legend clicks
- Filter chips with color-coded borders
- Visual feedback: matching nodes highlighted, others dimmed (opacity 0.25)
- Match count display ("X of Y entities")

**Layouts**: `cose` (force-directed), `grid`, `circle`, `breadthfirst` (hierarchical)

#### `kg/evidence.js`
Node evidence/citation viewer showing source transcript excerpts.

```javascript
export async function fetchNodeEvidence(projectId, nodeId);
export function renderEvidenceSection(evidence);
```

**Features**:
- Fetches citation evidence from `/kg/projects/{id}/nodes/{id}/evidence`
- Renders blockquote-style evidence with source metadata
- "View" button jumps to transcript viewer with search highlighting
- Graceful degradation if evidence unavailable

**Entity Type Colors**:
| Type | Color |
|------|-------|
| Person, Character | Blue (#3b82f6) |
| Organization, Group | Green (#10b981) |
| Event | Amber (#f59e0b) |
| Location, Place | Red (#ef4444) |
| Concept, Theme | Purple (#8b5cf6) |
| Technology | Cyan (#06b6d4) |
| Product, Object | Pink (#ec4899) |

---

## Dependency Graph

```
main.js
├── core/state.js
├── ui/theme.js, toast.js, sidebar.js, header.js, mobile.js
├── chat/session.js, send.js, status.js
├── panels/history.js, transcripts.js
├── jobs/jobs.js
├── upload/upload.js
└── kg/index.js

chat/messages.js
├── core/config.js (PURIFY_CONFIG)
├── core/utils.js (copyToClipboard)
├── ui/toast.js (showToast)
└── [CDN] window.marked, window.DOMPurify

chat/send.js
├── core/state.js
├── core/config.js (MAX_RETRIES, RETRY_DELAY_MS)
├── core/utils.js (sleep)
├── chat/messages.js
├── chat/activity.js (startActivityStream, stopActivityStream)
└── ui/toast.js

kg/graph.js
├── core/state.js (cytoscapeInstance)
└── [CDN] window.cytoscape
```

---

## Global Window Exports

Functions exposed on `window` for inline `onclick` handlers in HTML:

```javascript
// History panel
window.loadSession
window.deleteHistoryItem

// Transcripts panel
window.downloadTranscript
window.deleteTranscript

// KG Panel (prefixed with kg_)
window.kg_handleDropdownSelect
window.kg_deleteKGProject
window.kg_loadKGProjects
window.kg_selectKGProject
window.kg_confirmKGDiscovery
window.kg_toggleTypeFilter      // Multi-select type filtering
window.kg_clearAllFilters       // Reset all filters
window.kg_navigateToNode
window.kg_selectNodeById

// KG Actions
window.createKGProject
window.exportKGGraph
window.batchExportKGProjects  // Export all projects as single ZIP

// KG Graph Controls
window.changeGraphLayout
window.fitGraphView
window.resetGraphView

// Jobs
window.cancelJob
window.loadJobs
window.sendMessage   // Enables job callbacks to trigger agent messages

// Audit Trail
window.loadAuditEvents
window.toggleAuditPanel
window.refreshAuditStats
```

---

## Initialization Flow

```javascript
// main.js - DOMContentLoaded handler
document.addEventListener('DOMContentLoaded', () => {
    // 1. Reset state for clean UX
    resetKGState();

    // 2. Initialize DOM references
    initDOMReferences();

    // 3. Initialize UI components
    initToastContainer();
    initTheme();
    initMobileNav();
    initSidebarCollapse();
    initHeaderDropdowns();

    // 4. Initialize file upload
    initFileUpload();

    // 5. Initialize event listeners
    initEventListeners();

    // 6. Pre-load sidebar data
    loadHistory();
    loadTranscripts();
    loadKGProjects();
    loadJobs();  // Initialize jobs sidebar

    // 7. Start status polling
    startStatusPolling();

    // 8. Initialize graph search
    initGraphSearch();

    // 9. Initialize keyboard shortcuts
    initKeyboardShortcuts();

    // 10. Initialize chat session
    initSession();
});
```

---

## Keyboard Shortcuts

Global keyboard shortcuts initialized via `initKeyboardShortcuts()` in `main.js`:

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` / `Cmd+Enter` | Send chat message |
| `Escape` | Close modals/inspectors (priority: inspector → search → sidebar) |

---

## Loading Skeletons

Skeleton loaders provide visual feedback while data loads:

```css
.skeleton-line {
    background: linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%);
    animation: skeleton-shimmer 1.5s infinite;
}
```

**Locations**:
- `panels/history.js` — Session history list
- `panels/transcripts.js` — Transcript library list
- `kg/panel.js` — KG project dropdown

---

## Security

### XSS Protection
- All agent messages sanitized via DOMPurify
- `escapeHtml()` for user-controlled text
- Never use `innerHTML` with unsanitized content

### Session Isolation
- Session ID stored in `sessionStorage` (tab-scoped)
- UUID v4 generated client-side

### File Validation
- 500MB upload limit enforced client-side
- File extension whitelist

---

## Error Handling Patterns

### API Errors
All API modules follow consistent error handling:

```javascript
async function apiCall() {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            await handleApiError(response, 'Default message');
        }
        return response.json();
    } catch (e) {
        if (e.name === 'TypeError') {
            throw new Error('Network error');
        }
        throw e;
    }
}
```

### Unified Error Schema
Frontend parses the unified `APIError` schema:

```javascript
{
    error: {
        code: "ERROR_CODE",
        message: "Human-readable message",
        detail: "Technical details",
        hint: "Actionable suggestion",
        retryable: true/false
    }
}
```

---

## Common Pitfalls

### DOM Element Selectors in state.js

**CRITICAL:** When adding new DOM references in `initDOMReferences()`, always verify selectors match the actual HTML:

```javascript
// ✅ CORRECT: Use getElementById for elements with IDs (preferred)
state.kgCaret = document.getElementById('kg-caret');

// ❌ WRONG: Class selector typos fail silently
state.kgCaret = document.querySelector('#kg-toggle .sidebar-caret');  // Should be .panel-caret!
```

**Why this matters:**
- Wrong selectors return `null` without errors
- Guard clauses like `if (!state.element) return;` exit silently
- UI appears broken with no console errors
- Debugging becomes extremely difficult

**After refactoring:** Always test panel toggles, dropdowns, and interactive elements manually.

### Hidden Elements and Pointer Events

When debugging "can't click element" issues:

1. **Check parent visibility first** — Element may be inside a container with:
   - `max-height: 0` (collapsed panel)
   - `opacity: 0` (hidden state)
   - `overflow: hidden` (clipped content)

2. **Elements exist in DOM but are invisible** — Browser automation tools (Playwright) detect them but clicks fail

3. **Cryptic error messages** — "Element X intercepts pointer events" often means the target is hidden, not that X is overlapping

**Fix pattern:** Verify the toggle/expand mechanism works before debugging z-index or pointer-events CSS.

---

## Browser Compatibility

- Modern browsers with ES Module support
- No transpilation or build step required
- CDN dependencies loaded before modules

```html
<!-- Load CDN dependencies first -->
<script src="https://cdn.jsdelivr.net/npm/marked@11.0.0/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.8/dist/purify.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/cytoscape@3.28.1/dist/cytoscape.min.js"></script>

<!-- Then load ES modules -->
<script type="module" src="/static/js/main.js"></script>
```
