// ============================================
// Chat Send Module
// Message sending with retry logic and error handling
// ============================================

import { state } from '../core/state.js';
import { MAX_RETRIES, RETRY_DELAY_MS } from '../core/config.js';
import { sleep } from '../core/utils.js';
import { addMessage, showLoading, removeLoading, updateLoadingActivity } from './messages.js';
import { showToast } from '../ui/toast.js';
import { createJobProgressUI, loadJobs } from '../jobs/jobs.js';
import { startActivityStream, stopActivityStream } from './activity.js';

// ============================================
// Job Detection Patterns
// ============================================

// Pattern to detect job ID in agent responses
// Handles: "Job ID: xxx", "Job ID `xxx`", "job: xxx", "Job ID: `xxx`"
const JOB_ID_PATTERN = /(?:job[:\s]+|Job ID[:\s]*)[`]?([a-f0-9-]{36})[`]?/gi;

// ============================================
// Job Detection
// ============================================

/**
 * Detect job IDs in agent response and create progress UI
 * @param {string} responseText - Agent response text
 */
function detectAndTrackJobs(responseText) {
    if (!responseText) return;

    // Find all job IDs in the response
    const matches = [...responseText.matchAll(JOB_ID_PATTERN)];
    const jobIds = [...new Set(matches.map(m => m[1]))];

    if (jobIds.length === 0) return;

    // Determine job type from response context
    const isTranscription = /transcri/i.test(responseText);
    const title = isTranscription ? 'Transcribing' : 'Processing';

    // Create progress UI for each detected job
    for (const jobId of jobIds) {
        createJobProgressUI(jobId, title);
    }

    // Refresh the jobs sidebar panel
    loadJobs();

    // Show toast notification
    if (jobIds.length === 1) {
        showToast('Background job started', 'info');
    } else {
        showToast(`${jobIds.length} background jobs started`, 'info');
    }
}

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

    // Start activity stream to show real-time agent status
    startActivityStream((activityText, toolName) => {
        updateLoadingActivity(loadingId, activityText, toolName);
    });

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
                stopActivityStream();
                removeLoading(loadingId);
                showToast('Operation timed out', 'error');
                addMessage('**Timeout:** The operation took too long. Please try again with a shorter video.', 'agent');
                state.isProcessing = false;
                return false;
            }

            if (response.status === 422) {
                const errorData = await response.json();
                stopActivityStream();
                removeLoading(loadingId);
                const errorMsg = errorData.detail || 'Invalid input';
                showToast(errorMsg, 'error');
                addMessage(`**Validation Error:** ${errorMsg}`, 'agent');
                state.isProcessing = false;
                return false;
            }

            // Handle session expired (410 Gone)
            if (response.status === 410) {
                stopActivityStream();
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
            stopActivityStream();
            removeLoading(loadingId);
            addMessage(data.response, 'agent', data.usage);

            // Detect job creation in response and show progress UI
            detectAndTrackJobs(data.response);

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
    stopActivityStream();
    removeLoading(loadingId);
    showToast('Failed to send message', 'error');
    addMessage(`**Error:** ${lastError?.message || 'Unknown error'}. Please try again.`, 'agent');
    state.isProcessing = false;
    return false;
}
