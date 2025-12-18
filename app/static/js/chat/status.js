// ============================================
// Chat Status Module
// Agent status polling and rendering
// ============================================

import { state } from '../core/state.js';
import { getStatusPollInterval } from '../core/config.js';

// ============================================
// Status Polling State
// ============================================

let statusInterval = null;

// ============================================
// Status Polling
// ============================================

export function startStatusPolling() {
    updateStatus();
    statusInterval = setInterval(updateStatus, getStatusPollInterval());
}

export function stopStatusPolling() {
    if (statusInterval) {
        clearInterval(statusInterval);
        statusInterval = null;
    }
}

export async function updateStatus() {
    if (!state.sessionId) return;

    try {
        const response = await fetch(`/status/${state.sessionId}`);

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

export function renderStatus(status) {
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
