// KG Actions
// ============================================

import { state } from '../core/state.js';
import { showToast } from '../ui/toast.js';
import { kgClient } from './api.js';

async function createKGProject() {
    const name = prompt('Enter project name:');
    if (!name || !name.trim()) return;

    try {
        const project = await kgClient.createProject(name.trim());
        showToast(`Project "${project.name}" created`, 'success');

        // Late binding to panel module functions (avoid circular deps)
        if (window.kg_loadKGProjects) {
            await window.kg_loadKGProjects();
        }
        if (window.kg_selectKGProject) {
            await window.kg_selectKGProject(project.project_id);
        }
    } catch (e) {
        showToast(e.message, 'error', {
            hint: e.hint,
            code: e.code,
            detail: e.detail
        });
    }
}

async function confirmKGDiscovery(discoveryId, confirmed) {
    if (!state.kgCurrentProjectId) return;

    const item = document.querySelector(`[data-discovery-id="${discoveryId}"]`);
    const buttons = item?.querySelectorAll('button');
    buttons?.forEach(btn => btn.disabled = true);

    try {
        await kgClient.confirmDiscovery(state.kgCurrentProjectId, discoveryId, confirmed);

        item?.classList.add('fade-out');
        setTimeout(() => {
            item?.remove();
            const remaining = state.kgConfirmationsList?.children.length || 0;
            if (state.kgPendingBadge) {
                if (remaining > 0) {
                    state.kgPendingBadge.textContent = remaining;
                } else {
                    state.kgPendingBadge.classList.add('hidden');
                    state.kgConfirmations?.classList.add('hidden');
                }
            }
        }, 200);

        showToast(confirmed ? 'Discovery confirmed' : 'Discovery rejected', 'success');
    } catch (e) {
        showToast(e.message, 'error', {
            hint: e.hint,
            code: e.code,
            detail: e.detail
        });
        buttons?.forEach(btn => btn.disabled = false);
    }
}

async function exportKGGraph(format) {
    if (!state.kgCurrentProjectId) return;

    try {
        const result = await kgClient.exportGraph(state.kgCurrentProjectId, format);

        // Trigger browser download by navigating to the download endpoint
        triggerDownload(result.filename);
        showToast(`Downloading ${result.filename}`, 'success');
    } catch (e) {
        showToast(e.message, 'error', {
            hint: e.hint,
            code: e.code,
            detail: e.detail
        });
    }
}

/**
 * Trigger a browser download for an exported file.
 * Creates a temporary anchor element to initiate the download.
 */
function triggerDownload(filename) {
    const downloadUrl = `/kg/exports/${encodeURIComponent(filename)}`;

    // Create temporary anchor to trigger download
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

/**
 * Show the batch export modal for format selection.
 * Uses a proper modal dialog instead of browser prompt() for better UX.
 */
function showBatchExportModal() {
    const modal = document.getElementById('batch-export-modal');
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }
}

/**
 * Hide the batch export modal.
 */
function hideBatchExportModal() {
    const modal = document.getElementById('batch-export-modal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

/**
 * Initialize batch export modal event listeners.
 * Called from main.js during DOMContentLoaded.
 */
function initBatchExportModal() {
    const modal = document.getElementById('batch-export-modal');
    const cancelBtn = document.getElementById('batch-export-cancel');
    const formatBtns = document.querySelectorAll('.batch-export-option');

    // Cancel button
    cancelBtn?.addEventListener('click', hideBatchExportModal);

    // Click outside to close
    modal?.addEventListener('click', (e) => {
        if (e.target === modal) {
            hideBatchExportModal();
        }
    });

    // Escape key to close
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !modal?.classList.contains('hidden')) {
            hideBatchExportModal();
        }
    });

    // Format selection buttons
    formatBtns.forEach(btn => {
        btn.addEventListener('click', async () => {
            const format = btn.dataset.format;
            hideBatchExportModal();
            await executeBatchExport(format);
        });
    });
}

/**
 * Open batch export modal (entry point).
 * Shows modal for format selection, actual export happens on selection.
 */
async function batchExportKGProjects() {
    // Pre-check: verify there are projects to export
    const projects = await kgClient.listProjects();
    if (!projects?.projects?.length) {
        showToast('No projects to export', 'warning');
        return;
    }

    showBatchExportModal();
}

/**
 * Execute batch export with selected format.
 * Called after user selects format from modal.
 */
async function executeBatchExport(format) {
    try {
        const projects = await kgClient.listProjects();
        const projectIds = projects.projects.map(p => p.project_id);

        const result = await kgClient.batchExportProjects(projectIds, format);

        // Trigger browser download
        triggerDownload(result.filename);
        showToast(
            `Downloading ${result.project_count} projects as ${result.filename}`,
            'success'
        );
    } catch (e) {
        showToast(e.message, 'error', {
            hint: e.hint,
            code: e.code,
            detail: e.detail
        });
    }
}

export { createKGProject, confirmKGDiscovery, exportKGGraph, batchExportKGProjects, initBatchExportModal };
