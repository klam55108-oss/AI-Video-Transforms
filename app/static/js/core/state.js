// ============================================
// Centralized Application State
// ============================================

import { KG_PROJECT_STORAGE_KEY, KG_VIEW_STORAGE_KEY, getKGPollInterval as configGetKGPollInterval } from './config.js';

// Re-export storage keys for modules that need them
export { KG_PROJECT_STORAGE_KEY, KG_VIEW_STORAGE_KEY };

// Re-export config function
export function getKGPollInterval() {
    return configGetKGPollInterval();
}

// Generate session ID
function generateSessionId() {
    let sessionId = sessionStorage.getItem('agent_session_id');
    if (!sessionId) {
        sessionId = crypto.randomUUID();
        sessionStorage.setItem('agent_session_id', sessionId);
    }
    return sessionId;
}

// ============================================
// Unified State Object
// ============================================
// All modules import and access this shared state object directly.
// DOM elements are initialized via initDOMReferences() on DOMContentLoaded.

export const state = {
    // Session Management
    sessionId: generateSessionId(),
    isProcessing: false,
    statusInterval: null,
    fileInput: null,

    // KG Project State
    kgCurrentProjectId: null,
    kgCurrentProject: null,
    kgPollInterval: null,
    kgDropdownFocusedIndex: -1,

    // KG Graph View State
    kgCurrentView: localStorage.getItem(KG_VIEW_STORAGE_KEY) || 'list',
    cytoscapeInstance: null,
    selectedNodeData: null,
    graphResizeObserver: null,

    // Workspace layout state
    workspaceLayout: 'chat-only',  // 'chat-only' | 'chat-kg' | 'chat-kg-inspector'
    panelWidths: { chat: 50, kg: 50 },  // Percentage widths

    // DOM Element References (initialized in main.js)
    // KG Panel Elements
    kgContent: null,
    kgCaret: null,
    kgToggle: null,
    kgEmptyState: null,
    kgWorkflow: null,

    // KG Dropdown Elements
    kgDropdownLabel: null,
    kgDropdownList: null,
    kgDropdownToggle: null,

    // KG State & Action Elements
    kgStateBadge: null,
    kgStateLabel: null,
    kgActionBtn: null,
    kgProgress: null,
    kgProgressText: null,
    kgPendingBadge: null,

    // KG Confirmations & Stats
    kgConfirmations: null,
    kgConfirmationsList: null,
    kgStats: null,
    kgExport: null
};

// ============================================
// Initialize DOM References
// ============================================
// Called from main.js on DOMContentLoaded

export function initDOMReferences() {
    // KG Panel Elements
    state.kgContent = document.getElementById('kg-content');
    state.kgCaret = document.getElementById('kg-caret');
    state.kgToggle = document.getElementById('kg-toggle');
    state.kgEmptyState = document.getElementById('kg-empty-state');
    state.kgWorkflow = document.getElementById('kg-workflow');

    // KG Dropdown Elements
    state.kgDropdownLabel = document.getElementById('kg-dropdown-label');
    state.kgDropdownList = document.getElementById('kg-dropdown-list');
    state.kgDropdownToggle = document.getElementById('kg-dropdown-toggle');

    // KG State & Action Elements
    state.kgStateBadge = document.getElementById('kg-state-badge');
    state.kgStateLabel = document.getElementById('kg-state-label');
    state.kgActionBtn = document.getElementById('kg-action-btn');
    state.kgProgress = document.getElementById('kg-progress');
    state.kgProgressText = document.getElementById('kg-progress-text');
    state.kgPendingBadge = document.getElementById('kg-pending-badge');

    // KG Confirmations & Stats
    state.kgConfirmations = document.getElementById('kg-confirmations');
    state.kgConfirmationsList = document.getElementById('kg-confirmations-list');
    state.kgStats = document.getElementById('kg-stats');
    state.kgExport = document.getElementById('kg-export');
}

// ============================================
// State Reset Functions
// ============================================

export function resetKGState() {
    state.kgCurrentProjectId = null;
    state.kgCurrentProject = null;
    state.kgCurrentView = 'list';
    sessionStorage.removeItem(KG_PROJECT_STORAGE_KEY);
    localStorage.setItem(KG_VIEW_STORAGE_KEY, 'list');
}

export function resetSession() {
    state.sessionId = generateSessionId();
    state.isProcessing = false;
}
