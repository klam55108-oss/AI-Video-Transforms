// KG Polling
// ============================================

import { state, getKGPollInterval } from '../core/state.js';
import { kgClient } from './api.js';
import { updateKGUI } from './ui.js';

async function refreshKGProjectStatus() {
    if (!state.kgCurrentProjectId) return;

    try {
        const project = await kgClient.getProject(state.kgCurrentProjectId);
        if (!project) {
            const { showToast } = await import('../ui/toast.js');
            showToast('Project not found', 'error');
            // Need to call selectKGProject from panel module (late binding)
            if (window.kg_selectKGProject) {
                window.kg_selectKGProject(null);
            }
            return;
        }

        state.kgCurrentProject = project;
        updateKGUI(project);
    } catch (e) {
        console.error('Failed to refresh KG project:', e);
    }
}

function startKGPolling() {
    stopKGPolling();
    state.kgPollInterval = setInterval(refreshKGProjectStatus, getKGPollInterval());
}

function stopKGPolling() {
    if (state.kgPollInterval) {
        clearInterval(state.kgPollInterval);
        state.kgPollInterval = null;
    }
}

export { startKGPolling, stopKGPolling, refreshKGProjectStatus };
