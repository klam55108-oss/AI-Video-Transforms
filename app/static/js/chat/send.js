// ============================================
// Chat Send Module
// Message sending with retry logic and error handling
// ============================================

import { state } from '../core/state.js';
import { MAX_RETRIES, RETRY_DELAY_MS } from '../core/config.js';
import { sleep } from '../core/utils.js';
import { addMessage, showLoading, removeLoading } from './messages.js';
import { showToast } from '../ui/toast.js';

// ============================================
// Message Sending
// ============================================

export async function sendMessage(message, showInUI = true) {
    if (state.isProcessing) {
        showToast('Already processing a message', 'warning');
        return false;
    }

    state.isProcessing = true;

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
                body: JSON.stringify({ session_id: state.sessionId, message })
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
                state.isProcessing = false;
                return false;
            }

            if (response.status === 422) {
                const errorData = await response.json();
                removeLoading(loadingId);
                const errorMsg = errorData.detail || 'Invalid input';
                showToast(errorMsg, 'error');
                addMessage(`**Validation Error:** ${errorMsg}`, 'agent');
                state.isProcessing = false;
                return false;
            }

            // Handle session expired (410 Gone)
            if (response.status === 410) {
                removeLoading(loadingId);
                showToast('Session expired. Please start a new session.', 'warning');
                addMessage('**Session Expired**\n\nYour session has ended. This can happen after server restarts or prolonged inactivity.\n\nClick **"New Chat"** in the sidebar to start a fresh conversation.', 'agent');

                // Clear session state
                sessionStorage.removeItem('agent_session_id');
                state.isProcessing = false;

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
            // Note: This creates a circular dependency - loadTranscripts will be injected at runtime
            if (window.loadTranscripts && typeof window.loadTranscripts === 'function') {
                const transcriptsList = document.getElementById('transcripts-list');
                if (transcriptsList && transcriptsList.classList.contains('open')) {
                    window.loadTranscripts();
                }
            }

            state.isProcessing = false;
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
    state.isProcessing = false;
    return false;
}
