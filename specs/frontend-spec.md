# Frontend Implementation Spec

## Overview

This spec covers all frontend changes for the VideoAgent web application, including UI features, error handling improvements, and integration with new backend endpoints.

---

## Target Files

| File | Action | Description |
|------|--------|-------------|
| `templates/index.html` | MODIFY | Sidebar panels, status indicator, attachment button |
| `static/script.js` | MODIFY | Status polling, history/transcripts, file upload, error handling |
| `static/style.css` | MODIFY | New component styles (optional) |

---

## Part 1: HTML Template Updates

### 1.1 Add DOMPurify CDN

**File:** `templates/index.html:12` (after marked.js)

```html
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js"></script>
```

### 1.2 Update Status Indicator with IDs

**File:** `templates/index.html:85-92`

Replace the static status indicator with:
```html
<div class="flex items-center space-x-2 px-3 py-1.5 bg-slate-50 rounded-full border border-slate-200">
    <span id="status-indicator" class="relative flex h-2.5 w-2.5">
        <span id="status-ping" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span>
        <span id="status-dot" class="relative inline-flex rounded-full h-2.5 w-2.5 bg-yellow-500"></span>
    </span>
    <span id="status-label" class="text-xs font-medium text-slate-600">Initializing...</span>
</div>
```

### 1.3 Update Sidebar Navigation with Collapsible Panels

**File:** `templates/index.html:42-59`

Replace the menu items section with:
```html
<!-- Menu Items -->
<div class="space-y-1">
    <p class="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Workspace</p>

    <!-- Current Session (Active) -->
    <a href="#" class="group flex items-center px-3 py-2 text-sm font-medium rounded-md bg-white/10 text-white shadow-inner">
        <i class="ph-fill ph-chat-circle-text text-lg mr-3 text-blue-400"></i>
        Current Session
    </a>

    <!-- History Section (Collapsible) -->
    <div id="history-section">
        <button id="history-toggle" class="group flex items-center px-3 py-2 text-sm font-medium rounded-md text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors w-full text-left">
            <i class="ph-fill ph-clock-counter-clockwise text-lg mr-3 text-slate-500 group-hover:text-slate-400"></i>
            History
            <i id="history-caret" class="ph-bold ph-caret-right ml-auto text-slate-500 transition-transform duration-200"></i>
        </button>
        <div id="history-list" class="hidden ml-6 mt-1 space-y-1 max-h-48 overflow-y-auto">
            <p class="text-xs text-slate-500 px-2 py-1">Loading...</p>
        </div>
    </div>

    <!-- Transcripts Section (Collapsible) -->
    <div id="transcripts-section">
        <button id="transcripts-toggle" class="group flex items-center px-3 py-2 text-sm font-medium rounded-md text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors w-full text-left">
            <i class="ph-fill ph-folder-open text-lg mr-3 text-slate-500 group-hover:text-slate-400"></i>
            Transcripts
            <i id="transcripts-caret" class="ph-bold ph-caret-right ml-auto text-slate-500 transition-transform duration-200"></i>
        </button>
        <div id="transcripts-list" class="hidden ml-6 mt-1 space-y-1 max-h-48 overflow-y-auto">
            <p class="text-xs text-slate-500 px-2 py-1">Loading...</p>
        </div>
    </div>
</div>
```

### 1.4 Update Attachment Button with ID

**File:** `templates/index.html:110-112`

```html
<button id="attach-btn" type="button" title="Attach video file" class="p-2 text-slate-400 hover:text-slate-600 transition-colors mb-0.5">
    <i class="ph-bold ph-paperclip text-lg"></i>
</button>
```

---

## Part 2: JavaScript - Core Updates

### 2.1 Add New Element References and State

**File:** `static/script.js` (after existing element references, around line 16)

```javascript
// New element references
const attachBtn = document.getElementById('attach-btn');
const historyToggle = document.getElementById('history-toggle');
const historyList = document.getElementById('history-list');
const historyCaret = document.getElementById('history-caret');
const transcriptsToggle = document.getElementById('transcripts-toggle');
const transcriptsList = document.getElementById('transcripts-list');
const transcriptsCaret = document.getElementById('transcripts-caret');

// State
let isProcessing = false;
let statusInterval = null;
let fileInput = null;

// Configuration
const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 1000;
const STATUS_POLL_INTERVAL_MS = 3000;
```

### 2.2 Update Session Storage (Security Fix)

**File:** `static/script.js:3-8`

Replace localStorage with sessionStorage:
```javascript
function getSessionId() {
    let sessionId = sessionStorage.getItem('agent_session_id');
    if (!sessionId) {
        sessionId = crypto.randomUUID();
        sessionStorage.setItem('agent_session_id', sessionId);
    }
    return sessionId;
}
```

### 2.3 Add XSS Protection to Message Rendering

**File:** `static/script.js:86` (in addMessage function)

Replace:
```javascript
bubble.innerHTML = marked.parse(text);
```

With:
```javascript
// DOMPurify configuration for safe markdown rendering
const PURIFY_CONFIG = {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li',
                   'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'a', 'table',
                   'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'span', 'div'],
    ALLOWED_ATTR: ['href', 'class', 'target', 'rel'],
    ALLOW_DATA_ATTR: false
};

bubble.innerHTML = DOMPurify.sanitize(marked.parse(text), PURIFY_CONFIG);
```

---

## Part 3: JavaScript - Status Polling

### 3.1 Add Status Polling Functions

**File:** `static/script.js` (add new section)

```javascript
// ============================================
// Status Polling
// ============================================

function startStatusPolling() {
    updateStatus();
    statusInterval = setInterval(updateStatus, STATUS_POLL_INTERVAL_MS);
}

function stopStatusPolling() {
    if (statusInterval) {
        clearInterval(statusInterval);
        statusInterval = null;
    }
}

async function updateStatus() {
    try {
        const response = await fetch(`/status/${sessionId}`);
        if (!response.ok) return;

        const data = await response.json();
        renderStatus(data.status);
    } catch (e) {
        renderStatus('error');
    }
}

function renderStatus(status) {
    const ping = document.getElementById('status-ping');
    const dot = document.getElementById('status-dot');
    const label = document.getElementById('status-label');

    if (!ping || !dot || !label) return;

    const states = {
        initializing: { color: 'yellow', text: 'Initializing...' },
        ready: { color: 'emerald', text: 'Agent Ready' },
        processing: { color: 'blue', text: 'Processing...' },
        error: { color: 'red', text: 'Error' }
    };

    const state = states[status] || states.error;

    // Update colors
    ping.className = `animate-ping absolute inline-flex h-full w-full rounded-full bg-${state.color}-400 opacity-75`;
    dot.className = `relative inline-flex rounded-full h-2.5 w-2.5 bg-${state.color}-500`;
    label.textContent = state.text;

    // Pause animation when ready (less distracting)
    if (status === 'ready') {
        ping.classList.remove('animate-ping');
    }
}
```

---

## Part 4: JavaScript - History Management

### 4.1 Add History Functions

**File:** `static/script.js` (add new section)

```javascript
// ============================================
// History Management
// ============================================

async function loadHistory() {
    try {
        const response = await fetch('/history');
        if (!response.ok) throw new Error('Failed to load history');
        const data = await response.json();
        renderHistoryList(data.sessions);
    } catch (e) {
        console.error('History load failed:', e);
        if (historyList) {
            historyList.innerHTML = '<p class="text-xs text-slate-500 px-2 py-1">Failed to load</p>';
        }
    }
}

function renderHistoryList(sessions) {
    if (!historyList) return;

    if (sessions.length === 0) {
        historyList.innerHTML = '<p class="text-xs text-slate-500 px-2 py-1">No history yet</p>';
        return;
    }

    historyList.innerHTML = sessions.map(s => `
        <button
            onclick="loadSession('${escapeHtml(s.session_id)}')"
            class="w-full text-left px-2 py-1.5 text-xs text-slate-400 hover:bg-slate-700 hover:text-white rounded transition-colors truncate"
            title="${escapeHtml(s.title || 'Untitled')}"
        >
            <div class="truncate font-medium">${escapeHtml(s.title || 'Untitled')}</div>
            <div class="text-slate-500 text-[10px]">${formatRelativeTime(s.updated_at)} · ${s.message_count} msgs</div>
        </button>
    `).join('');
}

function toggleHistoryPanel() {
    if (!historyList || !historyCaret) return;

    const isHidden = historyList.classList.contains('hidden');
    historyList.classList.toggle('hidden');
    historyCaret.style.transform = isHidden ? 'rotate(90deg)' : '';

    // Load data when opening
    if (isHidden) {
        loadHistory();
    }
}

async function loadSession(loadSessionId) {
    if (loadSessionId === sessionId) return;

    if (isProcessing) {
        if (!confirm('A message is being processed. Switch session anyway?')) {
            return;
        }
    }

    // Close current session
    try {
        await fetch(`/chat/${sessionId}`, { method: 'DELETE' });
    } catch (e) {
        console.warn('Failed to close current session:', e);
    }

    // Switch to new session
    sessionStorage.setItem('agent_session_id', loadSessionId);
    window.location.reload();
}

async function deleteHistoryItem(historySessionId) {
    if (!confirm('Delete this session history?')) return;

    try {
        await fetch(`/history/${historySessionId}`, { method: 'DELETE' });
        loadHistory(); // Refresh list
    } catch (e) {
        console.error('Delete failed:', e);
    }
}
```

---

## Part 5: JavaScript - Transcripts Management

### 5.1 Add Transcripts Functions

**File:** `static/script.js` (add new section)

```javascript
// ============================================
// Transcripts Management
// ============================================

async function loadTranscripts() {
    try {
        const response = await fetch('/transcripts');
        if (!response.ok) throw new Error('Failed to load transcripts');
        const data = await response.json();
        renderTranscriptsList(data.transcripts);
    } catch (e) {
        console.error('Transcripts load failed:', e);
        if (transcriptsList) {
            transcriptsList.innerHTML = '<p class="text-xs text-slate-500 px-2 py-1">Failed to load</p>';
        }
    }
}

function renderTranscriptsList(transcripts) {
    if (!transcriptsList) return;

    if (transcripts.length === 0) {
        transcriptsList.innerHTML = '<p class="text-xs text-slate-500 px-2 py-1">No transcripts yet</p>';
        return;
    }

    transcriptsList.innerHTML = transcripts.map(t => `
        <div class="flex items-center justify-between px-2 py-1.5 text-xs text-slate-400 hover:bg-slate-700 rounded group">
            <div class="truncate flex-1 mr-2" title="${escapeHtml(t.filename)}">
                <div class="font-medium truncate">${escapeHtml(t.filename)}</div>
                <div class="text-slate-500 text-[10px]">${formatFileSize(t.file_size)} · ${formatRelativeTime(t.created_at)}</div>
            </div>
            <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button onclick="downloadTranscript('${t.id}')" title="Download" class="p-1 hover:text-white">
                    <i class="ph-bold ph-download-simple text-sm"></i>
                </button>
                <button onclick="deleteTranscript('${t.id}')" title="Delete" class="p-1 hover:text-red-400">
                    <i class="ph-bold ph-trash text-sm"></i>
                </button>
            </div>
        </div>
    `).join('');
}

function toggleTranscriptsPanel() {
    if (!transcriptsList || !transcriptsCaret) return;

    const isHidden = transcriptsList.classList.contains('hidden');
    transcriptsList.classList.toggle('hidden');
    transcriptsCaret.style.transform = isHidden ? 'rotate(90deg)' : '';

    // Load data when opening
    if (isHidden) {
        loadTranscripts();
    }
}

function downloadTranscript(id) {
    window.open(`/transcripts/${id}/download`, '_blank');
}

async function deleteTranscript(id) {
    if (!confirm('Delete this transcript? The file will be removed.')) return;

    try {
        await fetch(`/transcripts/${id}`, { method: 'DELETE' });
        loadTranscripts(); // Refresh list
    } catch (e) {
        console.error('Delete failed:', e);
        alert('Failed to delete transcript');
    }
}
```

---

## Part 6: JavaScript - File Upload

### 6.1 Add File Upload Functions

**File:** `static/script.js` (add new section)

```javascript
// ============================================
// File Upload
// ============================================

function initFileUpload() {
    // Create hidden file input
    fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.mp4,.mkv,.avi,.mov,.webm,.m4v';
    fileInput.style.display = 'none';
    document.body.appendChild(fileInput);

    // Wire up attachment button
    if (attachBtn) {
        attachBtn.addEventListener('click', () => {
            if (isProcessing) {
                alert('Please wait for the current operation to complete');
                return;
            }
            fileInput.click();
        });
    }

    // Handle file selection
    fileInput.addEventListener('change', handleFileSelect);
}

async function handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    // Validate file size (500MB limit)
    const MAX_SIZE = 500 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
        addMessage(`**Error:** File too large. Maximum size is 500MB.`, 'agent');
        fileInput.value = '';
        return;
    }

    // Show upload message
    addMessage(`Uploading: ${file.name} (${formatFileSize(file.size)})...`, 'user');
    const loadingId = showLoading();

    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('session_id', sessionId);

        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        removeLoading(loadingId);

        if (data.success) {
            // Automatically request transcription
            addMessage(`File uploaded successfully. Starting transcription...`, 'agent');

            // Trigger transcription request
            const message = `Please transcribe this uploaded video file: ${data.file_path}`;
            await sendMessage(message, false); // Don't show in UI, it's automated
        } else {
            addMessage(`**Upload Error:** ${data.error || 'Unknown error'}`, 'agent');
        }
    } catch (e) {
        removeLoading(loadingId);
        addMessage(`**Upload Error:** ${e.message}`, 'agent');
    }

    // Reset file input for next upload
    fileInput.value = '';
}
```

---

## Part 7: JavaScript - Error Handling Improvements

### 7.1 Refactor sendMessage with Retry Logic

**File:** `static/script.js`

Add helper function:
```javascript
// ============================================
// Utilities
// ============================================

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatRelativeTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
}

function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
```

Add sendMessage helper:
```javascript
async function sendMessage(message, showInUI = true) {
    if (isProcessing) {
        console.warn('Already processing a message');
        return false;
    }

    isProcessing = true;

    if (showInUI) {
        addMessage(message, 'user');
    }

    const loadingId = showLoading();
    let lastError = null;

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId, message })
            });

            // Handle specific status codes
            if (response.status === 503) {
                lastError = new Error('Server busy');
                await sleep(RETRY_DELAY_MS * (attempt + 1));
                continue;
            }

            if (response.status === 504) {
                removeLoading(loadingId);
                addMessage('**Timeout:** The operation took too long. Please try again with a shorter video.', 'agent');
                isProcessing = false;
                return false;
            }

            if (response.status === 422) {
                const errorData = await response.json();
                removeLoading(loadingId);
                addMessage(`**Validation Error:** ${errorData.detail || 'Invalid input'}`, 'agent');
                isProcessing = false;
                return false;
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Server error: ${response.status}`);
            }

            const data = await response.json();
            removeLoading(loadingId);
            addMessage(data.response, 'agent');

            // Refresh transcripts list in case a new one was created
            if (transcriptsList && !transcriptsList.classList.contains('hidden')) {
                loadTranscripts();
            }

            isProcessing = false;
            return true;

        } catch (error) {
            lastError = error;

            // Only retry network errors, not server errors
            if (attempt < MAX_RETRIES && error.name === 'TypeError') {
                console.log(`Network error, retry ${attempt + 1}/${MAX_RETRIES}...`);
                await sleep(RETRY_DELAY_MS * (attempt + 1));
            } else {
                break;
            }
        }
    }

    // All retries failed
    removeLoading(loadingId);
    addMessage(`**Error:** ${lastError?.message || 'Unknown error'}. Please try again.`, 'agent');
    isProcessing = false;
    return false;
}
```

### 7.2 Update Form Submit Handler

**File:** `static/script.js:196-241`

Replace the existing form submit handler:
```javascript
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const message = userInput.value.trim();
    if (!message) return;

    // Clear input immediately for better UX
    userInput.value = '';
    userInput.style.height = '44px';

    // Disable inputs during processing
    userInput.disabled = true;
    sendBtn.disabled = true;

    await sendMessage(message);

    // Re-enable inputs
    userInput.disabled = false;
    sendBtn.disabled = false;
    userInput.focus();
});
```

### 7.3 Update Reset Handler with Race Condition Fix

**File:** `static/script.js:244-256`

Replace the reset handler:
```javascript
resetBtn.addEventListener('click', async () => {
    if (isProcessing) {
        if (!confirm('A message is being processed. Reset anyway?')) {
            return;
        }
        isProcessing = false;
    }

    if (confirm('Start a new transcription session? Current chat will be cleared.')) {
        // Stop status polling
        stopStatusPolling();

        // Close current session on server
        try {
            await fetch(`/chat/${sessionId}`, { method: 'DELETE' });
        } catch (e) {
            console.warn('Failed to close session on server:', e);
        }

        // Clear session storage and reload
        sessionStorage.removeItem('agent_session_id');
        window.location.reload();
    }
});
```

---

## Part 8: JavaScript - Initialization

### 8.1 Update Initialization Code

**File:** `static/script.js` (at the bottom)

Replace/update the initialization:
```javascript
// ============================================
// Initialization
// ============================================

function initEventListeners() {
    // Sidebar toggles
    if (historyToggle) {
        historyToggle.addEventListener('click', toggleHistoryPanel);
    }
    if (transcriptsToggle) {
        transcriptsToggle.addEventListener('click', toggleTranscriptsPanel);
    }
}

function initSidebarData() {
    // Pre-load sidebar data (collapsed state)
    loadHistory();
    loadTranscripts();
}

// Run initialization when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initFileUpload();
    initEventListeners();
    initSidebarData();
    startStatusPolling();
});

// Initialize session
initSession();
```

---

## Testing Checklist

### XSS Protection
- [x] Inject `<script>alert('xss')</script>` in message - should be sanitized ✅ TESTED: displayed as plain text, no alert
- [x] Inject `<img src=x onerror="alert('xss')">` - should be sanitized ✅ TESTED: displayed as plain text, no alert
- [x] Markdown still renders correctly (bold, code, lists) ✅ TESTED: agent response showed proper formatting

### Status Indicator
- [ ] Shows "Initializing" on page load ⚠️ PARTIAL: verified in HTML source, but page loads too fast to catch visually
- [x] Changes to "Ready" after greeting received ✅ TESTED: saw "Agent Ready" in UI
- [x] Changes to "Processing" during message handling ✅ TESTED: caught "Processing..." during message send
- [ ] Shows "Error" if session fails ❌ NOT TESTED: requires network failure/server crash

### History Panel
- [x] Toggle opens/closes panel ✅ TESTED: clicked toggle, panel appeared/disappeared
- [x] Shows previous sessions sorted by date ✅ TESTED: saw "Just now", "1m ago" ordering
- [x] Clicking session switches to it ✅ TESTED: clicked session, page reloaded with new session
- [x] Shows message count for each session ✅ TESTED: saw "3 msgs", "7 msgs", "8 msgs"

### Transcripts Panel
- [x] Toggle opens/closes panel ✅ TESTED: clicked toggle, panel appeared/disappeared
- [x] Shows saved transcripts ✅ TESTED: created mock transcript, appeared in list
- [x] Download button downloads file ✅ TESTED: clicked, opened new tab with /transcripts/{id}/download
- [x] Delete button removes transcript ✅ TESTED: clicked, confirmed dialog, transcript removed

### File Upload
- [x] Attachment button opens file picker ✅ TESTED: clicked, file chooser modal appeared
- [x] Only accepts video file extensions ✅ TESTED: verified accept=".mp4,.mkv,.avi,.mov,.webm,.m4v"
- [x] Shows upload progress ✅ TESTED: saw "Uploading: test_video.mp4 (2.2 KB)..."
- [x] Auto-triggers transcription on success ✅ TESTED: saw "File uploaded successfully. Starting transcription..."
- [ ] Shows error for oversized files ❌ NOT TESTED: requires 500MB+ file (code verified only)

### Error Handling
- [ ] Network errors trigger retry ❌ NOT TESTED: requires network simulation (code verified only)
- [ ] 504 timeout shows appropriate message ❌ NOT TESTED: requires backend timeout (code verified only)
- [ ] 422 validation shows error detail ❌ NOT TESTED: requires validation failure (code verified only)
- [x] Reset works even during processing ✅ TESTED: reset dialog appeared and worked

### Session Management
- [x] Session ID stored in sessionStorage (not localStorage) ✅ TESTED: JS eval showed sessionStorage has ID, localStorage null
- [x] New tab gets new session ID ✅ TESTED: tab1 had different UUID than tab2
- [x] Reset clears session and creates new one ✅ TESTED: before/after reset showed different UUIDs

---

## Implementation Order

1. **DOMPurify integration** - Add CDN and sanitization
2. **Session storage fix** - Replace localStorage with sessionStorage
3. **Status indicator** - Add IDs, polling, rendering
4. **Utility functions** - escapeHtml, formatRelativeTime, formatFileSize
5. **History panel** - HTML structure, toggle, load, render
6. **Transcripts panel** - HTML structure, toggle, load, render
7. **File upload** - Input creation, button handler, upload logic
8. **sendMessage refactor** - Extract from form handler, add retry
9. **Form handler update** - Use sendMessage helper
10. **Reset handler update** - Fix race conditions
11. **Initialization update** - Wire everything together

---

## CSS Additions (Optional)

**File:** `static/style.css`

Add smooth transitions for sidebar panels:
```css
/* Sidebar panel transitions */
#history-list,
#transcripts-list {
    transition: max-height 0.2s ease-out;
}

/* Caret rotation */
#history-caret,
#transcripts-caret {
    transition: transform 0.2s ease-out;
}

/* Custom scrollbar for sidebar lists */
#history-list::-webkit-scrollbar,
#transcripts-list::-webkit-scrollbar {
    width: 4px;
}

#history-list::-webkit-scrollbar-track,
#transcripts-list::-webkit-scrollbar-track {
    background: transparent;
}

#history-list::-webkit-scrollbar-thumb,
#transcripts-list::-webkit-scrollbar-thumb {
    background: rgba(148, 163, 184, 0.3);
    border-radius: 2px;
}

#history-list::-webkit-scrollbar-thumb:hover,
#transcripts-list::-webkit-scrollbar-thumb:hover {
    background: rgba(148, 163, 184, 0.5);
}
```
