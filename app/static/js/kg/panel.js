// KG Panel Toggle & Project Management
// ============================================

import { state, KG_PROJECT_STORAGE_KEY } from '../core/state.js';
import { escapeHtml } from '../core/utils.js';
import { showToast } from '../ui/toast.js';
import { showKGPanel, hideKGPanel } from '../ui/workspace.js';
import { kgClient } from './api.js';
import { startKGPolling, stopKGPolling, refreshKGProjectStatus } from './polling.js';
import { updateKGUI } from './ui.js';

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
    clearDropdownFocus
};
