// ============================================
// Chat Session Module
// Session initialization and restoration
// ============================================

import { state } from '../core/state.js';
import { addMessage, showLoading, removeLoading, showEmptyState, hideEmptyState } from './messages.js';

// ============================================
// Session Management
// ============================================

// DOM reference getter (lazy lookup for consistency with state.js pattern)
function getChatMessages() {
    return document.getElementById('chat-messages');
}

export async function loadExistingSession() {
    try {
        const response = await fetch(`/history/${state.sessionId}`);
        if (!response.ok) return null;
        const data = await response.json();
        return data.messages || [];
    } catch (e) {
        console.warn('No existing session history:', e);
        return null;
    }
}

export async function initSession() {
    // Re-enable input (in case it was disabled by session expiry)
    const userInputEl = document.getElementById('user-input');
    if (userInputEl) {
        userInputEl.disabled = false;
        userInputEl.placeholder = 'Type your message...';
    }

    // Clear any placeholder content
    const chatMessages = getChatMessages();
    const listContainer = chatMessages?.querySelector('div.space-y-6');
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
        const container = chatMessages?.querySelector('div.space-y-6');
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
            body: JSON.stringify({ session_id: state.sessionId })
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
