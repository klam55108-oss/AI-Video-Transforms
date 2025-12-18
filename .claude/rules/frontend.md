---
paths: app/static/**/*.*, app/templates/**/*.*
---

# Frontend Conventions

## Stack

- **ES Modules** — 26 modules in `app/static/js/`
- **Tailwind CSS** via CDN (no build step)
- **Jinja2** templates in `app/templates/`
- **CDN Libraries**: Marked.js, DOMPurify, Cytoscape.js

## Module Structure

```
app/static/js/
├── main.js           # Entry point, aggregates all modules
├── core/             # state.js, config.js, utils.js
├── ui/               # theme.js, toast.js, sidebar.js, header.js, mobile.js
├── chat/             # messages.js, send.js, session.js, status.js
├── panels/           # history.js, transcripts.js
├── jobs/             # jobs.js
├── upload/           # upload.js
└── kg/               # 9 modules (api, panel, graph, search, inspector, etc.)
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
