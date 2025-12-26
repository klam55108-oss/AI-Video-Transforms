// ============================================
// Main Entry Point - ES Module Initialization
// ============================================
// Aggregates all modules and initializes the application

// ============================================
// Core Module Imports
// ============================================
import { state, initDOMReferences, resetKGState, KG_PROJECT_STORAGE_KEY, KG_VIEW_STORAGE_KEY } from './core/state.js';

// ============================================
// UI Module Imports
// ============================================
import { initTheme } from './ui/theme.js';
import { initToastContainer } from './ui/toast.js';
import { initMobileNav } from './ui/mobile.js';
import { initSidebarCollapse } from './ui/sidebar.js';
import { initHeaderDropdowns } from './ui/header.js';
import { initWorkspace } from './ui/workspace.js';

// ============================================
// Chat Module Imports
// ============================================
import { initSession } from './chat/session.js';
import { startStatusPolling, stopStatusPolling } from './chat/status.js';
import { sendMessage } from './chat/send.js';

// ============================================
// Panel Module Imports
// ============================================
import { loadHistory, toggleHistoryPanel, loadSession, deleteHistoryItem } from './panels/history.js';
import { loadTranscripts, toggleTranscriptsPanel, downloadTranscript, deleteTranscript } from './panels/transcripts.js';
import { initTranscriptSearch } from './panels/transcript-search.js';
import { initTranscriptViewer, openTranscriptViewer, closeModal } from './panels/transcript-viewer.js';

// ============================================
// Jobs Module Imports
// ============================================
import { cleanupAllJobPollers, cancelJob, toggleJobsPanel, loadJobs } from './jobs/jobs.js';

// ============================================
// Audit Module Imports
// ============================================
import {
    toggleAuditPanel,
    startAuditPolling,
    stopAuditPolling,
    loadCurrentSessionAudit,
    loadAuditStats,
    handleAuditCleanup,
    initAuditPanel
} from './audit/index.js';

// ============================================
// Upload Module Imports
// ============================================
import { initFileUpload } from './upload/upload.js';

// ============================================
// Knowledge Graph Module Imports (via index.js aggregator)
// ============================================
import {
    // API
    kgClient,
    // Panel
    toggleKGPanel,
    toggleKGAdvanced,
    loadKGProjects,
    selectKGProject,
    toggleKGDropdown,
    handleDropdownSelect,
    handleDropdownKeydown,
    deleteKGProject,
    // Actions
    createKGProject,
    confirmKGDiscovery,
    exportKGGraph,
    batchExportKGProjects,
    initBatchExportModal,
    // Polling
    startKGPolling,
    stopKGPolling,
    // Graph
    initKGGraph,
    toggleKGView,
    changeGraphLayout,
    fitGraphView,
    resetGraphView,
    filterByType,
    clearTypeFilter,
    // Search
    initGraphSearch,
    navigateToNode,
    hideSearchResults,
    toggleTypeFilter,
    clearAllFilters,
    // Inspector
    selectNodeById,
    closeInspector
} from './kg/index.js';

// ============================================
// Global Exports for Inline onclick Handlers
// ============================================
// These functions are called from HTML onclick attributes

// History panel
window.loadSession = loadSession;
window.deleteHistoryItem = deleteHistoryItem;

// Transcripts panel
window.downloadTranscript = downloadTranscript;
window.deleteTranscript = deleteTranscript;

// KG Panel & Project Management (prefixed with kg_ to avoid conflicts)
window.kg_handleDropdownSelect = handleDropdownSelect;
window.kg_deleteKGProject = deleteKGProject;
window.kg_loadKGProjects = loadKGProjects;
window.kg_selectKGProject = selectKGProject;

// KG Actions
window.kg_confirmKGDiscovery = confirmKGDiscovery;
window.createKGProject = createKGProject;
window.exportKGGraph = exportKGGraph;
window.batchExportKGProjects = batchExportKGProjects;

// KG Graph Controls (used in HTML onclick)
window.changeGraphLayout = changeGraphLayout;
window.fitGraphView = fitGraphView;
window.resetGraphView = resetGraphView;

// KG Graph Filtering
window.kg_filterByType = filterByType;
window.kg_clearTypeFilter = clearTypeFilter;

// KG Navigation & Search
window.kg_navigateToNode = navigateToNode;
window.kg_selectNodeById = selectNodeById;
window.kg_toggleTypeFilter = toggleTypeFilter;
window.kg_clearAllFilters = clearAllFilters;

// Jobs
window.cancelJob = cancelJob;
window.loadJobs = loadJobs;

// Audit
window.handleAuditCleanup = handleAuditCleanup;

// Chat (for job completion callback)
window.sendMessage = sendMessage;

// ============================================
// Keyboard Shortcuts
// ============================================

function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+Enter / Cmd+Enter - Send message
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            const chatForm = document.getElementById('chat-form');
            const input = document.getElementById('user-input');
            const message = input?.value?.trim();
            if (message && !state.isProcessing) {
                input.value = '';
                sendMessage(message);
            }
        }

        // Escape - Close modals/inspectors/dropdowns
        if (e.key === 'Escape') {
            // Close KG node inspector if open
            const inspector = document.getElementById('kg-node-inspector');
            if (inspector?.classList.contains('open')) {
                e.preventDefault();
                closeInspector();
                return;
            }

            // Close search results if open
            const searchResults = document.getElementById('kg-search-results');
            if (searchResults && !searchResults.classList.contains('hidden')) {
                e.preventDefault();
                hideSearchResults();
                const searchInput = document.getElementById('kg-graph-search');
                searchInput?.blur();
                return;
            }
        }
    });
}

// ============================================
// Event Listener Initialization
// ============================================

function initEventListeners() {
    // Sidebar panel toggles
    const historyToggle = document.getElementById('history-toggle');
    const transcriptsToggle = document.getElementById('transcripts-toggle');
    const jobsToggle = document.getElementById('jobs-toggle');
    const auditToggle = document.getElementById('audit-toggle');

    historyToggle?.addEventListener('click', toggleHistoryPanel);
    transcriptsToggle?.addEventListener('click', toggleTranscriptsPanel);
    jobsToggle?.addEventListener('click', toggleJobsPanel);
    auditToggle?.addEventListener('click', toggleAuditPanel);

    // KG Panel toggle
    state.kgToggle?.addEventListener('click', toggleKGPanel);

    // KG Advanced section toggle (More button)
    document.getElementById('kg-more-toggle')?.addEventListener('click', toggleKGAdvanced);

    // KG Dropdown
    state.kgDropdownToggle?.addEventListener('click', toggleKGDropdown);
    state.kgDropdownToggle?.addEventListener('keydown', handleDropdownKeydown);

    // Close KG dropdown on outside click
    document.addEventListener('click', (e) => {
        const dropdown = document.getElementById('kg-dropdown');
        if (dropdown && !dropdown.contains(e.target)) {
            const list = document.getElementById('kg-dropdown-list');
            const toggle = document.getElementById('kg-dropdown-toggle');
            list?.classList.add('hidden');
            list?.classList.remove('open');
            toggle?.setAttribute('aria-expanded', 'false');
        }
    });

    // KG View toggle buttons
    const listViewBtn = document.getElementById('kg-view-list-btn');
    const graphViewBtn = document.getElementById('kg-view-graph-btn');
    listViewBtn?.addEventListener('click', () => toggleKGView('list'));
    graphViewBtn?.addEventListener('click', () => toggleKGView('graph'));

    // KG Inspector close button
    const inspectorClose = document.getElementById('kg-inspector-close');
    inspectorClose?.addEventListener('click', closeInspector);

    // KG Create Project button
    const createProjectBtn = document.getElementById('kg-create-project');
    createProjectBtn?.addEventListener('click', createKGProject);

    // KG Export buttons
    const exportJsonBtn = document.getElementById('kg-export-json');
    const exportCsvBtn = document.getElementById('kg-export-csv');
    const exportGraphmlBtn = document.getElementById('kg-export-graphml');
    const batchExportBtn = document.getElementById('kg-batch-export');
    exportJsonBtn?.addEventListener('click', () => exportKGGraph('json'));
    exportCsvBtn?.addEventListener('click', () => exportKGGraph('csv'));
    exportGraphmlBtn?.addEventListener('click', () => exportKGGraph('graphml'));
    batchExportBtn?.addEventListener('click', batchExportKGProjects);

    // Chat form submission
    const chatForm = document.getElementById('chat-form');
    chatForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const input = document.getElementById('user-input');
        const message = input?.value?.trim();
        if (message) {
            input.value = '';
            await sendMessage(message);
        }
    });

    // Reset button
    const resetBtn = document.getElementById('reset-btn');
    resetBtn?.addEventListener('click', async () => {
        if (state.isProcessing) {
            if (!confirm('A message is being processed. Reset anyway?')) {
                return;
            }
            state.isProcessing = false;
        }

        if (confirm('Start a new transcription session? Current chat will be cleared.')) {
            stopStatusPolling();

            try {
                await fetch(`/chat/${state.sessionId}`, { method: 'DELETE' });
            } catch (e) {
                console.warn('Failed to close session on server:', e);
            }

            sessionStorage.removeItem('agent_session_id');
            window.location.reload();
        }
    });
}

// ============================================
// Sidebar Data Pre-loading
// ============================================

function initSidebarData() {
    // Pre-load sidebar data (collapsed state)
    loadHistory();
    loadTranscripts();
    loadKGProjects();
}

// ============================================
// Cleanup on Page Unload
// ============================================

window.addEventListener('beforeunload', () => {
    stopKGPolling();
    stopStatusPolling();
    stopAuditPolling();
    cleanupAllJobPollers();
});

// Pause/resume polling on visibility change
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopKGPolling();
        stopStatusPolling();
        stopAuditPolling();
    } else {
        startStatusPolling();
        if (state.kgCurrentProjectId) {
            startKGPolling();
        }
    }
});

// ============================================
// DOM Ready Initialization
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    // Reset KG state for clean UX on page load
    resetKGState();

    // Initialize DOM references for state
    initDOMReferences();

    // Initialize UI components
    initToastContainer();
    initTheme();
    initMobileNav();
    initSidebarCollapse();
    initHeaderDropdowns();
    initWorkspace();

    // Initialize file upload
    initFileUpload();

    // Initialize keyboard shortcuts
    initKeyboardShortcuts();

    // Initialize event listeners
    initEventListeners();

    // Initialize transcript search and viewer
    initTranscriptSearch();
    initTranscriptViewer();

    // Pre-load sidebar data
    initSidebarData();

    // Start status polling
    startStatusPolling();

    // Initialize graph search
    initGraphSearch();

    // Initialize batch export modal
    initBatchExportModal();

    // Initialize view toggle buttons to list view
    const listBtn = document.getElementById('kg-view-list-btn');
    const graphBtn = document.getElementById('kg-view-graph-btn');
    listBtn?.classList.add('active');
    graphBtn?.classList.remove('active');

    // Initialize audit panel
    initAuditPanel();

    // Initialize chat session (must run after DOM is ready)
    // This fetches session history and displays the initial greeting
    initSession();
});
