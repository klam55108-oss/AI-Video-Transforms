// KG UI Updates
// ============================================

import { state } from '../core/state.js';
import { kgClient } from './api.js';

function updateKGUI(project) {
    state.kgWorkflow?.classList.remove('hidden');

    updateKGStateBadge(project.state);
    updateKGActionButton(project);
    updateKGConfirmations(project.pending_confirmations);
    updateKGStats(project);

    const hasData = project.thing_count > 0 || project.connection_count > 0;

    // Show view toggle if we have data
    const viewToggle = document.getElementById('kg-view-toggle');
    viewToggle?.classList.toggle('hidden', !hasData);

    // Show "More" toggle when project has data (stats/export controlled by advanced panel)
    const moreToggle = document.getElementById('kg-more-toggle');
    if (moreToggle) {
        moreToggle.classList.toggle('hidden', !hasData);
    }

    if (state.kgPendingBadge) {
        if (project.pending_confirmations > 0) {
            state.kgPendingBadge.textContent = project.pending_confirmations;
            state.kgPendingBadge.classList.remove('hidden');
        } else {
            state.kgPendingBadge.classList.add('hidden');
        }
    }
}

function updateKGStateBadge(projectState) {
    if (!state.kgStateBadge || !state.kgStateLabel) return;

    state.kgStateBadge.classList.remove('hidden');

    const indicator = state.kgStateBadge.querySelector('.kg-state-indicator');
    if (indicator) {
        indicator.className = `kg-state-indicator ${projectState}`;
    }

    const labels = {
        'created': 'Created',
        'bootstrapping': 'Bootstrapping...',
        'active': 'Active',
        'stable': 'Stable'
    };

    state.kgStateLabel.textContent = labels[projectState] || projectState;
}

function updateKGActionButton(project) {
    if (!state.kgActionBtn) return;

    const icon = state.kgActionBtn.querySelector('i');
    const text = state.kgActionBtn.querySelector('span');

    switch (project.state) {
        case 'created':
            icon.className = 'ph-bold ph-lightning mr-1.5';
            text.textContent = 'Bootstrap from Video';
            state.kgActionBtn.disabled = false;
            state.kgProgress?.classList.add('hidden');
            break;
        case 'bootstrapping':
            icon.className = 'ph-bold ph-spinner mr-1.5 animate-spin';
            text.textContent = 'Bootstrapping...';
            state.kgActionBtn.disabled = true;
            state.kgProgress?.classList.remove('hidden');
            if (state.kgProgressText) state.kgProgressText.textContent = 'Analyzing domain...';
            break;
        case 'active':
        case 'stable':
            icon.className = 'ph-bold ph-magnifying-glass-plus mr-1.5';
            text.textContent = 'Extract from Video';
            state.kgActionBtn.disabled = false;
            state.kgProgress?.classList.add('hidden');
            break;
    }
}

async function updateKGConfirmations(pendingCount) {
    if (!state.kgConfirmations || !state.kgConfirmationsList) return;

    if (pendingCount === 0) {
        state.kgConfirmations.classList.add('hidden');
        return;
    }

    state.kgConfirmations.classList.remove('hidden');

    try {
        const discoveries = await kgClient.getConfirmations(state.kgCurrentProjectId);
        renderKGConfirmations(discoveries);
    } catch (e) {
        console.error('Failed to load confirmations:', e);
    }
}

function renderKGConfirmations(discoveries) {
    if (!state.kgConfirmationsList) return;

    state.kgConfirmationsList.innerHTML = discoveries.map(d => `
        <div class="kg-discovery-item" data-discovery-id="${escapeHtml(d.id)}">
            <span class="discovery-question">${DOMPurify.sanitize(d.user_question)}</span>
            <div class="discovery-actions">
                <button class="discovery-btn accept" onclick="window.kg_confirmKGDiscovery('${escapeHtml(d.id)}', true)">
                    <i class="ph-bold ph-check"></i> Yes
                </button>
                <button class="discovery-btn reject" onclick="window.kg_confirmKGDiscovery('${escapeHtml(d.id)}', false)">
                    <i class="ph-bold ph-x"></i> No
                </button>
            </div>
        </div>
    `).join('');
}

function updateKGStats(project) {
    if (!state.kgStats) return;

    const hasData = project.thing_count > 0 || project.connection_count > 0;
    state.kgStats.classList.toggle('hidden', !hasData);

    if (hasData) {
        document.getElementById('kg-stat-nodes').textContent = project.thing_count;
        document.getElementById('kg-stat-edges').textContent = project.connection_count;
    }
}

// escapeHtml is used inline - import from utils once available
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

export { updateKGUI, updateKGStateBadge, updateKGActionButton, updateKGConfirmations, renderKGConfirmations, updateKGStats };
