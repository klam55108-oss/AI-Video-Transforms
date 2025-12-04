// ============================================
// Session Management
// ============================================

function getSessionId() {
    let sessionId = sessionStorage.getItem('agent_session_id');
    if (!sessionId) {
        sessionId = crypto.randomUUID();
        sessionStorage.setItem('agent_session_id', sessionId);
    }
    return sessionId;
}

const sessionId = getSessionId();

// ============================================
// Element References
// ============================================

const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const chatMessages = document.getElementById('chat-messages');
const sendBtn = document.getElementById('send-btn');
const resetBtn = document.getElementById('reset-btn');

// New element references
const attachBtn = document.getElementById('attach-btn');
const historyToggle = document.getElementById('history-toggle');
const historyList = document.getElementById('history-list');
const historyCaret = document.getElementById('history-caret');
const transcriptsToggle = document.getElementById('transcripts-toggle');
const transcriptsList = document.getElementById('transcripts-list');
const transcriptsCaret = document.getElementById('transcripts-caret');

// Toast Container
let toastContainer = document.querySelector('.toast-container');
if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container';
    document.body.appendChild(toastContainer);
}

// ============================================
// State
// ============================================

let isProcessing = false;
let statusInterval = null;
let fileInput = null;

// ============================================
// Configuration
// ============================================

const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 1000;
const STATUS_POLL_INTERVAL_MS = 3000;

// DOMPurify configuration for safe markdown rendering
const PURIFY_CONFIG = {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li',
                   'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'a', 'table',
                   'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'span', 'div'],
    ALLOWED_ATTR: ['href', 'class', 'target', 'rel'],
    ALLOW_DATA_ATTR: false
};

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

function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        return navigator.clipboard.writeText(text);
    } else {
        // Fallback for non-secure context (e.g. http://localhost vs http://127.0.0.1)
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-9999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            document.execCommand('copy');
            return Promise.resolve();
        } catch (err) {
            return Promise.reject(err);
        } finally {
            document.body.removeChild(textArea);
        }
    }
}

// ============================================
// Toast Notifications
// ============================================

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const iconMap = {
        'info': 'ph-info',
        'success': 'ph-check-circle',
        'error': 'ph-warning-circle',
        'warning': 'ph-warning'
    };
    
    const iconClass = iconMap[type] || 'ph-info';

    toast.innerHTML = `
        <div class="flex items-center gap-3">
            <i class="ph-fill ${iconClass} text-lg opacity-80"></i>
            <span class="text-sm font-medium text-slate-700">${message}</span>
        </div>
        <button class="ml-4 text-slate-400 hover:text-slate-600">
            <i class="ph-bold ph-x"></i>
        </button>
    `;

    // Close button
    toast.querySelector('button').onclick = () => {
        toast.style.animation = 'fadeOut 0.2s forwards';
        setTimeout(() => toast.remove(), 200);
    };

    toastContainer.appendChild(toast);

    // Auto dismiss
    setTimeout(() => {
        if (toast.isConnected) {
            toast.style.animation = 'fadeOut 0.2s forwards';
            setTimeout(() => toast.remove(), 200);
        }
    }, 4000);
}

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
        showToast('Failed to delete history item', 'error');
    }
}

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
        showToast('Transcript deleted', 'success');
    } catch (e) {
        console.error('Delete failed:', e);
        showToast('Failed to delete transcript', 'error');
    }
}

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
                showToast('Please wait for the current operation to complete', 'warning');
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
        showToast('File too large. Maximum size is 500MB.', 'error');
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
            showToast('File uploaded successfully', 'success');
            // Automatically request transcription
            addMessage(`File uploaded successfully. Starting transcription...`, 'agent');

            // Trigger transcription request
            const message = `Please transcribe this uploaded video file: ${data.file_path}`;
            await sendMessage(message, false); // Don't show in UI, it's automated
        } else {
            showToast(data.error || 'Upload failed', 'error');
            addMessage(`**Upload Error:** ${data.error || 'Unknown error'}`, 'agent');
        }
    } catch (e) {
        removeLoading(loadingId);
        showToast('Upload failed', 'error');
        addMessage(`**Upload Error:** ${e.message}`, 'agent');
    }

    // Reset file input for next upload
    fileInput.value = '';
}

// ============================================
// UI Helpers
// ============================================

// Auto-resize textarea
userInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
    if(this.value === '') {
        this.style.height = '44px'; // Reset to min-height
    }
});

// Handle Enter to submit (Shift+Enter for newline)
userInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.requestSubmit();
    }
});

function scrollToBottom() {
    // Smooth scroll to bottom
    const scrollHeight = chatMessages.scrollHeight;
    chatMessages.scrollTo({
        top: scrollHeight,
        behavior: 'smooth'
    });
}

// Format usage stats for display
function formatUsageStats(usage) {
    if (!usage) return null;

    const totalTokens = (usage.input_tokens || 0) + (usage.output_tokens || 0);
    const cost = usage.total_cost_usd || 0;

    // Format cost with appropriate precision
    const costStr = cost < 0.01
        ? `$${cost.toFixed(4)}`
        : `$${cost.toFixed(2)}`;

    return {
        input: usage.input_tokens || 0,
        output: usage.output_tokens || 0,
        total: totalTokens,
        cost: costStr,
        cacheCreation: usage.cache_creation_tokens || 0,
        cacheRead: usage.cache_read_tokens || 0
    };
}

// Enhance markdown with code copy buttons
function enhanceMarkdown(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    
    // Process all code blocks
    const preTags = doc.querySelectorAll('pre');
    preTags.forEach(pre => {
        // Create wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'code-block-wrapper';
        
        // Wrap pre
        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(pre);
        
        // Add copy button
        const btn = document.createElement('button');
        btn.className = 'code-copy-btn';
        btn.innerHTML = '<i class="ph-bold ph-copy"></i> Copy';
        btn.onclick = async (e) => {
            const code = pre.querySelector('code')?.innerText || pre.innerText;
            try {
                await copyToClipboard(code);
                btn.innerHTML = '<i class="ph-bold ph-check"></i> Copied!';
                setTimeout(() => {
                    btn.innerHTML = '<i class="ph-bold ph-copy"></i> Copy';
                }, 2000);
            } catch (err) {
                console.error('Copy failed', err);
                showToast('Failed to copy to clipboard', 'error');
            }
        };
        
        wrapper.appendChild(btn);
    });
    
    return doc.body.innerHTML;
}

// Add Message to UI
function addMessage(text, sender, usage = null) {
    const isUser = sender === 'user';

    // Outer Container
    const container = document.createElement('div');
    container.className = isUser
        ? "flex items-start gap-4 flex-row-reverse"
        : "flex items-start gap-4";

    // Avatar
    const avatar = document.createElement('div');
    avatar.className = "flex-shrink-0";

    if (isUser) {
        avatar.innerHTML = `
            <div class="w-8 h-8 rounded-lg bg-blue-600 shadow-highlight-strong flex items-center justify-center">
                <span class="text-xs font-bold text-white">C</span>
            </div>
        `;
    } else {
        avatar.innerHTML = `
            <div class="w-8 h-8 rounded-lg bg-white border border-slate-200 shadow-sm flex items-center justify-center">
                <i class="ph-fill ph-robot text-blue-600"></i>
            </div>
        `;
    }

    // Message Content Wrapper
    const contentWrapper = document.createElement('div');
    contentWrapper.className = "flex-1 min-w-0";

    // Bubble
    const bubble = document.createElement('div');

    if (isUser) {
        // User Styling
        bubble.className = "bg-blue-600 text-white rounded-xl rounded-tr-none p-4 shadow-md shadow-highlight-strong text-sm leading-relaxed";
        bubble.textContent = text;
    } else {
        // Agent Styling
        bubble.className = "message-agent relative bg-white rounded-xl rounded-tl-none p-5 shadow-sm ring-1 ring-slate-900/5 text-sm text-slate-700 prose prose-slate max-w-none";
        
        // Sanitize first
        const safeHtml = DOMPurify.sanitize(marked.parse(text), PURIFY_CONFIG);
        // Then enhance with copy buttons
        bubble.innerHTML = enhanceMarkdown(safeHtml);
        
        // Bind click events for new elements (since innerHTML breaks event listeners)
        // We need to re-attach the event listeners because innerHTML string injection doesn't preserve function references
        // A better approach is to not use on* attributes in string but attach after.
        // Let's fix the enhanceMarkdown logic to handle this or just delegate.
        
        // Actually, since I used innerHTML in enhanceMarkdown to serialize back, the onclicks are gone if they were properties.
        // If they were attributes string (onclick="..."), they stay but scope is window.
        // My implementation in enhanceMarkdown assigns btn.onclick = function... which is lost on serialization.
        
        // FIX: Re-attach listeners after injection
        const copyBtns = bubble.querySelectorAll('.code-copy-btn');
        copyBtns.forEach(btn => {
            btn.onclick = async () => {
                // Find sibling pre/code
                const pre = btn.parentElement.querySelector('pre');
                const code = pre.querySelector('code')?.innerText || pre.innerText;
                try {
                    await copyToClipboard(code);
                    btn.innerHTML = '<i class="ph-bold ph-check"></i> Copied!';
                    setTimeout(() => {
                        btn.innerHTML = '<i class="ph-bold ph-copy"></i> Copy';
                    }, 2000);
                } catch (err) {
                    console.error('Copy failed', err);
                    showToast('Failed to copy to clipboard', 'error');
                }
            };
        });
    }

    // Footer container for timestamp and usage
    const footer = document.createElement('div');
    footer.className = `flex items-center gap-3 mt-1 ${isUser ? 'flex-row-reverse mr-1' : 'ml-1'}`;

    // Timestamp
    const timestamp = document.createElement('span');
    timestamp.className = 'text-[10px] text-slate-400 font-medium';
    timestamp.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    footer.appendChild(timestamp);

    // Usage Stats
    if (!isUser && usage) {
        const stats = formatUsageStats(usage);
        if (stats) {
            const usageEl = document.createElement('span');
            usageEl.className = 'inline-flex items-center gap-1 px-2 py-0.5 bg-amber-50 border border-amber-200 rounded-full';
            usageEl.innerHTML = `
                <i class="ph-fill ph-coins text-amber-500 text-xs"></i>
                <span class="text-xs font-semibold text-amber-700" title="Total API cost for this session (all messages)">${stats.cost}</span>
            `;
            footer.appendChild(usageEl);
        }
    }

    contentWrapper.appendChild(bubble);
    contentWrapper.appendChild(footer);

    container.appendChild(avatar);
    container.appendChild(contentWrapper);

    let listContainer = chatMessages.querySelector('div.space-y-8');
    if (!listContainer) {
        listContainer = document.createElement('div');
        listContainer.className = "max-w-3xl mx-auto space-y-8";
        chatMessages.appendChild(listContainer);
    }
    listContainer.appendChild(container);

    scrollToBottom();
}

// Add Loading Indicator
function showLoading() {
    const id = 'loading-' + Date.now();
    const container = document.createElement('div');
    container.id = id;
    container.className = "flex items-start gap-4";

    container.innerHTML = `
        <div class="flex-shrink-0">
            <div class="w-8 h-8 rounded-lg bg-white border border-slate-200 shadow-sm flex items-center justify-center">
                <i class="ph-fill ph-robot text-blue-600"></i>
            </div>
        </div>
        <div class="bg-white rounded-xl rounded-tl-none p-4 shadow-sm ring-1 ring-slate-900/5">
            <div class="flex space-x-1.5 items-center h-5">
                <div class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"></div>
                <div class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
                <div class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
            </div>
        </div>
    `;

    let listContainer = chatMessages.querySelector('div.space-y-8');
    if (!listContainer) {
         listContainer = document.createElement('div');
         listContainer.className = "max-w-3xl mx-auto space-y-8";
         chatMessages.appendChild(listContainer);
    }
    listContainer.appendChild(container);
    scrollToBottom();
    return id;
}

function removeLoading(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

// ============================================
// Message Sending
// ============================================

async function sendMessage(message, showInUI = true) {
    if (isProcessing) {
        showToast('Already processing a message', 'warning');
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
                showToast('Operation timed out', 'error');
                addMessage('**Timeout:** The operation took too long. Please try again with a shorter video.', 'agent');
                isProcessing = false;
                return false;
            }

            if (response.status === 422) {
                const errorData = await response.json();
                removeLoading(loadingId);
                const errorMsg = errorData.detail || 'Invalid input';
                showToast(errorMsg, 'error');
                addMessage(`**Validation Error:** ${errorMsg}`, 'agent');
                isProcessing = false;
                return false;
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Server error: ${response.status}`);
            }

            const data = await response.json();
            removeLoading(loadingId);
            addMessage(data.response, 'agent', data.usage);

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
    showToast('Failed to send message', 'error');
    addMessage(`**Error:** ${lastError?.message || 'Unknown error'}. Please try again.`, 'agent');
    isProcessing = false;
    return false;
}

// ============================================
// Session Initialization
// ============================================

async function loadExistingSession() {
    // Try to load existing messages from history storage
    try {
        const response = await fetch(`/history/${sessionId}`);
        if (!response.ok) return null;
        const data = await response.json();
        return data.messages || [];
    } catch (e) {
        console.warn('No existing session history:', e);
        return null;
    }
}

async function initSession() {
    // Clear any hardcoded placeholder if we want dynamic.
    const listContainer = chatMessages.querySelector('div.space-y-8');
    if (listContainer) {
        listContainer.innerHTML = ''; // Clear hardcoded placeholder
    }

    // First, check if this session has existing messages in storage
    const existingMessages = await loadExistingSession();

    if (existingMessages && existingMessages.length > 0) {
        // Display existing messages from history
        for (const msg of existingMessages) {
            addMessage(msg.content, msg.role);
        }
        // Add a visual indicator that this is a restored session
        const divider = document.createElement('div');
        divider.className = 'text-center text-xs text-slate-400 py-4 border-t border-slate-200';
        divider.innerHTML = '<span class="bg-slate-50 px-3 relative -top-2">Session restored from history</span>';
        const container = chatMessages.querySelector('div.space-y-8');
        if (container) {
            container.appendChild(divider);
        }
        return; // Session loaded from history
    }

    // No existing history - initialize new session
    const loadingId = showLoading();

    try {
        const response = await fetch('/chat/init', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId })
        });

        if (!response.ok) throw new Error('Failed to init session');

        const data = await response.json();
        removeLoading(loadingId);
        addMessage(data.response, 'agent', data.usage);

    } catch (e) {
        console.error("Init failed", e);
        removeLoading(loadingId);
        // Fallback or silent fail
        addMessage("Welcome! How can I help you with video transcription today?", 'agent');
    }
}

// ============================================
// Form Handlers
// ============================================

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