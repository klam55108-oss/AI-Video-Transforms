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
        showToast(`Graph exported as ${result.filename}`, 'success');
    } catch (e) {
        showToast(e.message, 'error', {
            hint: e.hint,
            code: e.code,
            detail: e.detail
        });
    }
}

export { createKGProject, confirmKGDiscovery, exportKGGraph };
