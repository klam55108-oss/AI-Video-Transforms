// KG Panel Toggle & Project Management
// ============================================

import { state, KG_PROJECT_STORAGE_KEY } from '../core/state.js';
import { escapeHtml } from '../core/utils.js';
import { showToast } from '../ui/toast.js';
import { showKGPanel, hideKGPanel } from '../ui/workspace.js';
import { kgClient, getPendingMerges, reviewMergeCandidate } from './api.js';
import { startKGPolling, stopKGPolling, refreshKGProjectStatus } from './polling.js';
import { updateKGUI } from './ui.js';
import { showMergeModal, getConfidenceLevel } from './merge-modal.js';
import { initKGGraph } from './graph.js';

function toggleKGPanel() {
    if (!state.kgContent || !state.kgCaret) return;

    const isOpen = state.kgContent.classList.contains('open');

    if (isOpen) {
        state.kgContent.classList.remove('open');
        state.kgCaret.classList.remove('open');
        stopKGPolling();
    } else {
        state.kgContent.classList.add('open');
        state.kgCaret.classList.add('open');
        loadKGProjects();
        if (state.kgCurrentProjectId) startKGPolling();
    }

    state.kgToggle?.setAttribute('aria-expanded', !isOpen);
}

/**
 * Toggle the KG advanced section (stats, exports)
 */
function toggleKGAdvanced() {
    const advanced = document.getElementById('kg-advanced');
    const caret = document.getElementById('kg-more-caret');
    const toggle = document.getElementById('kg-more-toggle');

    if (!advanced) return;

    const isOpen = advanced.classList.contains('open');

    if (isOpen) {
        advanced.classList.remove('open');
        caret?.classList.remove('open');
        toggle?.setAttribute('aria-expanded', 'false');
    } else {
        advanced.classList.add('open');
        caret?.classList.add('open');
        toggle?.setAttribute('aria-expanded', 'true');
    }
}

async function loadKGProjects() {
    // Show skeleton loader in dropdown
    if (state.kgDropdownList) {
        state.kgDropdownList.innerHTML = `
            <li class="kg-dropdown-option px-3 py-2">
                <div class="skeleton-loader">
                    <div class="skeleton-line h-3 w-3/4"></div>
                </div>
            </li>
        `;
    }

    try {
        const data = await kgClient.listProjects();
        renderKGProjectList(data.projects || []);
    } catch (e) {
        console.error('Failed to load KG projects:', e);
        state.kgEmptyState?.classList.remove('hidden');
        showToast(e.message, 'error', {
            hint: e.hint,
            code: e.code,
            detail: e.detail
        });
    }
}

async function deleteKGProject(projectId, projectName) {
    if (!confirm(`Delete project "${projectName}"? All data will be permanently removed.`)) {
        return;
    }

    try {
        await kgClient.deleteProject(projectId);

        // If we deleted the currently selected project, clear selection
        if (state.kgCurrentProjectId === projectId) {
            state.kgCurrentProjectId = null;
            state.kgCurrentProject = null;
            sessionStorage.removeItem(KG_PROJECT_STORAGE_KEY);
            state.kgDropdownLabel.textContent = '-- Select Project --';
            state.kgWorkflow?.classList.add('hidden');
            stopKGPolling();
        }

        // Refresh the project list
        loadKGProjects();
        showToast('Project deleted', 'success');
    } catch (e) {
        console.error('Delete project failed:', e);
        showToast(e.message, 'error', {
            hint: e.hint,
            code: e.code,
            detail: e.detail
        });
    }
}

function renderKGProjectList(projects) {
    if (!state.kgDropdownList || !state.kgDropdownLabel) return;

    // Clear existing options
    state.kgDropdownList.innerHTML = '';

    if (projects.length === 0) {
        state.kgEmptyState?.classList.remove('hidden');
        state.kgWorkflow?.classList.add('hidden');

        // Add empty placeholder option
        const emptyOption = document.createElement('li');
        emptyOption.className = 'kg-dropdown-option';
        emptyOption.setAttribute('data-empty', 'true');
        emptyOption.textContent = 'No projects yet';
        state.kgDropdownList.appendChild(emptyOption);

        state.kgDropdownLabel.textContent = '-- Select Project --';
        return;
    }

    state.kgEmptyState?.classList.add('hidden');

    // Add project options directly (no placeholder needed - toggle button shows current selection)
    // Add project options (styled like History items)
    projects.forEach((p, index) => {
        const option = document.createElement('li');
        option.className = 'kg-dropdown-option group';
        option.setAttribute('role', 'option');
        option.setAttribute('data-value', p.project_id);
        option.setAttribute('aria-selected', p.project_id === state.kgCurrentProjectId ? 'true' : 'false');
        option.innerHTML = `
            <div class="option-content" onclick="window.kg_handleDropdownSelect('${p.project_id}', '${escapeHtml(p.name).replace(/'/g, "\\'")}')">
                <span class="option-name truncate">${escapeHtml(p.name)}</span>
                <span class="option-state">${p.state}</span>
            </div>
            <button class="kg-delete-btn opacity-0 group-hover:opacity-100 transition-opacity"
                    onclick="event.stopPropagation(); window.kg_deleteKGProject('${p.project_id}', '${escapeHtml(p.name).replace(/'/g, "\\'")}')"
                    title="Delete project">
                <i class="ph-bold ph-trash text-xs"></i>
            </button>
        `;
        state.kgDropdownList.appendChild(option);
    });

    // Update label if current project is selected
    if (state.kgCurrentProjectId) {
        const currentProject = projects.find(p => p.project_id === state.kgCurrentProjectId);
        if (currentProject) {
            state.kgDropdownLabel.textContent = currentProject.name;
        }
        refreshKGProjectStatus();
    }
}

function handleDropdownSelect(projectId, projectName) {
    state.kgDropdownLabel.textContent = projectName || '-- Select Project --';
    closeKGDropdown();
    selectKGProject(projectId);

    // Update aria-selected on all options
    const options = state.kgDropdownList?.querySelectorAll('.kg-dropdown-option[role="option"]');
    options?.forEach(opt => {
        opt.setAttribute('aria-selected', opt.getAttribute('data-value') === projectId ? 'true' : 'false');
    });
}

function toggleKGDropdown() {
    const isOpen = state.kgDropdownToggle?.getAttribute('aria-expanded') === 'true';
    if (isOpen) {
        closeKGDropdown();
    } else {
        openKGDropdown();
    }
}

function openKGDropdown() {
    state.kgDropdownToggle?.setAttribute('aria-expanded', 'true');
    state.kgDropdownList?.classList.remove('hidden');
    state.kgDropdownList?.classList.add('open');
    state.kgDropdownFocusedIndex = -1;

    // Focus on currently selected option
    const selectedOption = state.kgDropdownList?.querySelector('[aria-selected="true"]');
    if (selectedOption) {
        const options = Array.from(state.kgDropdownList?.querySelectorAll('.kg-dropdown-option[role="option"]') || []);
        state.kgDropdownFocusedIndex = options.indexOf(selectedOption);
        updateDropdownFocus();
    }
}

function closeKGDropdown() {
    state.kgDropdownToggle?.setAttribute('aria-expanded', 'false');
    state.kgDropdownList?.classList.remove('open');
    state.kgDropdownList?.classList.add('hidden');
    state.kgDropdownFocusedIndex = -1;
    clearDropdownFocus();
}

function updateDropdownFocus() {
    const options = state.kgDropdownList?.querySelectorAll('.kg-dropdown-option[role="option"]');
    options?.forEach((opt, i) => {
        if (i === state.kgDropdownFocusedIndex) {
            opt.classList.add('focused');
            opt.scrollIntoView({ block: 'nearest' });
        } else {
            opt.classList.remove('focused');
        }
    });
}

function clearDropdownFocus() {
    const options = state.kgDropdownList?.querySelectorAll('.kg-dropdown-option');
    options?.forEach(opt => opt.classList.remove('focused'));
}

function handleDropdownKeydown(e) {
    const options = Array.from(state.kgDropdownList?.querySelectorAll('.kg-dropdown-option[role="option"]') || []);
    const isOpen = state.kgDropdownToggle?.getAttribute('aria-expanded') === 'true';

    switch (e.key) {
        case 'Enter':
        case ' ':
            e.preventDefault();
            if (!isOpen) {
                openKGDropdown();
            } else if (state.kgDropdownFocusedIndex >= 0 && options[state.kgDropdownFocusedIndex]) {
                const option = options[state.kgDropdownFocusedIndex];
                const value = option.getAttribute('data-value');
                const name = option.querySelector('span')?.textContent || option.textContent;
                handleDropdownSelect(value, name);
            }
            break;

        case 'Escape':
            e.preventDefault();
            closeKGDropdown();
            state.kgDropdownToggle?.focus();
            break;

        case 'ArrowDown':
            e.preventDefault();
            if (!isOpen) {
                openKGDropdown();
            } else {
                state.kgDropdownFocusedIndex = Math.min(state.kgDropdownFocusedIndex + 1, options.length - 1);
                updateDropdownFocus();
            }
            break;

        case 'ArrowUp':
            e.preventDefault();
            if (isOpen) {
                state.kgDropdownFocusedIndex = Math.max(state.kgDropdownFocusedIndex - 1, 0);
                updateDropdownFocus();
            }
            break;

        case 'Home':
            e.preventDefault();
            if (isOpen) {
                state.kgDropdownFocusedIndex = 0;
                updateDropdownFocus();
            }
            break;

        case 'End':
            e.preventDefault();
            if (isOpen) {
                state.kgDropdownFocusedIndex = options.length - 1;
                updateDropdownFocus();
            }
            break;

        case 'Tab':
            if (isOpen) {
                closeKGDropdown();
            }
            break;
    }
}

async function selectKGProject(projectId) {
    if (!projectId) {
        state.kgCurrentProjectId = null;
        state.kgCurrentProject = null;
        sessionStorage.removeItem(KG_PROJECT_STORAGE_KEY);
        state.kgWorkflow?.classList.add('hidden');
        state.kgStateBadge?.classList.add('hidden');
        state.kgConfirmations?.classList.add('hidden');
        state.kgStats?.classList.add('hidden');
        state.kgExport?.classList.add('hidden');
        stopKGPolling();
        hideKGPanel();
        return;
    }

    state.kgCurrentProjectId = projectId;
    sessionStorage.setItem(KG_PROJECT_STORAGE_KEY, projectId);
    await refreshKGProjectStatus();
    startKGPolling();

    // Only show KG panel if currently in graph view mode
    // Otherwise, wait for user to click "Graph" button
    if (state.kgCurrentView === 'graph') {
        showKGPanel();
    }
}

// ============================================
// Pending Merge Reviews Section
// ============================================

/**
 * Load and display pending merge candidates for the current project.
 */
async function loadPendingMerges() {
    if (!state.kgCurrentProjectId) return;

    const container = document.getElementById('kg-pending-merges');
    if (!container) return;

    try {
        const response = await getPendingMerges(state.kgCurrentProjectId);
        const candidates = (response.candidates || []).filter(c => c.status === 'pending');

        if (candidates.length === 0) {
            container.classList.add('hidden');
            updatePendingMergesBadge(0);
            return;
        }

        container.classList.remove('hidden');
        renderPendingMergesSection(candidates);
        updatePendingMergesBadge(candidates.length);
    } catch (e) {
        console.error('Failed to load pending merges:', e);
        container.classList.add('hidden');
        updatePendingMergesBadge(0);
    }
}

/**
 * Render the pending merges section in the KG panel.
 * @param {Array} candidates - List of pending merge candidates
 */
function renderPendingMergesSection(candidates) {
    const container = document.getElementById('kg-pending-merges');
    if (!container) return;

    const itemsHTML = candidates.map(candidate => {
        const confidenceLevel = getConfidenceLevel(candidate.confidence);
        const confidencePercent = Math.round(candidate.confidence * 100);

        // Get node labels from cytoscape if available
        let labelA = candidate.node_a_id;
        let labelB = candidate.node_b_id;

        if (state.cytoscapeInstance) {
            const nodeA = state.cytoscapeInstance.nodes(`[id = "${candidate.node_a_id}"]`);
            const nodeB = state.cytoscapeInstance.nodes(`[id = "${candidate.node_b_id}"]`);
            if (nodeA.length > 0) labelA = nodeA.data('label') || labelA;
            if (nodeB.length > 0) labelB = nodeB.data('label') || labelB;
        }

        return `
            <div class="pending-merge-item" data-candidate-id="${escapeHtml(candidate.id)}">
                <div class="pending-merge-labels">
                    <span class="pending-merge-node" title="${escapeHtml(labelA)}">${escapeHtml(truncateLabel(labelA, 15))}</span>
                    <i class="ph-regular ph-arrows-left-right text-[var(--text-muted)]"></i>
                    <span class="pending-merge-node" title="${escapeHtml(labelB)}">${escapeHtml(truncateLabel(labelB, 15))}</span>
                    <span class="confidence-badge confidence-${confidenceLevel}">${confidencePercent}%</span>
                </div>
                <div class="pending-merge-actions">
                    <button class="btn-approve"
                            onclick="window.kg_approveMerge('${escapeHtml(candidate.id)}')"
                            title="Approve merge">
                        <i class="ph-bold ph-check"></i>
                    </button>
                    <button class="btn-reject"
                            onclick="window.kg_rejectMerge('${escapeHtml(candidate.id)}')"
                            title="Reject merge">
                        <i class="ph-bold ph-x"></i>
                    </button>
                    <button class="btn-view-merge"
                            onclick="window.kg_viewMergeCandidate('${escapeHtml(candidate.id)}', '${escapeHtml(candidate.node_a_id)}', '${escapeHtml(candidate.node_b_id)}', ${candidate.confidence})"
                            title="View details">
                        <i class="ph-regular ph-eye"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = `
        <div class="pending-merges-section">
            <div class="pending-merges-header">
                <i class="ph-regular ph-git-merge"></i>
                <span>Pending Reviews</span>
                <span class="pending-merges-count">${candidates.length}</span>
            </div>
            <div class="pending-merges-list">
                ${itemsHTML}
            </div>
        </div>
    `;
}

/**
 * Update the pending merges badge count in the panel header.
 * @param {number} count - Number of pending merge candidates
 */
function updatePendingMergesBadge(count) {
    const badge = document.getElementById('kg-merges-badge');
    if (badge) {
        if (count > 0) {
            badge.textContent = count;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }
}

/**
 * Truncate a label for display.
 * @param {string} label
 * @param {number} maxLen
 * @returns {string}
 */
function truncateLabel(label, maxLen = 20) {
    if (!label) return '';
    return label.length > maxLen ? label.slice(0, maxLen - 1) + '...' : label;
}

/**
 * Approve a merge candidate.
 * @param {string} candidateId
 */
async function approveMergeCandidate(candidateId) {
    if (!state.kgCurrentProjectId) return;

    try {
        await reviewMergeCandidate(state.kgCurrentProjectId, candidateId, true);
        showToast('Merge approved', 'success');

        // Refresh the pending merges list and graph
        await loadPendingMerges();
        if (state.kgCurrentProjectId && state.kgCurrentView === 'graph') {
            await initKGGraph(state.kgCurrentProjectId);
        }

        // Dispatch event for other components
        window.dispatchEvent(new CustomEvent('kg-merge-reviewed', {
            detail: { projectId: state.kgCurrentProjectId, candidateId, approved: true }
        }));
    } catch (e) {
        console.error('Failed to approve merge:', e);
        showToast(e.message || 'Failed to approve merge', 'error');
    }
}

/**
 * Reject a merge candidate.
 * @param {string} candidateId
 */
async function rejectMergeCandidate(candidateId) {
    if (!state.kgCurrentProjectId) return;

    try {
        await reviewMergeCandidate(state.kgCurrentProjectId, candidateId, false);
        showToast('Merge rejected', 'info');

        // Refresh the pending merges list
        await loadPendingMerges();

        // Dispatch event for other components
        window.dispatchEvent(new CustomEvent('kg-merge-reviewed', {
            detail: { projectId: state.kgCurrentProjectId, candidateId, approved: false }
        }));
    } catch (e) {
        console.error('Failed to reject merge:', e);
        showToast(e.message || 'Failed to reject merge', 'error');
    }
}

/**
 * View merge candidate details in a modal.
 * @param {string} candidateId
 * @param {string} nodeAId
 * @param {string} nodeBId
 * @param {number} confidence
 */
async function viewMergeCandidate(candidateId, nodeAId, nodeBId, confidence) {
    if (!state.kgCurrentProjectId) return;

    // Get node data from cytoscape
    let nodeA = { id: nodeAId, label: nodeAId };
    let nodeB = { id: nodeBId, label: nodeBId };

    if (state.cytoscapeInstance) {
        const cyNodeA = state.cytoscapeInstance.nodes(`[id = "${nodeAId}"]`);
        const cyNodeB = state.cytoscapeInstance.nodes(`[id = "${nodeBId}"]`);

        if (cyNodeA.length > 0) nodeA = cyNodeA.data();
        if (cyNodeB.length > 0) nodeB = cyNodeB.data();
    }

    // Get signals from the candidate
    try {
        const response = await getPendingMerges(state.kgCurrentProjectId);
        const candidate = (response.candidates || []).find(c => c.id === candidateId);
        const signals = candidate?.signals || {};

        showMergeModal(state.kgCurrentProjectId, nodeA, nodeB, confidence, signals);
    } catch (e) {
        console.error('Failed to view merge candidate:', e);
        showMergeModal(state.kgCurrentProjectId, nodeA, nodeB, confidence, {});
    }
}

// Window exports for onclick handlers
window.kg_approveMerge = approveMergeCandidate;
window.kg_rejectMerge = rejectMergeCandidate;
window.kg_viewMergeCandidate = viewMergeCandidate;

// Listen for merge completion events to refresh pending list
window.addEventListener('kg-merge-completed', () => {
    loadPendingMerges();
});

export {
    toggleKGPanel,
    toggleKGAdvanced,
    loadKGProjects,
    renderKGProjectList,
    selectKGProject,
    toggleKGDropdown,
    openKGDropdown,
    closeKGDropdown,
    handleDropdownSelect,
    handleDropdownKeydown,
    deleteKGProject,
    updateDropdownFocus,
    clearDropdownFocus,
    loadPendingMerges,
    renderPendingMergesSection,
    updatePendingMergesBadge,
    approveMergeCandidate,
    rejectMergeCandidate,
    viewMergeCandidate
};
