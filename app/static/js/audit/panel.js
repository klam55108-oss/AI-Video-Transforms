// ============================================
// Audit Panel Module
// ============================================
// Handles sidebar panel rendering and real-time audit event display

import { state } from '../core/state.js';
import { escapeHtml, formatDuration } from '../core/utils.js';
import { fetchAuditStats, fetchSessionAuditLog, fetchAuditSessions, triggerAuditCleanup } from './api.js';

// ============================================
// DOM Accessors (lazy lookup pattern)
// ============================================

function getAuditToggle() {
    return document.getElementById('audit-toggle');
}

function getAuditCaret() {
    return document.getElementById('audit-caret');
}

function getAuditContent() {
    return document.getElementById('audit-content');
}

function getAuditEventsList() {
    return document.getElementById('audit-events-list');
}

function getAuditEmpty() {
    return document.getElementById('audit-empty');
}

function getAuditCountBadge() {
    return document.getElementById('audit-count-badge');
}

function getAuditStatsContainer() {
    return document.getElementById('audit-stats');
}

// ============================================
// State
// ============================================

let isAuditPanelExpanded = false;
let auditPollingInterval = null;
let lastEventCount = 0;
let lastFirstEventId = null;  // Track first event ID to detect content changes

// Use server-injected config for consistency with other poll intervals
function getAuditPollInterval() {
    return window.APP_CONFIG?.AUDIT_POLL_INTERVAL_MS || 3000;
}

// ============================================
// Panel Toggle
// ============================================

export function toggleAuditPanel() {
    const content = getAuditContent();
    const caret = getAuditCaret();

    if (!content || !caret) return;

    isAuditPanelExpanded = !isAuditPanelExpanded;

    if (isAuditPanelExpanded) {
        content.classList.remove('hidden');
        content.classList.add('open');
        caret.classList.add('open');  // Use 'open' class to match CSS (.panel-caret.open)
        loadCurrentSessionAudit();
        startAuditPolling();
    } else {
        content.classList.remove('open');
        content.classList.add('hidden');
        caret.classList.remove('open');
        stopAuditPolling();
    }
}

// ============================================
// Polling
// ============================================

export function startAuditPolling() {
    if (auditPollingInterval) return;

    auditPollingInterval = setInterval(() => {
        if (isAuditPanelExpanded && state.sessionId) {
            loadCurrentSessionAudit();
            loadAuditStats();
        }
    }, getAuditPollInterval());
}

export function stopAuditPolling() {
    if (auditPollingInterval) {
        clearInterval(auditPollingInterval);
        auditPollingInterval = null;
    }
}

// ============================================
// Data Loading
// ============================================

export async function loadCurrentSessionAudit() {
    if (!state.sessionId) {
        renderEmptyState('No active session');
        return;
    }

    const data = await fetchSessionAuditLog(state.sessionId, 30, 0);
    renderAuditEvents(data.entries, data.total_count);
}

export async function loadAuditStats() {
    const stats = await fetchAuditStats();
    if (stats) {
        renderAuditStats(stats);
    }
}

export async function loadHistoricalSessions() {
    const data = await fetchAuditSessions(10);
    return data.sessions || [];
}

// ============================================
// Rendering
// ============================================

function renderEmptyState(message = 'No audit events yet') {
    const eventsList = getAuditEventsList();
    const emptyEl = getAuditEmpty();
    const badge = getAuditCountBadge();

    if (eventsList) eventsList.innerHTML = '';
    if (emptyEl) {
        emptyEl.textContent = message;
        emptyEl.classList.remove('hidden');
    }
    if (badge) badge.classList.add('hidden');
}

function renderAuditEvents(entries, totalCount) {
    const eventsList = getAuditEventsList();
    const emptyEl = getAuditEmpty();
    const badge = getAuditCountBadge();

    if (!eventsList) return;

    // Update badge
    if (badge) {
        if (totalCount > 0) {
            badge.textContent = totalCount > 99 ? '99+' : totalCount;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }

    // Handle empty state
    if (!entries || entries.length === 0) {
        renderEmptyState();
        return;
    }

    if (emptyEl) emptyEl.classList.add('hidden');

    // Check if we need to re-render by comparing count AND first event ID.
    // Comparing only count would miss updates if events are replaced (same count, different content).
    const firstEventId = entries[0]?.id || null;
    if (entries.length === lastEventCount && firstEventId === lastFirstEventId) {
        return; // No change
    }
    lastEventCount = entries.length;
    lastFirstEventId = firstEventId;

    // Render events
    eventsList.innerHTML = entries.map(entry => renderAuditEventItem(entry)).join('');
}

function renderAuditEventItem(entry) {
    const { icon, iconColor, bgColor } = getEventIconAndColor(entry);
    const timestamp = formatTimestamp(entry.timestamp);
    const toolName = entry.tool_name ? escapeHtml(entry.tool_name) : '';
    const summary = entry.summary ? escapeHtml(entry.summary) : '';
    const duration = formatDuration(entry.duration_ms);

    const blockedClass = entry.blocked ? 'audit-event-blocked' : '';
    const successClass = entry.success === false ? 'audit-event-failed' : '';

    return `
        <div class="audit-event-item ${blockedClass} ${successClass}" title="${summary}">
            <div class="audit-event-icon ${bgColor}">
                <i class="ph-fill ${icon} ${iconColor}"></i>
            </div>
            <div class="audit-event-content">
                <div class="audit-event-header">
                    <span class="audit-event-tool">${toolName || entry.event_type}</span>
                    ${duration ? `<span class="audit-event-duration">${duration}</span>` : ''}
                </div>
                <div class="audit-event-summary">${summary}</div>
                <div class="audit-event-time">${timestamp}</div>
            </div>
            ${renderEventBadges(entry)}
        </div>
    `;
}

function renderEventBadges(entry) {
    let badges = '';

    if (entry.blocked) {
        badges += '<span class="audit-badge audit-badge-blocked">Blocked</span>';
    }
    if (entry.success === false) {
        badges += '<span class="audit-badge audit-badge-failed">Failed</span>';
    }
    if (entry.success === true && !entry.blocked) {
        badges += '<span class="audit-badge audit-badge-success">OK</span>';
    }

    return badges ? `<div class="audit-event-badges">${badges}</div>` : '';
}

function getEventIconAndColor(entry) {
    const eventType = entry.event_type || '';
    const toolName = entry.tool_name || '';

    // Blocked events
    if (entry.blocked) {
        return { icon: 'ph-shield-warning', iconColor: 'text-red-400', bgColor: 'bg-red-500/20' };
    }

    // Failed events
    if (entry.success === false) {
        return { icon: 'ph-x-circle', iconColor: 'text-orange-400', bgColor: 'bg-orange-500/20' };
    }

    // Event type specific icons
    if (eventType === 'pre_tool_use') {
        return { icon: 'ph-play', iconColor: 'text-cyan-400', bgColor: 'bg-cyan-500/20' };
    }
    if (eventType === 'post_tool_use') {
        return { icon: 'ph-check', iconColor: 'text-green-400', bgColor: 'bg-green-500/20' };
    }
    if (eventType === 'session_stop') {
        return { icon: 'ph-stop', iconColor: 'text-purple-400', bgColor: 'bg-purple-500/20' };
    }
    if (eventType === 'subagent_stop') {
        return { icon: 'ph-flow-arrow', iconColor: 'text-indigo-400', bgColor: 'bg-indigo-500/20' };
    }

    // Tool-specific icons
    if (toolName === 'Bash') {
        return { icon: 'ph-terminal', iconColor: 'text-green-400', bgColor: 'bg-green-500/20' };
    }
    if (toolName === 'Read') {
        return { icon: 'ph-file-text', iconColor: 'text-blue-400', bgColor: 'bg-blue-500/20' };
    }
    if (toolName === 'Write' || toolName === 'Edit') {
        return { icon: 'ph-pencil', iconColor: 'text-yellow-400', bgColor: 'bg-yellow-500/20' };
    }
    if (toolName.startsWith('mcp__')) {
        return { icon: 'ph-plug', iconColor: 'text-cyan-400', bgColor: 'bg-cyan-500/20' };
    }

    // Default
    return { icon: 'ph-gear', iconColor: 'text-gray-400', bgColor: 'bg-gray-500/20' };
}

function formatTimestamp(timestamp) {
    if (!timestamp) return '';

    // Timestamp is in seconds (Unix epoch)
    const date = new Date(timestamp * 1000);
    const now = new Date();
    const diffMs = now - date;
    const diffSecs = Math.floor(diffMs / 1000);

    if (diffSecs < 5) return 'Just now';
    if (diffSecs < 60) return `${diffSecs}s ago`;
    if (diffSecs < 3600) return `${Math.floor(diffSecs / 60)}m ago`;
    if (diffSecs < 86400) return `${Math.floor(diffSecs / 3600)}h ago`;

    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function renderAuditStats(stats) {
    const container = getAuditStatsContainer();
    if (!container) return;

    const avgDuration = stats.avg_tool_duration_ms
        ? formatDuration(stats.avg_tool_duration_ms)
        : '-';

    container.innerHTML = `
        <div class="audit-stats-grid">
            <div class="audit-stat">
                <div class="audit-stat-value">${stats.tools_invoked || 0}</div>
                <div class="audit-stat-label">Invoked</div>
            </div>
            <div class="audit-stat audit-stat-success">
                <div class="audit-stat-value">${stats.tools_succeeded || 0}</div>
                <div class="audit-stat-label">Success</div>
            </div>
            <div class="audit-stat audit-stat-blocked">
                <div class="audit-stat-value">${stats.tools_blocked || 0}</div>
                <div class="audit-stat-label">Blocked</div>
            </div>
            <div class="audit-stat">
                <div class="audit-stat-value">${avgDuration}</div>
                <div class="audit-stat-label">Avg Time</div>
            </div>
        </div>
    `;
}

// ============================================
// Cleanup
// ============================================

export async function handleAuditCleanup() {
    if (!confirm('Clean up audit logs older than 7 days?')) {
        return;
    }
    await triggerAuditCleanup();
    loadCurrentSessionAudit();
    loadAuditStats();
}

// ============================================
// Initialization
// ============================================

export function initAuditPanel() {
    const toggle = getAuditToggle();
    if (toggle) {
        toggle.addEventListener('click', toggleAuditPanel);
    }

    // Initial data load (but don't start polling until panel is opened)
    loadAuditStats();
}
