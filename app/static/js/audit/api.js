// ============================================
// Audit API Client
// ============================================
// Handles all communication with the /audit/* endpoints

import { showToast } from '../ui/toast.js';

/**
 * Fetch aggregate audit statistics.
 * @returns {Promise<{total_events: number, tools_invoked: number, tools_blocked: number, tools_succeeded: number, tools_failed: number, sessions_stopped: number, subagents_stopped: number, avg_tool_duration_ms: number|null}>}
 */
export async function fetchAuditStats() {
    try {
        const response = await fetch('/audit/stats');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (err) {
        console.error('Failed to fetch audit stats:', err);
        return null;
    }
}

/**
 * Fetch list of sessions with audit logs.
 * @param {number} limit - Max number of sessions to return
 * @returns {Promise<{sessions: Array<{session_id: string, event_count: number, last_modified: number}>}>}
 */
export async function fetchAuditSessions(limit = 20) {
    try {
        const response = await fetch(`/audit/sessions?limit=${limit}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (err) {
        console.error('Failed to fetch audit sessions:', err);
        return { sessions: [] };
    }
}

/**
 * Fetch audit log for a specific session.
 * @param {string} sessionId - The session ID to fetch logs for
 * @param {number} limit - Max entries per page
 * @param {number} offset - Pagination offset
 * @returns {Promise<{session_id: string, entries: Array, total_count: number, has_more: boolean}>}
 */
export async function fetchSessionAuditLog(sessionId, limit = 50, offset = 0) {
    try {
        const params = new URLSearchParams({ limit, offset });
        const response = await fetch(`/audit/sessions/${sessionId}?${params}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (err) {
        console.error(`Failed to fetch audit log for session ${sessionId}:`, err);
        return { session_id: sessionId, entries: [], total_count: 0, has_more: false };
    }
}

/**
 * Trigger manual cleanup of old audit logs.
 * @returns {Promise<{success: boolean, sessions_cleaned: number}>}
 */
export async function triggerAuditCleanup() {
    try {
        const response = await fetch('/audit/cleanup', { method: 'POST' });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        if (data.success) {
            showToast(`Cleaned up ${data.sessions_cleaned} old audit sessions`, 'success');
        }
        return data;
    } catch (err) {
        console.error('Failed to trigger audit cleanup:', err);
        showToast('Failed to clean up audit logs', 'error');
        return { success: false, sessions_cleaned: 0 };
    }
}
