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

// KG Elements
const kgToggle = document.getElementById('kg-toggle');
const kgContent = document.getElementById('kg-content');
const kgCaret = document.getElementById('kg-caret');
const kgPendingBadge = document.getElementById('kg-pending-badge');
const kgDropdownToggle = document.getElementById('kg-dropdown-toggle');
const kgDropdownList = document.getElementById('kg-dropdown-list');
const kgDropdownLabel = document.getElementById('kg-dropdown-label');
const kgNewProjectBtn = document.getElementById('kg-new-project-btn');
const kgStateBadge = document.getElementById('kg-state-badge');
const kgStateLabel = document.getElementById('kg-state-label');
const kgWorkflow = document.getElementById('kg-workflow');
const kgActionBtn = document.getElementById('kg-action-btn');
const kgProgress = document.getElementById('kg-progress');
const kgProgressText = document.getElementById('kg-progress-text');
const kgConfirmations = document.getElementById('kg-confirmations');
const kgConfirmationsList = document.getElementById('kg-confirmations-list');
const kgStats = document.getElementById('kg-stats');
const kgExport = document.getElementById('kg-export');
const kgEmptyState = document.getElementById('kg-empty-state');

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

// KG State
const KG_PROJECT_STORAGE_KEY = 'kg_current_project';
const KG_VIEW_STORAGE_KEY = 'kg_current_view';
// Poll interval from server config (fallback to default)
const KG_POLL_INTERVAL_MS = window.APP_CONFIG?.KG_POLL_INTERVAL_MS || 5000;
let kgCurrentProjectId = sessionStorage.getItem(KG_PROJECT_STORAGE_KEY) || null;
let kgCurrentProject = null;
let kgPollInterval = null;
let kgDropdownFocusedIndex = -1;

// KG Graph View State
let kgCurrentView = localStorage.getItem(KG_VIEW_STORAGE_KEY) || 'list';
let cytoscapeInstance = null;
let selectedNodeData = null;
let graphResizeObserver = null;

// ============================================
// Configuration
// ============================================

const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 1000;
// Status poll interval from server config (fallback to default)
const STATUS_POLL_INTERVAL_MS = window.APP_CONFIG?.STATUS_POLL_INTERVAL_MS || 3000;
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

function showToast(message, type = 'info', options = {}) {
    const { hint = null, code = null, detail = null } = options;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const iconMap = {
        'info': 'ph-info',
        'success': 'ph-check-circle',
        'error': 'ph-warning-circle',
        'warning': 'ph-warning'
    };

    const iconClass = iconMap[type] || 'ph-info';

    // Build toast content
    let toastContent = `
        <div class="flex items-start gap-3 flex-1">
            <i class="ph-fill ${iconClass} text-lg opacity-80 mt-0.5"></i>
            <div class="flex-1 min-w-0">
                <div class="text-sm font-medium">${escapeHtml(message)}</div>
    `;

    // Add hint if available
    if (hint) {
        toastContent += `
                <div class="text-xs mt-1 opacity-75">
                    <i class="ph-bold ph-lightbulb text-xs mr-1"></i>${escapeHtml(hint)}
                </div>
        `;
    }

    toastContent += `
            </div>
        </div>
    `;

    // Add action buttons container
    toastContent += `<div class="flex items-center gap-2 ml-2">`;

    // Add "Copy Debug Info" button for errors with code
    if (type === 'error' && (code || detail)) {
        toastContent += `
            <button class="copy-debug-btn opacity-60 hover:opacity-100 transition-opacity text-xs px-2 py-1 rounded hover:bg-black/10" title="Copy debug info">
                <i class="ph-bold ph-copy text-sm"></i>
            </button>
        `;
    }

    // Close button
    toastContent += `
            <button class="close-btn opacity-60 hover:opacity-100 transition-opacity">
                <i class="ph-bold ph-x"></i>
            </button>
        </div>
    `;

    toast.innerHTML = toastContent;

    // Close button handler
    const closeBtn = toast.querySelector('.close-btn');
    if (closeBtn) {
        closeBtn.onclick = () => {
            toast.style.animation = 'toastFadeOut 0.2s forwards';
            setTimeout(() => toast.remove(), 200);
        };
    }

    // Copy debug info handler
    const copyBtn = toast.querySelector('.copy-debug-btn');
    if (copyBtn) {
        copyBtn.onclick = async () => {
            const debugInfo = {
                message,
                code,
                detail,
                timestamp: new Date().toISOString()
            };
            const debugText = JSON.stringify(debugInfo, null, 2);

            try {
                await copyToClipboard(debugText);
                copyBtn.innerHTML = '<i class="ph-bold ph-check text-sm"></i>';
                setTimeout(() => {
                    copyBtn.innerHTML = '<i class="ph-bold ph-copy text-sm"></i>';
                }, 1500);
            } catch (err) {
                console.error('Failed to copy debug info:', err);
            }
        };
    }

    toastContainer.appendChild(toast);

    // Auto dismiss after 4 seconds (6 seconds for errors with hints)
    const dismissDelay = (type === 'error' && hint) ? 6000 : 4000;
    setTimeout(() => {
        if (toast.isConnected) {
            toast.style.animation = 'toastFadeOut 0.2s forwards';
            setTimeout(() => toast.remove(), 200);
        }
    }, dismissDelay);
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
// Knowledge Graph API Client
// ============================================

/**
 * Handle KG API errors consistently with unified error schema.
 * Distinguishes network errors from server errors for better user feedback.
 * Parses APIError schema with code, message, detail, hint, and retryable fields.
 */
async function handleKGApiError(response, defaultMessage) {
    // Network error or server unavailable
    if (!response) {
        throw new Error('Network error. Please check your connection and try again.');
    }

    // Try to parse structured error details from response
    let errorMessage = defaultMessage;
    let errorHint = null;
    let errorCode = null;
    let isRetryable = false;

    try {
        const errorData = await response.json();

        // New unified error schema format
        if (errorData.error) {
            const error = errorData.error;
            errorCode = error.code;
            errorMessage = error.message || defaultMessage;
            errorHint = error.hint;
            isRetryable = error.retryable || false;

            // Append detail to message if available (for debugging)
            if (error.detail && error.detail !== errorMessage) {
                errorMessage = `${errorMessage}: ${error.detail}`;
            }
        }
        // Legacy format fallback (for backward compatibility)
        else if (errorData.detail) {
            errorMessage = errorData.detail;
        }
    } catch {
        // Response wasn't JSON, use default message
    }

    // Add status code context for debugging if we don't have structured error
    if (!errorCode) {
        if (response.status === 503) {
            errorMessage = 'Server is busy. Please try again in a moment.';
            isRetryable = true;
        } else if (response.status === 500) {
            errorMessage = 'Server error. Please try again later.';
            isRetryable = true;
        }
    }

    // Create error with hint attached for display
    const error = new Error(errorMessage);
    error.hint = errorHint;
    error.code = errorCode;
    error.retryable = isRetryable;
    throw error;
}

const kgClient = {
    async listProjects() {
        try {
            const response = await fetch('/kg/projects');
            if (!response.ok) {
                await handleKGApiError(response, 'Failed to load projects');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Please check your connection.');
            }
            throw e;
        }
    },

    async createProject(name) {
        try {
            const response = await fetch('/kg/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });
            if (!response.ok) {
                await handleKGApiError(response, 'Failed to create project');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Could not create project.');
            }
            throw e;
        }
    },

    async getProject(projectId) {
        try {
            const response = await fetch(`/kg/projects/${projectId}`);
            if (response.status === 404) return null;
            if (!response.ok) {
                await handleKGApiError(response, 'Failed to load project');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Could not load project.');
            }
            throw e;
        }
    },

    async getConfirmations(projectId) {
        try {
            const response = await fetch(`/kg/projects/${projectId}/confirmations`);
            if (!response.ok) {
                await handleKGApiError(response, 'Failed to load confirmations');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Could not load confirmations.');
            }
            throw e;
        }
    },

    async confirmDiscovery(projectId, discoveryId, confirmed) {
        try {
            const response = await fetch(`/kg/projects/${projectId}/confirm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ discovery_id: discoveryId, confirmed })
            });
            if (!response.ok) {
                await handleKGApiError(response, 'Confirmation failed');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Could not confirm discovery.');
            }
            throw e;
        }
    },

    async getGraphStats(projectId) {
        try {
            const response = await fetch(`/kg/projects/${projectId}/graph`);
            if (response.status === 404) return null;
            if (!response.ok) {
                await handleKGApiError(response, 'Failed to load graph statistics');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Could not load statistics.');
            }
            throw e;
        }
    },

    async exportGraph(projectId, format) {
        try {
            const response = await fetch(`/kg/projects/${projectId}/export`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ format })
            });
            if (!response.ok) {
                await handleKGApiError(response, 'Export failed');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Could not export graph.');
            }
            throw e;
        }
    },

    async deleteProject(projectId) {
        try {
            const response = await fetch(`/kg/projects/${projectId}`, {
                method: 'DELETE'
            });
            if (!response.ok) {
                await handleKGApiError(response, 'Failed to delete project');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Could not delete project.');
            }
            throw e;
        }
    }
};

// ============================================
// KG Panel Toggle & Project Management
// ============================================

function toggleKGPanel() {
    if (!kgContent || !kgCaret) return;

    const isOpen = kgContent.classList.contains('open');

    if (isOpen) {
        kgContent.classList.remove('open');
        kgCaret.classList.remove('open');
        stopKGPolling();
    } else {
        kgContent.classList.add('open');
        kgCaret.classList.add('open');
        loadKGProjects();
        if (kgCurrentProjectId) startKGPolling();
    }

    kgToggle?.setAttribute('aria-expanded', !isOpen);
}

async function loadKGProjects() {
    try {
        const data = await kgClient.listProjects();
        renderKGProjectList(data.projects || []);
    } catch (e) {
        console.error('Failed to load KG projects:', e);
        kgEmptyState?.classList.remove('hidden');
        showToast(e.message, 'error', {
            hint: e.hint,
            code: e.code,
            detail: e.detail
        });
    }
}

async function deleteKGProject(projectId, projectName) {
    if (!confirm(`Delete project "${projectName}"? All data will be permanently removed.`)) {
        return;
    }

    try {
        await kgClient.deleteProject(projectId);

        // If we deleted the currently selected project, clear selection
        if (kgCurrentProjectId === projectId) {
            kgCurrentProjectId = null;
            kgCurrentProject = null;
            sessionStorage.removeItem(KG_PROJECT_STORAGE_KEY);
            kgDropdownLabel.textContent = '-- Select Project --';
            kgWorkflow?.classList.add('hidden');
            stopKGPolling();
        }

        // Refresh the project list
        loadKGProjects();
        showToast('Project deleted', 'success');
    } catch (e) {
        console.error('Delete project failed:', e);
        showToast(e.message, 'error', {
            hint: e.hint,
            code: e.code,
            detail: e.detail
        });
    }
}

function renderKGProjectList(projects) {
    if (!kgDropdownList || !kgDropdownLabel) return;

    // Clear existing options
    kgDropdownList.innerHTML = '';

    if (projects.length === 0) {
        kgEmptyState?.classList.remove('hidden');
        kgWorkflow?.classList.add('hidden');

        // Add empty placeholder option
        const emptyOption = document.createElement('li');
        emptyOption.className = 'kg-dropdown-option';
        emptyOption.setAttribute('data-empty', 'true');
        emptyOption.textContent = 'No projects yet';
        kgDropdownList.appendChild(emptyOption);

        kgDropdownLabel.textContent = '-- Select Project --';
        return;
    }

    kgEmptyState?.classList.add('hidden');

    // Add project options directly (no placeholder needed - toggle button shows current selection)
    // Add project options (styled like History items)
    projects.forEach((p, index) => {
        const option = document.createElement('li');
        option.className = 'kg-dropdown-option group';
        option.setAttribute('role', 'option');
        option.setAttribute('data-value', p.project_id);
        option.setAttribute('aria-selected', p.project_id === kgCurrentProjectId ? 'true' : 'false');
        option.innerHTML = `
            <div class="option-content" onclick="handleDropdownSelect('${p.project_id}', '${escapeHtml(p.name).replace(/'/g, "\\'")}')">
                <span class="option-name truncate">${escapeHtml(p.name)}</span>
                <span class="option-state">${p.state}</span>
            </div>
            <button class="kg-delete-btn opacity-0 group-hover:opacity-100 transition-opacity"
                    onclick="event.stopPropagation(); deleteKGProject('${p.project_id}', '${escapeHtml(p.name).replace(/'/g, "\\'")}')"
                    title="Delete project">
                <i class="ph-bold ph-trash text-xs"></i>
            </button>
        `;
        kgDropdownList.appendChild(option);
    });

    // Update label if current project is selected
    if (kgCurrentProjectId) {
        const currentProject = projects.find(p => p.project_id === kgCurrentProjectId);
        if (currentProject) {
            kgDropdownLabel.textContent = currentProject.name;
        }
        refreshKGProjectStatus();
    }
}

function handleDropdownSelect(projectId, projectName) {
    kgDropdownLabel.textContent = projectName || '-- Select Project --';
    closeKGDropdown();
    selectKGProject(projectId);

    // Update aria-selected on all options
    const options = kgDropdownList?.querySelectorAll('.kg-dropdown-option[role="option"]');
    options?.forEach(opt => {
        opt.setAttribute('aria-selected', opt.getAttribute('data-value') === projectId ? 'true' : 'false');
    });
}

function toggleKGDropdown() {
    const isOpen = kgDropdownToggle?.getAttribute('aria-expanded') === 'true';
    if (isOpen) {
        closeKGDropdown();
    } else {
        openKGDropdown();
    }
}

function openKGDropdown() {
    kgDropdownToggle?.setAttribute('aria-expanded', 'true');
    kgDropdownList?.classList.remove('hidden');
    kgDropdownList?.classList.add('open');
    kgDropdownFocusedIndex = -1;

    // Focus on currently selected option
    const selectedOption = kgDropdownList?.querySelector('[aria-selected="true"]');
    if (selectedOption) {
        const options = Array.from(kgDropdownList?.querySelectorAll('.kg-dropdown-option[role="option"]') || []);
        kgDropdownFocusedIndex = options.indexOf(selectedOption);
        updateDropdownFocus();
    }
}

function closeKGDropdown() {
    kgDropdownToggle?.setAttribute('aria-expanded', 'false');
    kgDropdownList?.classList.remove('open');
    kgDropdownList?.classList.add('hidden');
    kgDropdownFocusedIndex = -1;
    clearDropdownFocus();
}

function updateDropdownFocus() {
    const options = kgDropdownList?.querySelectorAll('.kg-dropdown-option[role="option"]');
    options?.forEach((opt, i) => {
        if (i === kgDropdownFocusedIndex) {
            opt.classList.add('focused');
            opt.scrollIntoView({ block: 'nearest' });
        } else {
            opt.classList.remove('focused');
        }
    });
}

function clearDropdownFocus() {
    const options = kgDropdownList?.querySelectorAll('.kg-dropdown-option');
    options?.forEach(opt => opt.classList.remove('focused'));
}

function handleDropdownKeydown(e) {
    const options = Array.from(kgDropdownList?.querySelectorAll('.kg-dropdown-option[role="option"]') || []);
    const isOpen = kgDropdownToggle?.getAttribute('aria-expanded') === 'true';

    switch (e.key) {
        case 'Enter':
        case ' ':
            e.preventDefault();
            if (!isOpen) {
                openKGDropdown();
            } else if (kgDropdownFocusedIndex >= 0 && options[kgDropdownFocusedIndex]) {
                const option = options[kgDropdownFocusedIndex];
                const value = option.getAttribute('data-value');
                const name = option.querySelector('span')?.textContent || option.textContent;
                handleDropdownSelect(value, name);
            }
            break;

        case 'Escape':
            e.preventDefault();
            closeKGDropdown();
            kgDropdownToggle?.focus();
            break;

        case 'ArrowDown':
            e.preventDefault();
            if (!isOpen) {
                openKGDropdown();
            } else {
                kgDropdownFocusedIndex = Math.min(kgDropdownFocusedIndex + 1, options.length - 1);
                updateDropdownFocus();
            }
            break;

        case 'ArrowUp':
            e.preventDefault();
            if (isOpen) {
                kgDropdownFocusedIndex = Math.max(kgDropdownFocusedIndex - 1, 0);
                updateDropdownFocus();
            }
            break;

        case 'Home':
            e.preventDefault();
            if (isOpen) {
                kgDropdownFocusedIndex = 0;
                updateDropdownFocus();
            }
            break;

        case 'End':
            e.preventDefault();
            if (isOpen) {
                kgDropdownFocusedIndex = options.length - 1;
                updateDropdownFocus();
            }
            break;

        case 'Tab':
            if (isOpen) {
                closeKGDropdown();
            }
            break;
    }
}

async function selectKGProject(projectId) {
    if (!projectId) {
        kgCurrentProjectId = null;
        kgCurrentProject = null;
        sessionStorage.removeItem(KG_PROJECT_STORAGE_KEY);
        kgWorkflow?.classList.add('hidden');
        kgStateBadge?.classList.add('hidden');
        kgConfirmations?.classList.add('hidden');
        kgStats?.classList.add('hidden');
        kgExport?.classList.add('hidden');
        stopKGPolling();
        return;
    }

    kgCurrentProjectId = projectId;
    sessionStorage.setItem(KG_PROJECT_STORAGE_KEY, projectId);
    await refreshKGProjectStatus();
    startKGPolling();
}

async function refreshKGProjectStatus() {
    if (!kgCurrentProjectId) return;

    try {
        const project = await kgClient.getProject(kgCurrentProjectId);
        if (!project) {
            showToast('Project not found', 'error');
            selectKGProject(null);
            return;
        }

        kgCurrentProject = project;
        updateKGUI(project);
    } catch (e) {
        console.error('Failed to refresh KG project:', e);
    }
}

// ============================================
// KG UI Updates
// ============================================

function updateKGUI(project) {
    kgWorkflow?.classList.remove('hidden');

    updateKGStateBadge(project.state);
    updateKGActionButton(project);
    updateKGConfirmations(project.pending_confirmations);
    updateKGStats(project);

    const hasData = project.thing_count > 0 || project.connection_count > 0;
    kgExport?.classList.toggle('hidden', !hasData);

    // Show view toggle if we have data
    const viewToggle = document.getElementById('kg-view-toggle');
    viewToggle?.classList.toggle('hidden', !hasData);

    // Show stats if we have data
    kgStats?.classList.toggle('hidden', !hasData);

    if (kgPendingBadge) {
        if (project.pending_confirmations > 0) {
            kgPendingBadge.textContent = project.pending_confirmations;
            kgPendingBadge.classList.remove('hidden');
        } else {
            kgPendingBadge.classList.add('hidden');
        }
    }
}

function updateKGStateBadge(state) {
    if (!kgStateBadge || !kgStateLabel) return;

    kgStateBadge.classList.remove('hidden');

    const indicator = kgStateBadge.querySelector('.kg-state-indicator');
    if (indicator) {
        indicator.className = `kg-state-indicator ${state}`;
    }

    const labels = {
        'created': 'Created',
        'bootstrapping': 'Bootstrapping...',
        'active': 'Active',
        'stable': 'Stable'
    };

    kgStateLabel.textContent = labels[state] || state;
}

function updateKGActionButton(project) {
    if (!kgActionBtn) return;

    const icon = kgActionBtn.querySelector('i');
    const text = kgActionBtn.querySelector('span');

    switch (project.state) {
        case 'created':
            icon.className = 'ph-bold ph-lightning mr-1.5';
            text.textContent = 'Bootstrap from Video';
            kgActionBtn.disabled = false;
            kgProgress?.classList.add('hidden');
            break;
        case 'bootstrapping':
            icon.className = 'ph-bold ph-spinner mr-1.5 animate-spin';
            text.textContent = 'Bootstrapping...';
            kgActionBtn.disabled = true;
            kgProgress?.classList.remove('hidden');
            if (kgProgressText) kgProgressText.textContent = 'Analyzing domain...';
            break;
        case 'active':
        case 'stable':
            icon.className = 'ph-bold ph-magnifying-glass-plus mr-1.5';
            text.textContent = 'Extract from Video';
            kgActionBtn.disabled = false;
            kgProgress?.classList.add('hidden');
            break;
    }
}

async function updateKGConfirmations(pendingCount) {
    if (!kgConfirmations || !kgConfirmationsList) return;

    if (pendingCount === 0) {
        kgConfirmations.classList.add('hidden');
        return;
    }

    kgConfirmations.classList.remove('hidden');

    try {
        const discoveries = await kgClient.getConfirmations(kgCurrentProjectId);
        renderKGConfirmations(discoveries);
    } catch (e) {
        console.error('Failed to load confirmations:', e);
    }
}

function renderKGConfirmations(discoveries) {
    if (!kgConfirmationsList) return;

    kgConfirmationsList.innerHTML = discoveries.map(d => `
        <div class="kg-discovery-item" data-discovery-id="${escapeHtml(d.id)}">
            <span class="discovery-question">${DOMPurify.sanitize(d.user_question)}</span>
            <div class="discovery-actions">
                <button class="discovery-btn accept" onclick="confirmKGDiscovery('${escapeHtml(d.id)}', true)">
                    <i class="ph-bold ph-check"></i> Yes
                </button>
                <button class="discovery-btn reject" onclick="confirmKGDiscovery('${escapeHtml(d.id)}', false)">
                    <i class="ph-bold ph-x"></i> No
                </button>
            </div>
        </div>
    `).join('');
}

function updateKGStats(project) {
    if (!kgStats) return;

    const hasData = project.thing_count > 0 || project.connection_count > 0;
    kgStats.classList.toggle('hidden', !hasData);

    if (hasData) {
        document.getElementById('kg-stat-nodes').textContent = project.thing_count;
        document.getElementById('kg-stat-edges').textContent = project.connection_count;
    }
}

// ============================================
// KG Actions
// ============================================

async function createKGProject() {
    const name = prompt('Enter project name:');
    if (!name || !name.trim()) return;

    try {
        const project = await kgClient.createProject(name.trim());
        showToast(`Project "${project.name}" created`, 'success');

        await loadKGProjects();
        // selectKGProject handles updating the custom dropdown display
        await selectKGProject(project.project_id);
    } catch (e) {
        showToast(e.message, 'error', {
            hint: e.hint,
            code: e.code,
            detail: e.detail
        });
    }
}

async function confirmKGDiscovery(discoveryId, confirmed) {
    if (!kgCurrentProjectId) return;

    const item = document.querySelector(`[data-discovery-id="${discoveryId}"]`);
    const buttons = item?.querySelectorAll('button');
    buttons?.forEach(btn => btn.disabled = true);

    try {
        await kgClient.confirmDiscovery(kgCurrentProjectId, discoveryId, confirmed);

        item?.classList.add('fade-out');
        setTimeout(() => {
            item?.remove();
            const remaining = kgConfirmationsList?.children.length || 0;
            if (kgPendingBadge) {
                if (remaining > 0) {
                    kgPendingBadge.textContent = remaining;
                } else {
                    kgPendingBadge.classList.add('hidden');
                    kgConfirmations?.classList.add('hidden');
                }
            }
        }, 200);

        showToast(confirmed ? 'Discovery confirmed' : 'Discovery rejected', 'success');
    } catch (e) {
        showToast(e.message, 'error', {
            hint: e.hint,
            code: e.code,
            detail: e.detail
        });
        buttons?.forEach(btn => btn.disabled = false);
    }
}

async function exportKGGraph(format) {
    if (!kgCurrentProjectId) return;

    try {
        const result = await kgClient.exportGraph(kgCurrentProjectId, format);
        showToast(`Graph exported as ${result.filename}`, 'success');
    } catch (e) {
        showToast(e.message, 'error', {
            hint: e.hint,
            code: e.code,
            detail: e.detail
        });
    }
}

// ============================================
// KG Polling
// ============================================

function startKGPolling() {
    stopKGPolling();
    kgPollInterval = setInterval(refreshKGProjectStatus, KG_POLL_INTERVAL_MS);
}

function stopKGPolling() {
    if (kgPollInterval) {
        clearInterval(kgPollInterval);
        kgPollInterval = null;
    }
}

// ============================================
// KG View Toggle (List/Graph)
// ============================================

function toggleKGView(view) {
    if (view === kgCurrentView) return;

    kgCurrentView = view;
    localStorage.setItem(KG_VIEW_STORAGE_KEY, view);

    const chatContainer = document.getElementById('chat-messages');
    const graphView = document.getElementById('kg-graph-view');
    const listViewToggle = document.getElementById('kg-view-list-btn');
    const graphViewToggle = document.getElementById('kg-view-graph-btn');
    const headerControls = document.getElementById('graph-header-controls');
    const headerTitle = document.getElementById('header-title');
    const headerIcon = document.getElementById('header-icon');

    if (view === 'graph') {
        // Hide chat, show graph
        chatContainer?.classList.add('hidden');
        graphView?.classList.remove('hidden');

        // Update button states
        listViewToggle?.classList.remove('active');
        graphViewToggle?.classList.add('active');

        // Show header controls
        headerControls?.classList.remove('hidden');
        headerControls?.classList.add('flex');

        // Update header title
        if (headerTitle) headerTitle.textContent = 'Knowledge Graph';
        if (headerIcon) {
            headerIcon.className = 'ph-regular ph-graph text-[var(--text-tertiary)]';
        }

        // Initialize graph if project selected
        if (kgCurrentProjectId) {
            initKGGraph(kgCurrentProjectId);
        }
    } else {
        // Show chat, hide graph
        chatContainer?.classList.remove('hidden');
        graphView?.classList.add('hidden');

        // Update button states
        listViewToggle?.classList.add('active');
        graphViewToggle?.classList.remove('active');

        // Hide header controls
        headerControls?.classList.add('hidden');
        headerControls?.classList.remove('flex');

        // Restore header title
        if (headerTitle) headerTitle.textContent = 'Transcription & Analysis';
        if (headerIcon) {
            headerIcon.className = 'ph-regular ph-hash text-[var(--text-tertiary)]';
        }

        // Close inspector when switching to list view
        closeInspector();
    }
}

// ============================================
// KG Graph Visualization
// ============================================

async function initKGGraph(projectId) {
    if (!window.cytoscape) {
        showToast('Cytoscape library not loaded', 'error');
        return;
    }

    try {
        const response = await fetch(`/kg/projects/${projectId}/graph-data`);
        if (!response.ok) {
            if (response.status === 404) {
                renderEmptyGraph();
                return;
            }
            throw new Error('Failed to load graph data');
        }

        const graphData = await response.json();
        renderGraph(graphData);
        updateGraphStats(graphData);
    } catch (e) {
        console.error('Failed to initialize graph:', e);
        showToast(e.message, 'error');
        renderEmptyGraph();
    }
}

function renderGraph(data) {
    const container = document.getElementById('kg-graph-container');
    if (!container) return;

    // Clear existing instance and observer
    if (graphResizeObserver) {
        graphResizeObserver.disconnect();
        graphResizeObserver = null;
    }
    if (cytoscapeInstance) {
        cytoscapeInstance.destroy();
        cytoscapeInstance = null;
    }

    // Calculate node degrees for size scaling
    const nodeDegrees = {};
    data.nodes.forEach(n => { nodeDegrees[n.data.id] = 0; });
    data.edges.forEach(e => {
        nodeDegrees[e.data.source] = (nodeDegrees[e.data.source] || 0) + 1;
        nodeDegrees[e.data.target] = (nodeDegrees[e.data.target] || 0) + 1;
    });

    // Find max degree for scaling
    const maxDegree = Math.max(...Object.values(nodeDegrees), 1);
    const minNodeSize = 30;
    const maxNodeSize = 70;

    // Add degree to node data
    data.nodes.forEach(n => {
        n.data.degree = nodeDegrees[n.data.id] || 0;
    });

    // Entity type colors (vibrant, accessible palette)
    const typeColors = {
        'Person': '#3b82f6',
        'Character': '#3b82f6',
        'Organization': '#10b981',
        'Group': '#10b981',
        'Event': '#f59e0b',
        'Location': '#ef4444',
        'Place': '#ef4444',
        'Concept': '#8b5cf6',
        'Theme': '#8b5cf6',
        'Technology': '#06b6d4',
        'Product': '#ec4899',
        'Object': '#ec4899',
        'default': '#64748b'
    };

    // Helper to get color for a type
    const getTypeColor = (type) => typeColors[type] || typeColors.default;

    // Helper to calculate node size based on degree
    const getNodeSize = (degree) => {
        const normalized = degree / maxDegree;
        return minNodeSize + (maxNodeSize - minNodeSize) * Math.sqrt(normalized);
    };

    // Helper to truncate label
    const truncateLabel = (label, maxLen = 12) => {
        if (!label) return '';
        return label.length > maxLen ? label.slice(0, maxLen - 1) + '…' : label;
    };

    // Initialize Cytoscape
    cytoscapeInstance = cytoscape({
        container: container,
        elements: [...data.nodes, ...data.edges],
        style: [
            // Base node style
            {
                selector: 'node',
                style: {
                    'background-color': (ele) => getTypeColor(ele.data('type')),
                    'background-opacity': 0.9,
                    'label': (ele) => truncateLabel(ele.data('label')),
                    'width': (ele) => getNodeSize(ele.data('degree')),
                    'height': (ele) => getNodeSize(ele.data('degree')),
                    'font-size': (ele) => Math.max(10, Math.min(14, 10 + ele.data('degree') * 0.3)),
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'color': '#ffffff',
                    'text-outline-width': 2,
                    'text-outline-color': (ele) => getTypeColor(ele.data('type')),
                    'text-outline-opacity': 1,
                    'overlay-padding': 6,
                    'border-width': 2,
                    'border-color': (ele) => getTypeColor(ele.data('type')),
                    'border-opacity': 0.3,
                    'transition-property': 'background-opacity, border-width, border-opacity, width, height',
                    'transition-duration': '0.2s',
                    'transition-timing-function': 'ease-out'
                }
            },
            // Node hover state
            {
                selector: 'node:active',
                style: {
                    'overlay-opacity': 0.1
                }
            },
            // Node selected state
            {
                selector: 'node:selected',
                style: {
                    'border-width': 4,
                    'border-color': '#ffffff',
                    'border-opacity': 1,
                    'background-opacity': 1
                }
            },
            // Highlighted node (neighbor of selected)
            {
                selector: 'node.highlighted',
                style: {
                    'border-width': 3,
                    'border-color': '#ffffff',
                    'border-opacity': 0.7,
                    'background-opacity': 1
                }
            },
            // Dimmed node (not connected to selected)
            {
                selector: 'node.dimmed',
                style: {
                    'background-opacity': 0.25,
                    'text-opacity': 0.4,
                    'border-opacity': 0.1
                }
            },
            // Base edge style
            {
                selector: 'edge',
                style: {
                    'width': 2,
                    'line-color': '#64748b',
                    'line-opacity': 0.4,
                    'target-arrow-color': '#64748b',
                    'target-arrow-shape': 'triangle',
                    'arrow-scale': 0.8,
                    'curve-style': 'bezier',
                    'control-point-step-size': 40,
                    'transition-property': 'line-opacity, width, line-color',
                    'transition-duration': '0.2s'
                }
            },
            // Edge hover - show label with proper colors (NO CSS VARIABLES - Cytoscape uses Canvas!)
            {
                selector: 'edge:active',
                style: {
                    'label': 'data(label)',
                    'font-size': 11,
                    'font-weight': 'bold',
                    'text-rotation': 'autorotate',
                    'text-margin-y': -10,
                    'color': '#ffffff',
                    'text-outline-color': '#1e293b',
                    'text-outline-width': 2,
                    'text-background-color': '#1e293b',
                    'text-background-opacity': 0.95,
                    'text-background-padding': 6,
                    'text-background-shape': 'roundrectangle',
                    'line-opacity': 1,
                    'width': 3,
                    'z-index': 999
                }
            },
            // Highlighted edge (connected to selected node) - FIXED: Use hex colors
            {
                selector: 'edge.highlighted',
                style: {
                    'line-color': '#f59e0b',
                    'target-arrow-color': '#f59e0b',
                    'line-opacity': 1,
                    'width': 3,
                    'label': 'data(label)',
                    'font-size': 11,
                    'font-weight': 'bold',
                    'text-rotation': 'autorotate',
                    'text-margin-y': -10,
                    'color': '#ffffff',
                    'text-outline-color': '#78350f',
                    'text-outline-width': 2,
                    'text-background-color': '#78350f',
                    'text-background-opacity': 0.95,
                    'text-background-padding': 6,
                    'text-background-shape': 'roundrectangle',
                    'z-index': 999
                }
            },
            // Dimmed edge
            {
                selector: 'edge.dimmed',
                style: {
                    'line-opacity': 0.1,
                    'label': ''
                }
            }
        ],
        layout: {
            name: 'cose',
            animate: true,
            animationDuration: 800,
            animationEasing: 'ease-out-cubic',
            nodeRepulsion: function(node) {
                // Higher repulsion for high-degree nodes
                return 10000 + (node.data('degree') || 0) * 500;
            },
            idealEdgeLength: 120,
            edgeElasticity: 80,
            nestingFactor: 1.2,
            gravity: 0.8,
            numIter: 1500,
            initialTemp: 250,
            coolingFactor: 0.95,
            minTemp: 1.0,
            fit: true,
            padding: 40
        },
        // Performance options
        minZoom: 0.2,
        maxZoom: 3,
        wheelSensitivity: 0.3
    });

    // Node hover effect - highlight neighbors
    cytoscapeInstance.on('mouseover', 'node', (evt) => {
        const node = evt.target;
        highlightNodeNeighborhood(node);
    });

    cytoscapeInstance.on('mouseout', 'node', () => {
        // Only clear hover highlight if no node is selected
        if (!selectedNodeData) {
            clearHighlights();
        }
    });

    // Node click handler
    cytoscapeInstance.on('tap', 'node', async (evt) => {
        const node = evt.target;
        selectedNodeData = node.data();
        highlightNodeNeighborhood(node, true); // Persistent highlight
        await selectNode(selectedNodeData);
    });

    // Edge hover - show relationship type
    cytoscapeInstance.on('mouseover', 'edge', (evt) => {
        evt.target.addClass('hovered');
    });

    cytoscapeInstance.on('mouseout', 'edge', (evt) => {
        evt.target.removeClass('hovered');
    });

    // Click on background to deselect
    cytoscapeInstance.on('tap', (evt) => {
        if (evt.target === cytoscapeInstance) {
            clearHighlights();
            closeInspector();
        }
    });

    // Set up ResizeObserver to handle container size changes
    // This ensures cytoscape redraws correctly when inspector panel opens/closes
    graphResizeObserver = new ResizeObserver(() => {
        if (cytoscapeInstance) {
            cytoscapeInstance.resize();
            // Optional: re-fit after resize for better UX (commented out to preserve user's zoom/pan)
            // cytoscapeInstance.fit(null, 30);
        }
    });
    graphResizeObserver.observe(container);

    // Build type legend
    buildTypeLegend(data.nodes);
}

// Highlight a node and its neighborhood
function highlightNodeNeighborhood(node, persistent = false) {
    if (!cytoscapeInstance) return;

    const neighborhood = node.neighborhood().add(node);
    const connectedEdges = node.connectedEdges();

    // Clear previous highlights
    cytoscapeInstance.elements().removeClass('highlighted dimmed');

    // Dim all elements
    cytoscapeInstance.elements().addClass('dimmed');

    // Highlight neighborhood
    neighborhood.removeClass('dimmed').addClass('highlighted');
    connectedEdges.removeClass('dimmed').addClass('highlighted');

    // The selected node itself shouldn't have .highlighted class, just .selected
    node.removeClass('highlighted');
}

// Clear all highlights
function clearHighlights() {
    if (!cytoscapeInstance) return;
    cytoscapeInstance.elements().removeClass('highlighted dimmed');
}

// Build the type legend based on actual types in the graph
function buildTypeLegend(nodes) {
    const legendContainer = document.getElementById('kg-type-legend');
    if (!legendContainer) return;

    // Count entities per type
    const typeCounts = {};
    nodes.forEach(n => {
        const type = n.data.type || 'Unknown';
        typeCounts[type] = (typeCounts[type] || 0) + 1;
    });

    // Sort by count descending
    const sortedTypes = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);

    // Type colors
    const typeColors = {
        'Person': '#3b82f6',
        'Character': '#3b82f6',
        'Organization': '#10b981',
        'Group': '#10b981',
        'Event': '#f59e0b',
        'Location': '#ef4444',
        'Place': '#ef4444',
        'Concept': '#8b5cf6',
        'Theme': '#8b5cf6',
        'Technology': '#06b6d4',
        'Product': '#ec4899',
        'Object': '#ec4899',
        'default': '#64748b'
    };

    // Build legend HTML
    let html = '<div class="legend-title">Entity Types</div><div class="legend-items">';
    sortedTypes.forEach(([type, count]) => {
        const color = typeColors[type] || typeColors.default;
        html += `
            <button class="legend-item" data-type="${escapeHtml(type)}" onclick="filterByType('${escapeHtml(type)}')">
                <span class="legend-dot" style="background-color: ${color}"></span>
                <span class="legend-label">${escapeHtml(type)}</span>
                <span class="legend-count">${count}</span>
            </button>
        `;
    });
    html += `
        <button class="legend-item legend-reset" onclick="clearTypeFilter()">
            <i class="ph-bold ph-arrow-counter-clockwise"></i>
            <span class="legend-label">Show All</span>
        </button>
    </div>`;

    legendContainer.innerHTML = html;
    legendContainer.classList.remove('hidden');
}

// Filter graph by entity type
function filterByType(type) {
    if (!cytoscapeInstance) return;

    // Update active state in legend
    document.querySelectorAll('.legend-item').forEach(item => {
        item.classList.toggle('active', item.dataset.type === type);
    });

    // Show only nodes of this type and their edges
    const matchingNodes = cytoscapeInstance.nodes().filter(n => n.data('type') === type);
    const connectedEdges = matchingNodes.connectedEdges();
    const connectedNodes = connectedEdges.connectedNodes();

    cytoscapeInstance.elements().addClass('dimmed');
    matchingNodes.removeClass('dimmed').addClass('filtered');
    connectedEdges.removeClass('dimmed');
    connectedNodes.removeClass('dimmed');
}

// Clear type filter
function clearTypeFilter() {
    if (!cytoscapeInstance) return;

    document.querySelectorAll('.legend-item').forEach(item => {
        item.classList.remove('active');
    });

    cytoscapeInstance.elements().removeClass('dimmed filtered');
}

// ============================================
// Graph Search Functionality
// ============================================

let graphSearchData = []; // Cache of all nodes for searching
let searchSelectedIndex = -1;

function initGraphSearch() {
    const searchInput = document.getElementById('kg-graph-search');
    const clearBtn = document.getElementById('kg-search-clear');
    const resultsContainer = document.getElementById('kg-search-results');

    if (!searchInput) return;

    // Debounced search
    let searchTimeout;
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();

        // Show/hide clear button
        clearBtn?.classList.toggle('hidden', !query);

        // Reset selection
        searchSelectedIndex = -1;

        // Debounce search
        clearTimeout(searchTimeout);
        if (query.length >= 1) {
            searchTimeout = setTimeout(() => performGraphSearch(query), 150);
        } else {
            hideSearchResults();
            clearHighlights();
        }
    });

    // Keyboard navigation
    searchInput.addEventListener('keydown', (e) => {
        const results = resultsContainer?.querySelectorAll('.search-result-item') || [];

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            searchSelectedIndex = Math.min(searchSelectedIndex + 1, results.length - 1);
            updateSearchSelection(results);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            searchSelectedIndex = Math.max(searchSelectedIndex - 1, 0);
            updateSearchSelection(results);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (searchSelectedIndex >= 0 && results[searchSelectedIndex]) {
                const nodeId = results[searchSelectedIndex].dataset.nodeId;
                navigateToNode(nodeId);
            } else if (results.length > 0) {
                const nodeId = results[0].dataset.nodeId;
                navigateToNode(nodeId);
            }
        } else if (e.key === 'Escape') {
            hideSearchResults();
            searchInput.blur();
        }
    });

    // Clear button
    clearBtn?.addEventListener('click', () => {
        searchInput.value = '';
        clearBtn.classList.add('hidden');
        hideSearchResults();
        clearHighlights();
        searchInput.focus();
    });

    // Click outside to close
    document.addEventListener('click', (e) => {
        const container = document.getElementById('kg-search-container');
        if (container && !container.contains(e.target)) {
            hideSearchResults();
        }
    });
}

function performGraphSearch(query) {
    if (!cytoscapeInstance) return;

    const resultsContainer = document.getElementById('kg-search-results');
    if (!resultsContainer) return;

    const lowerQuery = query.toLowerCase();

    // Search through nodes
    const matches = [];
    cytoscapeInstance.nodes().forEach(node => {
        const data = node.data();
        const label = (data.label || '').toLowerCase();
        const aliases = (data.aliases || []).map(a => a.toLowerCase());
        const type = (data.type || '').toLowerCase();

        // Check label, aliases, and type
        if (label.includes(lowerQuery) ||
            aliases.some(a => a.includes(lowerQuery)) ||
            type.includes(lowerQuery)) {
            matches.push({
                id: data.id,
                label: data.label,
                type: data.type,
                degree: data.degree || 0,
                matchScore: label.startsWith(lowerQuery) ? 2 : 1
            });
        }
    });

    // Sort by match score (prefix matches first), then by degree
    matches.sort((a, b) => {
        if (b.matchScore !== a.matchScore) return b.matchScore - a.matchScore;
        return b.degree - a.degree;
    });

    // Limit results
    const topMatches = matches.slice(0, 8);

    if (topMatches.length === 0) {
        resultsContainer.innerHTML = '<div class="search-no-results">No entities found</div>';
    } else {
        // Type colors for result dots
        const typeColors = {
            'Person': '#3b82f6',
            'Character': '#3b82f6',
            'Organization': '#10b981',
            'Group': '#10b981',
            'Event': '#f59e0b',
            'Location': '#ef4444',
            'Place': '#ef4444',
            'Concept': '#8b5cf6',
            'Theme': '#8b5cf6',
            'Technology': '#06b6d4',
            'Product': '#ec4899',
            'Object': '#ec4899',
            'default': '#64748b'
        };

        resultsContainer.innerHTML = topMatches.map((match, idx) => {
            const color = typeColors[match.type] || typeColors.default;
            return `
                <div class="search-result-item ${idx === searchSelectedIndex ? 'selected' : ''}"
                     data-node-id="${escapeHtml(match.id)}"
                     onclick="navigateToNode('${escapeHtml(match.id)}')">
                    <span class="result-dot" style="background-color: ${color}"></span>
                    <div class="result-info">
                        <div class="result-name">${escapeHtml(match.label)}</div>
                        <div class="result-type">${escapeHtml(match.type)}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    resultsContainer.classList.remove('hidden');
}

function updateSearchSelection(results) {
    results.forEach((item, idx) => {
        item.classList.toggle('selected', idx === searchSelectedIndex);
    });

    // Scroll selected item into view
    if (searchSelectedIndex >= 0 && results[searchSelectedIndex]) {
        results[searchSelectedIndex].scrollIntoView({ block: 'nearest' });
    }
}

function navigateToNode(nodeId) {
    if (!cytoscapeInstance) return;

    const node = cytoscapeInstance.nodes(`[id = "${nodeId}"]`);
    if (node.length === 0) return;

    // Hide search results
    hideSearchResults();

    // Clear search input
    const searchInput = document.getElementById('kg-graph-search');
    if (searchInput) {
        searchInput.value = '';
        document.getElementById('kg-search-clear')?.classList.add('hidden');
    }

    // Animate to node
    cytoscapeInstance.animate({
        center: { eles: node },
        zoom: 1.8
    }, {
        duration: 400,
        easing: 'ease-out-cubic',
        complete: async () => {
            // Select the node
            selectedNodeData = node.data();
            highlightNodeNeighborhood(node, true);
            await selectNode(selectedNodeData);
        }
    });
}

function hideSearchResults() {
    const resultsContainer = document.getElementById('kg-search-results');
    resultsContainer?.classList.add('hidden');
    searchSelectedIndex = -1;
}

function renderEmptyGraph() {
    const container = document.getElementById('kg-graph-container');
    if (!container) return;

    // Clean up observer and instance
    if (graphResizeObserver) {
        graphResizeObserver.disconnect();
        graphResizeObserver = null;
    }
    if (cytoscapeInstance) {
        cytoscapeInstance.destroy();
        cytoscapeInstance = null;
    }

    container.innerHTML = `
        <div class="flex items-center justify-center h-full text-center">
            <div>
                <i class="ph-light ph-graph text-6xl text-[var(--text-muted)] opacity-50"></i>
                <p class="text-sm text-[var(--text-secondary)] mt-4">No graph data yet</p>
                <p class="text-xs text-[var(--text-muted)] mt-2">Extract entities from a video to populate the graph</p>
            </div>
        </div>
    `;
}

function changeGraphLayout(layout) {
    if (!cytoscapeInstance) return;

    const layoutOptions = {
        name: layout,
        animate: true,
        animationDuration: 500,
        fit: true,
        padding: 30
    };

    if (layout === 'cose') {
        layoutOptions.nodeRepulsion = 8000;
        layoutOptions.idealEdgeLength = 100;
        layoutOptions.edgeElasticity = 100;
    }

    cytoscapeInstance.layout(layoutOptions).run();

    document.querySelectorAll('.graph-layout-option').forEach(opt => {
        opt.classList.toggle('active', opt.dataset.layout === layout);
    });

    document.getElementById('graph-layout-dropdown')?.classList.add('hidden');
}

function fitGraphView() {
    if (!cytoscapeInstance) return;
    cytoscapeInstance.fit(null, 30);
}

function resetGraphView() {
    if (!cytoscapeInstance) return;
    cytoscapeInstance.zoom(1);
    cytoscapeInstance.center();
}

function updateGraphStats(data) {
    const nodes = data.nodes || [];
    const edges = data.edges || [];

    // Count unique entity types
    const types = new Set(nodes.map(n => n.data.type));

    document.getElementById('kg-stat-nodes').textContent = nodes.length;
    document.getElementById('kg-stat-edges').textContent = edges.length;
}

// ============================================
// Node Inspector Panel
// ============================================

async function selectNode(nodeData) {
    if (!kgCurrentProjectId || !nodeData) return;

    try {
        // Highlight selected node
        if (cytoscapeInstance) {
            cytoscapeInstance.nodes().removeClass('selected');
            cytoscapeInstance.nodes(`[id = "${nodeData.id}"]`).addClass('selected');
        }

        // Fetch neighbors
        const response = await fetch(`/kg/projects/${kgCurrentProjectId}/nodes/${nodeData.id}/neighbors`);
        if (!response.ok) {
            throw new Error('Failed to load node neighbors');
        }

        const neighbors = await response.json();
        updateInspector(nodeData, neighbors);
        showInspector();
    } catch (e) {
        console.error('Failed to select node:', e);
        showToast(e.message, 'error');
    }
}

function updateInspector(nodeData, neighbors) {
    const inspectorTitle = document.getElementById('kg-inspector-title');
    const inspectorContent = document.getElementById('kg-inspector-content');

    if (!inspectorTitle || !inspectorContent) return;

    // Update title
    inspectorTitle.textContent = nodeData.label;

    // Build inspector content - using flex layout for proper space distribution
    // Static fields (Type, Description, Aliases) stay fixed, Connections fills remaining space
    let html = `
        <div class="inspector-static-fields flex-shrink-0">
            <div class="inspector-field">
                <span class="label text-[10px] font-semibold text-[var(--text-muted)] uppercase">Type</span>
                <span class="badge badge-${nodeData.type.toLowerCase()} mt-1 inline-block px-2 py-1 text-[10px] font-medium rounded">${nodeData.type}</span>
            </div>
    `;

    // Description
    if (nodeData.description) {
        html += `
            <div class="inspector-field mt-3">
                <span class="label text-[10px] font-semibold text-[var(--text-muted)] uppercase">Description</span>
                <p class="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">${escapeHtml(nodeData.description)}</p>
            </div>
        `;
    }

    // Aliases
    if (nodeData.aliases && nodeData.aliases.length > 0) {
        html += `
            <div class="inspector-field mt-3">
                <span class="label text-[10px] font-semibold text-[var(--text-muted)] uppercase">Aliases</span>
                <div class="flex flex-wrap gap-1 mt-1">
                    ${nodeData.aliases.map(alias => `<span class="text-[10px] px-2 py-0.5 rounded bg-[var(--bg-tertiary)] text-[var(--text-secondary)]">${escapeHtml(alias)}</span>`).join('')}
                </div>
            </div>
        `;
    }

    html += `</div>`; // Close static fields wrapper

    // Connections - this section grows to fill available space
    if (neighbors && neighbors.length > 0) {
        html += `
            <div class="inspector-connections-section flex-1 min-h-0 mt-3 flex flex-col">
                <span class="label text-[10px] font-semibold text-[var(--text-muted)] uppercase flex-shrink-0">Connections (${neighbors.length})</span>
                <div class="mt-2 space-y-1 flex-1 overflow-y-auto min-h-0 pr-1">
                    ${neighbors.map(neighbor => `
                        <button onclick="selectNodeById('${neighbor.id}')"
                                class="w-full text-left text-xs px-2 py-1.5 rounded bg-[var(--bg-tertiary)] hover:bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">
                            <span class="font-medium">${escapeHtml(neighbor.label)}</span>
                            <span class="text-[10px] text-[var(--text-muted)] ml-1">(${neighbor.entity_type})</span>
                        </button>
                    `).join('')}
                </div>
            </div>
        `;
    }

    inspectorContent.innerHTML = html;
}

function showInspector() {
    const inspector = document.getElementById('kg-node-inspector');
    inspector?.classList.add('open');
}

function closeInspector() {
    const inspector = document.getElementById('kg-node-inspector');
    inspector?.classList.remove('open');

    // Clear highlights
    clearHighlights();

    // Deselect nodes in graph
    if (cytoscapeInstance) {
        cytoscapeInstance.nodes().removeClass('selected');
    }

    selectedNodeData = null;
}

async function selectNodeById(nodeId) {
    if (!kgCurrentProjectId) return;

    try {
        // Find node in graph
        if (cytoscapeInstance) {
            const node = cytoscapeInstance.nodes(`[id = "${nodeId}"]`);
            if (node.length > 0) {
                // Center on node
                cytoscapeInstance.animate({
                    center: { eles: node },
                    zoom: 1.5
                }, {
                    duration: 300
                });

                // Trigger selection
                selectedNodeData = node.data();
                await selectNode(selectedNodeData);
            }
        }
    } catch (e) {
        console.error('Failed to select node by ID:', e);
    }
}

// ============================================
// KG Event Listeners
// ============================================

function initKGEventListeners() {
    kgToggle?.addEventListener('click', toggleKGPanel);
    kgNewProjectBtn?.addEventListener('click', createKGProject);

    // Custom dropdown events
    kgDropdownToggle?.addEventListener('click', toggleKGDropdown);
    kgDropdownToggle?.addEventListener('keydown', handleDropdownKeydown);

    // Click outside to close
    document.addEventListener('click', (e) => {
        const dropdown = document.getElementById('kg-project-dropdown');
        if (dropdown && !dropdown.contains(e.target)) {
            closeKGDropdown();
        }
    });

    document.getElementById('kg-export-json')?.addEventListener('click', () => exportKGGraph('json'));
    document.getElementById('kg-export-graphml')?.addEventListener('click', () => exportKGGraph('graphml'));

    // View toggle buttons
    document.getElementById('kg-view-list-btn')?.addEventListener('click', () => toggleKGView('list'));
    document.getElementById('kg-view-graph-btn')?.addEventListener('click', () => toggleKGView('graph'));

    // Graph layout dropdown toggle
    document.getElementById('graph-layout-btn')?.addEventListener('click', (e) => {
        e.stopPropagation();
        const dropdown = document.getElementById('graph-layout-dropdown');
        dropdown?.classList.toggle('hidden');
    });

    // Close layout dropdown when clicking outside
    document.addEventListener('click', (e) => {
        const layoutSelector = document.querySelector('.graph-layout-selector');
        const layoutDropdown = document.getElementById('graph-layout-dropdown');
        if (layoutSelector && !layoutSelector.contains(e.target)) {
            layoutDropdown?.classList.add('hidden');
        }
    });

    // Inspector close button
    document.getElementById('kg-inspector-close')?.addEventListener('click', closeInspector);

    // Initialize graph search
    initGraphSearch();

    // Initialize sidebar collapse
    initSidebarCollapse();

    // Initialize header dropdowns
    initHeaderDropdowns();
}

// ============================================
// Sidebar Collapse/Expand
// ============================================

function initSidebarCollapse() {
    const sidebar = document.getElementById('sidebar');
    const collapseBtn = document.getElementById('sidebar-collapse-btn');
    const expandBtn = document.getElementById('sidebar-expand-btn');

    // Check for stored preference
    const isCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
    if (isCollapsed) {
        collapseSidebar();
    }

    // Collapse button (in sidebar header)
    collapseBtn?.addEventListener('click', collapseSidebar);

    // Expand button (in main header)
    expandBtn?.addEventListener('click', expandSidebar);
}

function collapseSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar?.classList.add('collapsed');
    document.body.classList.add('sidebar-collapsed');
    localStorage.setItem('sidebar-collapsed', 'true');
}

function expandSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar?.classList.remove('collapsed');
    document.body.classList.remove('sidebar-collapsed');
    localStorage.setItem('sidebar-collapsed', 'false');
}

// ============================================
// Header Dropdowns
// ============================================

function initHeaderDropdowns() {
    const layoutBtn = document.getElementById('header-layout-btn');
    const layoutMenu = document.getElementById('header-layout-menu');

    // Toggle layout dropdown
    layoutBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        layoutMenu?.classList.toggle('hidden');
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        const dropdown = document.getElementById('header-layout-dropdown');
        if (dropdown && !dropdown.contains(e.target)) {
            layoutMenu?.classList.add('hidden');
        }
    });

    // Update active state on layout change
    document.querySelectorAll('.header-dropdown-item[data-layout]').forEach(item => {
        item.addEventListener('click', () => {
            // Update active state
            document.querySelectorAll('.header-dropdown-item[data-layout]').forEach(i => {
                i.classList.remove('active');
            });
            item.classList.add('active');

            // Close dropdown
            layoutMenu?.classList.add('hidden');
        });
    });
}

// ============================================
// Job Progress UI
// ============================================

const JOB_POLL_INTERVAL_MS = window.APP_CONFIG?.JOB_POLL_INTERVAL_MS || 1000;
let jobProgressPollers = new Map();

const STAGE_LABELS = {
    'queued': 'Queued',
    'downloading': 'Downloading video',
    'extracting_audio': 'Extracting audio',
    'transcribing': 'Transcribing',
    'processing': 'Processing',
    'finalizing': 'Finalizing'
};

function createJobProgressUI(jobId, title = 'Processing') {
    const container = document.createElement('div');
    container.id = `job-progress-${jobId}`;
    container.className = 'job-progress-container';
    container.innerHTML = `
        <div class="job-progress-header">
            <div class="job-progress-title">
                <i class="ph-fill ph-spinner animate-spin"></i>
                <span>${escapeHtml(title)}</span>
            </div>
            <button class="job-progress-cancel" data-job-id="${jobId}">
                <i class="ph-bold ph-x-circle"></i> Cancel
            </button>
        </div>
        <div class="job-progress-bar-container">
            <div class="job-progress-bar animated" style="width: 0%"></div>
        </div>
        <div class="job-progress-info">
            <span class="job-progress-stage">Initializing...</span>
            <span class="job-progress-percent">0%</span>
        </div>
    `;

    const cancelBtn = container.querySelector('.job-progress-cancel');
    cancelBtn?.addEventListener('click', () => cancelJob(jobId));

    const messageContainer = chatMessages.querySelector('div.space-y-6');
    if (messageContainer) {
        messageContainer.appendChild(container);
        scrollToBottom();
    }

    startJobPolling(jobId);

    return jobId;
}

async function startJobPolling(jobId) {
    if (jobProgressPollers.has(jobId)) {
        return;
    }

    const pollerId = setInterval(() => updateJobProgress(jobId), JOB_POLL_INTERVAL_MS);
    jobProgressPollers.set(jobId, pollerId);

    await updateJobProgress(jobId);
}

function stopJobPolling(jobId) {
    const pollerId = jobProgressPollers.get(jobId);
    if (pollerId) {
        clearInterval(pollerId);
        jobProgressPollers.delete(jobId);
    }
}

async function updateJobProgress(jobId) {
    try {
        const response = await fetch(`/jobs/${jobId}`);

        if (!response.ok) {
            if (response.status === 404) {
                stopJobPolling(jobId);
                return;
            }
            throw new Error('Failed to fetch job status');
        }

        const job = await response.json();
        renderJobProgress(job);

        if (job.status === 'completed' || job.status === 'failed') {
            stopJobPolling(jobId);
            setTimeout(() => {
                const container = document.getElementById(`job-progress-${jobId}`);
                if (container) {
                    container.style.opacity = '0';
                    container.style.transform = 'translateY(-10px)';
                    container.style.transition = 'all 0.3s ease';
                    setTimeout(() => container.remove(), 300);
                }
            }, 3000);

            if (job.status === 'completed') {
                loadTranscripts();
            }
        }

    } catch (e) {
        console.error('Job progress update failed:', e);
    }
}

function renderJobProgress(job) {
    const container = document.getElementById(`job-progress-${job.id}`);
    if (!container) return;

    const progressBar = container.querySelector('.job-progress-bar');
    const stageEl = container.querySelector('.job-progress-stage');
    const percentEl = container.querySelector('.job-progress-percent');
    const cancelBtn = container.querySelector('.job-progress-cancel');

    if (progressBar) {
        progressBar.style.width = `${job.progress}%`;
        if (job.status === 'running') {
            progressBar.classList.add('animated');
        } else {
            progressBar.classList.remove('animated');
        }
    }

    if (stageEl) {
        stageEl.textContent = STAGE_LABELS[job.stage] || job.stage;
    }

    if (percentEl) {
        percentEl.textContent = `${job.progress}%`;
    }

    if (cancelBtn) {
        cancelBtn.disabled = job.status !== 'pending' && job.status !== 'running';
    }

    if (job.status === 'completed') {
        const existingStatus = container.querySelector('.job-progress-status');
        if (!existingStatus) {
            const statusDiv = document.createElement('div');
            statusDiv.className = 'job-progress-status success';
            statusDiv.innerHTML = '<i class="ph-fill ph-check-circle"></i><span>Completed successfully</span>';
            container.appendChild(statusDiv);
        }
    } else if (job.status === 'failed') {
        const existingStatus = container.querySelector('.job-progress-status');
        if (!existingStatus) {
            const statusDiv = document.createElement('div');
            statusDiv.className = 'job-progress-status error';
            const errorMsg = job.error || 'Job failed';
            statusDiv.innerHTML = `<i class="ph-fill ph-x-circle"></i><span>${escapeHtml(errorMsg)}</span>`;
            container.appendChild(statusDiv);
        }
    }
}

async function cancelJob(jobId) {
    if (!confirm('Cancel this job?')) return;

    try {
        const response = await fetch(`/jobs/${jobId}`, { method: 'DELETE' });

        if (!response.ok) {
            throw new Error('Failed to cancel job');
        }

        stopJobPolling(jobId);

        const container = document.getElementById(`job-progress-${jobId}`);
        if (container) {
            const statusDiv = document.createElement('div');
            statusDiv.className = 'job-progress-status cancelled';
            statusDiv.innerHTML = '<i class="ph-fill ph-warning-circle"></i><span>Cancelled</span>';
            container.appendChild(statusDiv);

            setTimeout(() => {
                container.style.opacity = '0';
                container.style.transform = 'translateY(-10px)';
                container.style.transition = 'all 0.3s ease';
                setTimeout(() => container.remove(), 300);
            }, 2000);
        }

        showToast('Job cancelled', 'info');

    } catch (e) {
        console.error('Cancel job failed:', e);
        showToast('Failed to cancel job', 'error');
    }
}

function cleanupAllJobPollers() {
    jobProgressPollers.forEach((pollerId) => clearInterval(pollerId));
    jobProgressPollers.clear();
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
// Empty State Management
// ============================================

function showEmptyState() {
    const emptyState = document.getElementById('empty-state');
    const messageContainer = chatMessages?.querySelector('div.space-y-6');
    if (emptyState) {
        emptyState.classList.remove('hidden');
    }
    if (messageContainer) {
        messageContainer.classList.add('hidden');
    }
}

function hideEmptyState() {
    const emptyState = document.getElementById('empty-state');
    const messageContainer = chatMessages?.querySelector('div.space-y-6');
    if (emptyState) {
        emptyState.classList.add('hidden');
    }
    if (messageContainer) {
        messageContainer.classList.remove('hidden');
    }
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
    hideEmptyState();

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
        hideEmptyState();
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

    // Initialize new session - show empty state initially
    showEmptyState();
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

    // Initialize KG event listeners
    initKGEventListeners();
}

function initSidebarData() {
    // Pre-load sidebar data (collapsed state)
    loadHistory();
    loadTranscripts();
    loadKGProjects();
}

// ============================================
// Cleanup on Page Unload
// ============================================

// Clean up intervals when page is unloaded to prevent memory leaks.
// Note: beforeunload is more reliable than unload for cleanup tasks.
window.addEventListener('beforeunload', () => {
    stopKGPolling();
    stopStatusPolling();
    cleanupAllJobPollers();
});

// Also clean up when tab becomes hidden (e.g., user switches tabs)
// This prevents unnecessary polling when the page isn't visible.
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopKGPolling();
        stopStatusPolling();
    } else {
        // Resume polling when tab becomes visible again
        startStatusPolling();
        if (kgCurrentProjectId) {
            startKGPolling();
        }
    }
});

// Run initialization when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Reset KG state for clean UX on page load
    // Users should start fresh - project can be reselected, view defaults to list
    kgCurrentProjectId = null;
    kgCurrentProject = null;
    kgCurrentView = 'list';
    sessionStorage.removeItem(KG_PROJECT_STORAGE_KEY);
    localStorage.setItem(KG_VIEW_STORAGE_KEY, 'list');

    initTheme();
    initMobileNav();
    initFileUpload();
    initEventListeners();
    initSidebarData();
    startStatusPolling();

    // Initialize view toggle buttons to list view
    const listBtn = document.getElementById('kg-view-list-btn');
    const graphBtn = document.getElementById('kg-view-graph-btn');
    listBtn?.classList.add('active');
    graphBtn?.classList.remove('active');
});

// Initialize session
initSession();
