---
paths: app/static/**/*.*, app/templates/**/*.*
---

# Frontend Conventions

## Stack

- **ES Modules** — 37 modules in `app/static/js/`
- **Tailwind CSS** via CDN (no build step)
- **Jinja2** templates in `app/templates/`
- **CDN Libraries**: Marked.js, DOMPurify, Cytoscape.js

## Module Structure

```
app/static/js/
├── main.js           # Entry point, aggregates all modules
├── core/             # state.js, config.js, utils.js
├── ui/               # theme.js, toast.js, sidebar.js, header.js, mobile.js
├── chat/             # messages.js, send.js, session.js, status.js, activity.js
├── panels/           # history.js, transcripts.js, transcript-search.js, transcript-viewer.js
├── jobs/             # jobs.js, step-progress.js
├── upload/           # upload.js
├── audit/            # index.js, api.js, panel.js (audit trail)
├── ui/               # workspace.js (3-panel resizable layout)
└── kg/               # 12 modules (api, panel, graph, search, inspector, evidence, merge-modal, etc.)
```

See @FRONTEND.md for complete module documentation.

## DOM Reference Pattern

```javascript
// ✅ Correct: Lazy lookup (consistent with state.js pattern)
function getElement() {
    return document.getElementById('my-element');
}

// ✅ Correct: Use centralized state for shared refs
import { state } from '../core/state.js';
state.kgPanel?.addEventListener('click', handler);

// ❌ Wrong: Module-level DOM reference
const element = document.getElementById('my-element');  // Fragile timing
```

## Security (CRITICAL)

- **ALWAYS** use DOMPurify for XSS sanitization on rendered content
- **NEVER** trust user input in DOM manipulation
- **ALWAYS** escape dynamic content in Jinja2: `{{ variable }}`
- **NEVER** use `innerHTML` with unsanitized content
- **ALWAYS** use `escapeHtml()` from `core/utils.js` for user text

## Session Management

- Store session ID in `sessionStorage` (tab isolation)
- Generate UUID v4 client-side via `crypto.randomUUID()`
- Poll `/status/{id}` for agent processing state

## API Communication

- Use `fetch()` for all API calls
- Handle unified error schema (code, message, detail, hint, retryable)
- Show cost/usage data from response

## Activity Streaming

Real-time agent activity displayed during message processing:

```javascript
import { startActivityStream, stopActivityStream } from './chat/activity.js';
import { updateLoadingActivity } from './chat/messages.js';

// Start SSE stream before sending message
startActivityStream(updateLoadingActivity);

// Stop stream when response completes or errors
stopActivityStream();
```

**Activity Types**: `thinking`, `tool_use`, `tool_result`, `subagent`, `file_save`, `completed`

**Timing**: Activity debounced at 150ms to smooth rapid tool sequences. Polling fallback uses 1000ms intervals.

## Job Sidebar & Auto-Continuation

Jobs panel provides real-time tracking with auto-continuation callbacks:

```javascript
// Sidebar tracks all active jobs with live progress
loadJobs();           // Fetch and render sidebar
toggleJobsPanel();    // Expand/collapse

// Auto-continuation: when job completes, trigger agent callback
triggerJobCompletionCallback(job);  // Sends hidden message to agent
triggerJobFailureCallback(job);     // Handles errors via agent
```

**Pattern**: `window.sendMessage(message, false)` sends without UI display, enabling seamless agent responses.

**Race Condition Handling**: `sendMessageWhenReady()` retries callbacks at 500ms intervals (max 10s) until `state.isProcessing` clears.

## Global Window Exports

Functions exposed for HTML `onclick` handlers (prefixed to avoid conflicts):

```javascript
// KG functions use kg_ prefix
window.kg_selectKGProject = selectKGProject;
window.kg_deleteKGProject = deleteKGProject;

// KG export functions
window.exportKGGraph = exportKGGraph;
window.batchExportKGProjects = batchExportKGProjects;

// Other modules
window.loadSession = loadSession;
window.cancelJob = cancelJob;
window.loadJobs = loadJobs;
window.sendMessage = sendMessage;  // For job callbacks
```

## File Uploads

- Max 500MB file size
- Allowed: `.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.m4v`
- Use FormData for multipart uploads

## Design Tokens (style.css)

Use semantic tokens instead of raw colors for theme consistency:

```css
/* ✅ Correct: Semantic tokens */
color: var(--color-action-text);
background: var(--color-action);
border-color: var(--color-danger);

/* ❌ Wrong: Raw color values */
color: #00d9ff;
background: cyan;
```

**Core Semantic Tokens**:
| Token | Purpose |
|-------|---------|
| `--color-action` | Primary CTA buttons, links |
| `--color-action-text` | WCAG-compliant text on backgrounds |
| `--color-interactive` | Secondary interactive elements |
| `--color-success/warning/danger/info` | Status indicators |
| `--accent-text` | Text using accent color (darker for light mode) |

**WCAG Compliance**: Light mode uses `--accent-text: #b45309` (darker amber) instead of `#f59e0b` to achieve 4.56:1 contrast ratio on cream backgrounds.

## Empty State & Initializing

The empty state shows **pipeline visualization** + **initializing indicator**:

- **Pipeline**: 3-step informational diagram (Upload → Transcribe → Knowledge Graph)
- **Not interactive**: Steps are visual only - users interact via sidebar upload button or chat
- **Initializing**: Pulsing robot icon with "Preparing your AI assistant..."
- **Flow**: `initSession()` → empty state visible → greeting arrives → `hideEmptyState()`

**Reduced Motion**: All animations respect `prefers-reduced-motion`. When enabled, uses instant transitions while preserving color/opacity feedback.
