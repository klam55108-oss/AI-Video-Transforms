// ============================================
// VIDEOAGENT - Enhanced Frontend Script
// Dual Theme System + Improved UX
// ============================================

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

// Sidebar elements
const attachBtn = document.getElementById('attach-btn');
const historyToggle = document.getElementById('history-toggle');
const historyList = document.getElementById('history-list');
const historyCaret = document.getElementById('history-caret');
const transcriptsToggle = document.getElementById('transcripts-toggle');
const transcriptsList = document.getElementById('transcripts-list');
const transcriptsCaret = document.getElementById('transcripts-caret');

// Theme toggle
const themeToggle = document.getElementById('theme-toggle');

// Mobile navigation
const mobileMenuBtn = document.getElementById('mobile-menu-btn');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebar-overlay');
const sidebarClose = document.getElementById('sidebar-close');

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
const THEME_STORAGE_KEY = 'videoagent-theme';

// DOMPurify configuration for safe markdown rendering
const PURIFY_CONFIG = {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li',
                   'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'a', 'table',
                   'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'span', 'div'],
    ALLOWED_ATTR: ['href', 'class', 'target', 'rel'],
    ALLOW_DATA_ATTR: false
};

// ============================================
// Theme Management
// ============================================

function getTheme() {
    return localStorage.getItem(THEME_STORAGE_KEY) || 'dark';
}

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_STORAGE_KEY, theme);
}

function toggleTheme() {
    const currentTheme = getTheme();
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);

    // Optional: Show toast notification
    const themeName = newTheme === 'dark' ? 'Dark' : 'Light';
    showToast(`Switched to ${themeName} theme`, 'info');
}

function initTheme() {
    // Theme is already set in inline script, but ensure toggle works
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
}

// ============================================
// Mobile Navigation
// ============================================

function openSidebar() {
    sidebar?.classList.add('open');
    sidebarOverlay?.classList.add('open');
    document.body.style.overflow = 'hidden';
}

function closeSidebar() {
    sidebar?.classList.remove('open');
    sidebarOverlay?.classList.remove('open');
    document.body.style.overflow = '';
}

function initMobileNav() {
    mobileMenuBtn?.addEventListener('click', openSidebar);
    sidebarClose?.addEventListener('click', closeSidebar);
    sidebarOverlay?.addEventListener('click', closeSidebar);

    // Close sidebar on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebar?.classList.contains('open')) {
            closeSidebar();
        }
    });
}

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
        // Fallback for non-secure context
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
            <span class="text-sm font-medium">${escapeHtml(message)}</span>
        </div>
        <button class="ml-4 opacity-60 hover:opacity-100 transition-opacity">
            <i class="ph-bold ph-x"></i>
        </button>
    `;

    // Close button handler
    toast.querySelector('button').onclick = () => {
        toast.style.animation = 'toastFadeOut 0.2s forwards';
        setTimeout(() => toast.remove(), 200);
    };

    toastContainer.appendChild(toast);

    // Auto dismiss after 4 seconds
    setTimeout(() => {
        if (toast.isConnected) {
            toast.style.animation = 'toastFadeOut 0.2s forwards';
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
    if (!sessionId) return;

    try {
        const response = await fetch(`/status/${sessionId}`);

        // Handle session expired
        if (response.status === 410) {
            renderStatus('expired');
            sessionStorage.removeItem('agent_session_id');
            return;
        }

        if (!response.ok) return;

        const data = await response.json();
        renderStatus(data.status);
    } catch (e) {
        renderStatus('error');
    }
}

function renderStatus(status) {
    const indicator = document.getElementById('status-indicator');
    const label = document.getElementById('status-label');

    if (!indicator || !label) return;

    const states = {
        initializing: { class: 'initializing', text: 'Initializing...' },
        ready: { class: 'ready', text: 'Agent Ready' },
        processing: { class: 'processing', text: 'Processing...' },
        error: { class: 'error', text: 'Error' },
        expired: { class: 'expired', text: 'Session Expired' }
    };

    const state = states[status] || states.error;

    // Update classes
    indicator.className = `status-dot ${state.class}`;
    label.textContent = state.text;

    // Pause animation when ready (less distracting)
    if (status === 'ready') {
        indicator.style.setProperty('--pulse-animation', 'none');
    } else {
        indicator.style.removeProperty('--pulse-animation');
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
            historyList.innerHTML = '<p class="text-xs text-[var(--sidebar-text-muted)] px-2 py-1">Failed to load</p>';
        }
    }
}

function renderHistoryList(sessions) {
    if (!historyList) return;

    if (sessions.length === 0) {
        historyList.innerHTML = '<p class="text-xs text-[var(--sidebar-text-muted)] px-2 py-1">No history yet</p>';
        return;
    }

    historyList.innerHTML = sessions.map(s => `
        <button
            onclick="loadSession('${escapeHtml(s.session_id)}')"
            class="w-full text-left px-2 py-1.5 text-xs rounded-md transition-all
                   text-[var(--sidebar-text-secondary)] hover:bg-[var(--sidebar-hover)] hover:text-[var(--sidebar-text-primary)]"
            title="${escapeHtml(s.title || 'Untitled')}"
        >
            <div class="truncate font-medium">${escapeHtml(s.title || 'Untitled')}</div>
            <div class="text-[var(--sidebar-text-muted)] text-[10px]">${formatRelativeTime(s.updated_at)} · ${s.message_count} msgs</div>
        </button>
    `).join('');
}

function toggleHistoryPanel() {
    if (!historyList || !historyCaret) return;

    const isOpen = historyList.classList.contains('open');

    if (isOpen) {
        historyList.classList.remove('open');
        historyCaret.classList.remove('open');
    } else {
        historyList.classList.add('open');
        historyCaret.classList.add('open');
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
        loadHistory();
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
            transcriptsList.innerHTML = '<p class="text-xs text-[var(--sidebar-text-muted)] px-2 py-1">Failed to load</p>';
        }
    }
}

function renderTranscriptsList(transcripts) {
    if (!transcriptsList) return;

    if (transcripts.length === 0) {
        transcriptsList.innerHTML = '<p class="text-xs text-[var(--sidebar-text-muted)] px-2 py-1">No transcripts yet</p>';
        return;
    }

    transcriptsList.innerHTML = transcripts.map(t => `
        <div class="flex items-center justify-between px-2 py-1.5 text-xs rounded-md group
                    text-[var(--sidebar-text-secondary)] hover:bg-[var(--sidebar-hover)]">
            <div class="truncate flex-1 mr-2" title="${escapeHtml(t.filename)}">
                <div class="font-medium truncate">${escapeHtml(t.filename)}</div>
                <div class="text-[var(--sidebar-text-muted)] text-[10px]">${formatFileSize(t.file_size)} · ${formatRelativeTime(t.created_at)}</div>
            </div>
            <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button onclick="downloadTranscript('${t.id}')" title="Download"
                        class="p-1 hover:text-[var(--sidebar-text-primary)] transition-colors">
                    <i class="ph-bold ph-download-simple text-sm"></i>
                </button>
                <button onclick="deleteTranscript('${t.id}')" title="Delete"
                        class="p-1 hover:text-[var(--status-error)] transition-colors">
                    <i class="ph-bold ph-trash text-sm"></i>
                </button>
            </div>
        </div>
    `).join('');
}

function toggleTranscriptsPanel() {
    if (!transcriptsList || !transcriptsCaret) return;

    const isOpen = transcriptsList.classList.contains('open');

    if (isOpen) {
        transcriptsList.classList.remove('open');
        transcriptsCaret.classList.remove('open');
    } else {
        transcriptsList.classList.add('open');
        transcriptsCaret.classList.add('open');
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
        loadTranscripts();
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
            addMessage(`File uploaded successfully. Starting transcription...`, 'agent');

            // Trigger transcription request using session-specific upload directory
            const message = `Please transcribe this uploaded video file: uploads/${sessionId}/${data.file_id}_${file.name}`;
            await sendMessage(message, false);
        } else {
            showToast(data.error || 'Upload failed', 'error');
            addMessage(`**Upload Error:** ${data.error || 'Unknown error'}`, 'agent');
        }
    } catch (e) {
        removeLoading(loadingId);
        showToast('Upload failed', 'error');
        addMessage(`**Upload Error:** ${e.message}`, 'agent');
    }

    // Reset file input
    fileInput.value = '';
}

// ============================================
// UI Helpers
// ============================================

// Auto-resize textarea
userInput?.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
    if(this.value === '') {
        this.style.height = '44px';
    }
});

// Handle Enter to submit (Shift+Enter for newline)
userInput?.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.requestSubmit();
    }
});

function scrollToBottom() {
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

        // Add copy button (will be re-attached after innerHTML)
        const btn = document.createElement('button');
        btn.className = 'code-copy-btn';
        btn.setAttribute('data-copy-btn', 'true');
        btn.innerHTML = '<i class="ph-bold ph-copy"></i> Copy';
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

    if (isUser) {
        avatar.className = "avatar avatar-user";
        avatar.innerHTML = `<span class="text-sm font-bold text-white">U</span>`;
    } else {
        avatar.className = "avatar avatar-agent";
        avatar.innerHTML = `<i class="ph-fill ph-robot text-lg" style="color: var(--accent-primary);"></i>`;
    }

    // Message Content Wrapper
    const contentWrapper = document.createElement('div');
    contentWrapper.className = "flex-1 min-w-0";

    // Bubble
    const bubble = document.createElement('div');

    if (isUser) {
        bubble.className = "message-user text-sm leading-relaxed";
        bubble.textContent = text;
    } else {
        bubble.className = "message-agent prose prose-sm max-w-none";

        // Sanitize and enhance markdown
        const safeHtml = DOMPurify.sanitize(marked.parse(text), PURIFY_CONFIG);
        bubble.innerHTML = enhanceMarkdown(safeHtml);

        // Re-attach copy button event listeners
        const copyBtns = bubble.querySelectorAll('[data-copy-btn]');
        copyBtns.forEach(btn => {
            btn.onclick = async () => {
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

    // Footer container
    const footer = document.createElement('div');
    footer.className = `flex items-center gap-3 mt-2 ${isUser ? 'flex-row-reverse mr-1' : 'ml-1'}`;

    // Timestamp
    const timestamp = document.createElement('span');
    timestamp.className = 'text-[10px] font-medium';
    timestamp.style.color = 'var(--text-muted)';
    timestamp.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    footer.appendChild(timestamp);

    // Usage Stats (for agent messages)
    if (!isUser && usage) {
        const stats = formatUsageStats(usage);
        if (stats) {
            const usageEl = document.createElement('span');
            usageEl.className = 'cost-badge';
            usageEl.innerHTML = `
                <i class="ph-fill ph-coins text-xs"></i>
                <span title="Total API cost for this session">${stats.cost}</span>
            `;
            footer.appendChild(usageEl);
        }
    }

    contentWrapper.appendChild(bubble);
    contentWrapper.appendChild(footer);

    container.appendChild(avatar);
    container.appendChild(contentWrapper);

    let listContainer = chatMessages.querySelector('div.space-y-6');
    if (!listContainer) {
        listContainer = document.createElement('div');
        listContainer.className = "max-w-3xl mx-auto space-y-6";
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
        <div class="avatar avatar-agent">
            <i class="ph-fill ph-robot text-lg" style="color: var(--accent-primary);"></i>
        </div>
        <div class="message-agent" style="padding: 16px 24px;">
            <div class="loading-dots">
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
            </div>
        </div>
    `;

    let listContainer = chatMessages.querySelector('div.space-y-6');
    if (!listContainer) {
         listContainer = document.createElement('div');
         listContainer.className = "max-w-3xl mx-auto space-y-6";
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

            // Handle session expired (410 Gone)
            if (response.status === 410) {
                removeLoading(loadingId);
                showToast('Session expired. Please start a new session.', 'warning');
                addMessage('**Session Expired**\n\nYour session has ended. This can happen after server restarts or prolonged inactivity.\n\nClick **"New Chat"** in the sidebar to start a fresh conversation.', 'agent');

                // Clear session state
                sessionStorage.removeItem('agent_session_id');
                isProcessing = false;

                // Disable input until new session
                const userInputEl = document.getElementById('user-input');
                if (userInputEl) {
                    userInputEl.disabled = true;
                    userInputEl.placeholder = 'Session expired - start a new chat';
                }

                return false;
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Server error: ${response.status}`);
            }

            const data = await response.json();
            removeLoading(loadingId);
            addMessage(data.response, 'agent', data.usage);

            // Refresh transcripts list if panel is open
            if (transcriptsList && transcriptsList.classList.contains('open')) {
                loadTranscripts();
            }

            isProcessing = false;
            return true;

        } catch (error) {
            lastError = error;

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
    // Re-enable input (in case it was disabled by session expiry)
    const userInputEl = document.getElementById('user-input');
    if (userInputEl) {
        userInputEl.disabled = false;
        userInputEl.placeholder = 'Type your message...';
    }

    // Clear any placeholder content
    const listContainer = chatMessages.querySelector('div.space-y-6');
    if (listContainer) {
        listContainer.innerHTML = '';
    }

    // Check for existing messages
    const existingMessages = await loadExistingSession();

    if (existingMessages && existingMessages.length > 0) {
        // Restore existing messages
        for (const msg of existingMessages) {
            addMessage(msg.content, msg.role);
        }

        // Add restoration indicator
        const divider = document.createElement('div');
        divider.className = 'text-center text-xs py-4 border-t';
        divider.style.borderColor = 'var(--divider)';
        divider.style.color = 'var(--text-muted)';
        divider.innerHTML = '<span class="px-3 relative -top-2" style="background: var(--content-bg);">Session restored from history</span>';
        const container = chatMessages.querySelector('div.space-y-6');
        if (container) {
            container.appendChild(divider);
        }
        return;
    }

    // Initialize new session
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
        addMessage("Welcome! How can I help you with video transcription today?", 'agent');
    }
}

// ============================================
// Form Handlers
// ============================================

chatForm?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const message = userInput.value.trim();
    if (!message) return;

    // Clear input immediately
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

resetBtn?.addEventListener('click', async () => {
    if (isProcessing) {
        if (!confirm('A message is being processed. Reset anyway?')) {
            return;
        }
        isProcessing = false;
    }

    if (confirm('Start a new transcription session? Current chat will be cleared.')) {
        stopStatusPolling();

        try {
            await fetch(`/chat/${sessionId}`, { method: 'DELETE' });
        } catch (e) {
            console.warn('Failed to close session on server:', e);
        }

        sessionStorage.removeItem('agent_session_id');
        window.location.reload();
    }
});

// ============================================
// Initialization
// ============================================

function initEventListeners() {
    // Sidebar panel toggles
    historyToggle?.addEventListener('click', toggleHistoryPanel);
    transcriptsToggle?.addEventListener('click', toggleTranscriptsPanel);
}

function initSidebarData() {
    // Pre-load sidebar data (collapsed state)
    loadHistory();
    loadTranscripts();
}

// Run initialization when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initMobileNav();
    initFileUpload();
    initEventListeners();
    initSidebarData();
    startStatusPolling();
});

// Initialize session
initSession();
