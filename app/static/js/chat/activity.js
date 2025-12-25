// ============================================
// Chat Activity Module
// Real-time activity streaming from agent processing
// ============================================

import { state } from '../core/state.js';

// ============================================
// Activity Stream State
// ============================================

/** @type {EventSource|null} */
let activityEventSource = null;

/** @type {function(string, string|null): void|null} */
let activityUpdateCallback = null;

/** @type {number|null} */
let pollingIntervalId = null;

/** @type {number|null} */
let debounceTimeoutId = null;

/** @type {{text: string, toolName: string|null}|null} */
let pendingActivity = null;

// Use SSE by default, fall back to polling if needed
let usePollingFallback = false;

// Debounce interval to smooth rapid tool sequences (ms)
const ACTIVITY_DEBOUNCE_MS = 150;

// ============================================
// Activity Text Formatting
// ============================================

/**
 * Format activity event into display text with emoji
 * @param {Object} event - Activity event from server
 * @returns {string} Formatted display text
 */
function formatActivityText(event) {
    if (!event || !event.type) return '';

    // Use the server-provided message directly (includes emojis)
    return event.message || '';
}

/**
 * Debounced activity update to smooth rapid tool sequences.
 * Prevents UI flicker when tools execute in quick succession.
 * @param {string} text - Activity text to display
 * @param {string|null} toolName - Optional tool name
 */
function debouncedActivityUpdate(text, toolName) {
    // Store the latest activity
    pendingActivity = { text, toolName };

    // Clear any existing timeout
    if (debounceTimeoutId) {
        clearTimeout(debounceTimeoutId);
    }

    // Schedule the update after debounce interval
    debounceTimeoutId = setTimeout(() => {
        if (pendingActivity && activityUpdateCallback) {
            activityUpdateCallback(pendingActivity.text, pendingActivity.toolName);
            pendingActivity = null;
        }
        debounceTimeoutId = null;
    }, ACTIVITY_DEBOUNCE_MS);
}

/**
 * Flush any pending debounced activity immediately.
 * Called when stream ends to ensure final state is shown.
 */
function flushPendingActivity() {
    if (debounceTimeoutId) {
        clearTimeout(debounceTimeoutId);
        debounceTimeoutId = null;
    }
    if (pendingActivity && activityUpdateCallback) {
        activityUpdateCallback(pendingActivity.text, pendingActivity.toolName);
        pendingActivity = null;
    }
}

// ============================================
// SSE Connection Management
// ============================================

/**
 * Start listening to activity events via SSE
 * @param {function(string, string|null): void} onUpdate - Callback for activity updates
 */
export function startActivityStream(onUpdate) {
    if (!state.sessionId) {
        console.warn('Cannot start activity stream: no session ID');
        return;
    }

    // Stop any existing stream first (before setting new callback)
    stopActivityStream();

    // Store callback for updates AFTER stopping (stopActivityStream clears it)
    activityUpdateCallback = onUpdate;

    if (usePollingFallback) {
        startPollingFallback();
        return;
    }

    try {
        const url = `/chat/activity/${state.sessionId}`;
        activityEventSource = new EventSource(url);

        activityEventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                const text = formatActivityText(data);

                if (text) {
                    // Use debounced update to smooth rapid tool sequences
                    debouncedActivityUpdate(text, data.tool_name || null);
                }

                // Stop stream on completion (flush pending first)
                if (data.type === 'completed') {
                    flushPendingActivity();
                    stopActivityStream();
                }
            } catch (err) {
                console.warn('Failed to parse activity event:', err);
            }
        };

        activityEventSource.onerror = (err) => {
            console.warn('Activity SSE error, falling back to polling:', err);
            usePollingFallback = true;
            stopActivityStream();
            startPollingFallback();
        };

    } catch (err) {
        console.warn('Failed to create EventSource, using polling:', err);
        usePollingFallback = true;
        startPollingFallback();
    }
}

/**
 * Stop listening to activity events
 */
export function stopActivityStream() {
    if (activityEventSource) {
        activityEventSource.close();
        activityEventSource = null;
    }

    if (pollingIntervalId) {
        clearInterval(pollingIntervalId);
        pollingIntervalId = null;
    }

    // Clean up debounce state
    if (debounceTimeoutId) {
        clearTimeout(debounceTimeoutId);
        debounceTimeoutId = null;
    }
    pendingActivity = null;

    activityUpdateCallback = null;
}

// ============================================
// Polling Fallback
// ============================================

// Polling interval - reduced from 500ms to 1000ms to lower server load
const POLLING_INTERVAL_MS = 1000;

/**
 * Start polling for activity (fallback when SSE fails)
 */
function startPollingFallback() {
    if (!state.sessionId || !activityUpdateCallback) return;

    const pollActivity = async () => {
        try {
            const response = await fetch(`/chat/activity/${state.sessionId}/current`);
            if (!response.ok) return;

            const data = await response.json();
            if (data.type && data.message) {
                // Use debouncing for consistency with SSE path
                debouncedActivityUpdate(data.message, data.tool_name || null);
            }
        } catch (err) {
            // Silently ignore polling errors
        }
    };

    // Poll immediately, then at configured interval
    pollActivity();
    pollingIntervalId = setInterval(pollActivity, POLLING_INTERVAL_MS);
}

// ============================================
// Activity Display Helpers
// ============================================

/**
 * Get activity icon based on type
 * @param {string} activityType - Activity type from server
 * @returns {string} Icon class or emoji
 */
export function getActivityIcon(activityType) {
    switch (activityType) {
        case 'thinking':
            return 'ph-brain';
        case 'tool_use':
            return 'ph-wrench';
        case 'tool_result':
            return 'ph-check-circle';
        case 'subagent':
            return 'ph-users-three';
        case 'completed':
            return 'ph-sparkle';
        default:
            return 'ph-circle-notch';
    }
}
