// ============================================
// History Management
// ============================================

import { escapeHtml, formatRelativeTime } from '../core/utils.js';
import { showToast } from '../ui/toast.js';
import { state } from '../core/state.js';

export async function loadHistory() {
    const historyList = document.getElementById('history-list');

    // Show skeleton loader
    if (historyList) {
        historyList.innerHTML = `
            <div class="skeleton-loader">
                <div class="skeleton-line h-4 w-3/4"></div>
                <div class="skeleton-line h-3 w-1/2 mt-1"></div>
            </div>
            <div class="skeleton-loader">
                <div class="skeleton-line h-4 w-2/3"></div>
                <div class="skeleton-line h-3 w-1/2 mt-1"></div>
            </div>
            <div class="skeleton-loader">
                <div class="skeleton-line h-4 w-3/4"></div>
                <div class="skeleton-line h-3 w-1/2 mt-1"></div>
            </div>
        `;
    }

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

export function renderHistoryList(sessions) {
    const historyList = document.getElementById('history-list');
    if (!historyList) return;

    if (sessions.length === 0) {
        historyList.innerHTML = '<p class="text-xs text-[var(--sidebar-text-muted)] px-2 py-1">No history yet</p>';
        return;
    }

    historyList.innerHTML = sessions.map(s => `
        <button
            onclick="window.loadSession('${escapeHtml(s.session_id)}')"
            class="w-full text-left px-2 py-1.5 text-xs rounded-md transition-all
                   text-[var(--sidebar-text-secondary)] hover:bg-[var(--sidebar-hover)] hover:text-[var(--sidebar-text-primary)]"
            title="${escapeHtml(s.title || 'Untitled')}"
        >
            <div class="truncate font-medium">${escapeHtml(s.title || 'Untitled')}</div>
            <div class="text-[var(--sidebar-text-muted)] text-[10px]">${formatRelativeTime(s.updated_at)} · ${s.message_count} msgs</div>
        </button>
    `).join('');
}

export function toggleHistoryPanel() {
    const historyList = document.getElementById('history-list');
    const historyCaret = document.getElementById('history-caret');

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

export async function loadSession(loadSessionId) {
    if (loadSessionId === state.sessionId) return;

    if (state.isProcessing) {
        if (!confirm('A message is being processed. Switch session anyway?')) {
            return;
        }
    }

    // Close current session
    try {
        await fetch(`/chat/${state.sessionId}`, { method: 'DELETE' });
    } catch (e) {
        console.warn('Failed to close current session:', e);
    }

    // Switch to new session
    sessionStorage.setItem('agent_session_id', loadSessionId);
    window.location.reload();
}

export async function deleteHistoryItem(historySessionId) {
    if (!confirm('Delete this session history?')) return;

    try {
        await fetch(`/history/${historySessionId}`, { method: 'DELETE' });
        loadHistory();
    } catch (e) {
        console.error('Delete failed:', e);
        showToast('Failed to delete history item', 'error');
    }
}

// Expose to global scope for onclick handlers
window.loadSession = loadSession;
window.deleteHistoryItem = deleteHistoryItem;
