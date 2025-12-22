// Node Inspector Panel
// ============================================

import { state } from '../core/state.js';
import { showToast } from '../ui/toast.js';
import { fetchNodeEvidence, renderEvidenceSection } from './evidence.js';

// Circular dependency resolution - graph module will call setGraphModule
let graphModule = null;

function setGraphModule(module) {
    graphModule = module;
}

// escapeHtml utility (temporary - will import from utils once available)
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function selectNode(nodeData) {
    if (!state.kgCurrentProjectId || !nodeData) return;

    try {
        // Highlight selected node
        if (state.cytoscapeInstance) {
            state.cytoscapeInstance.nodes().removeClass('selected');
            state.cytoscapeInstance.nodes(`[id = "${nodeData.id}"]`).addClass('selected');
        }

        // Fetch neighbors and evidence in parallel
        const [neighborsResponse, evidence] = await Promise.all([
            fetch(`/kg/projects/${state.kgCurrentProjectId}/nodes/${nodeData.id}/neighbors`),
            fetchNodeEvidence(state.kgCurrentProjectId, nodeData.id)
        ]);

        if (!neighborsResponse.ok) {
            throw new Error('Failed to load node neighbors');
        }

        const neighbors = await neighborsResponse.json();
        updateInspector(nodeData, neighbors, evidence);
        showInspector();
    } catch (e) {
        console.error('Failed to select node:', e);
        showToast(e.message, 'error');
    }
}

function updateInspector(nodeData, neighbors, evidence = null) {
    const inspectorTitle = document.getElementById('kg-inspector-title');
    const inspectorContent = document.getElementById('kg-inspector-content');

    if (!inspectorTitle || !inspectorContent) return;

    // Update title
    inspectorTitle.textContent = nodeData.label;

    // Build inspector content - simple scrollable layout
    let html = `<div class="inspector-static-fields">`;

    // Type
    html += `
        <div class="inspector-field">
            <div class="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-1">Type</div>
            <div class="text-sm font-medium text-[var(--text-primary)]">${escapeHtml(nodeData.type)}</div>
        </div>
    `;

    // Description
    if (nodeData.description) {
        html += `
            <div class="inspector-field">
                <div class="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-1">Description</div>
                <p class="text-sm text-[var(--text-secondary)] leading-relaxed">${escapeHtml(nodeData.description)}</p>
            </div>
        `;
    }

    // Aliases
    if (nodeData.aliases && nodeData.aliases.length > 0) {
        html += `
            <div class="inspector-field">
                <div class="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-2">Aliases</div>
                <div class="flex flex-wrap gap-1.5">
                    ${nodeData.aliases.map(alias => `<span class="text-xs px-2 py-1 rounded-md bg-[var(--bg-tertiary)] text-[var(--text-secondary)]">${escapeHtml(alias)}</span>`).join('')}
                </div>
            </div>
        `;
    }

    // Evidence Section
    html += renderEvidenceSection(evidence);

    html += `</div>`; // Close static fields wrapper

    // Connections section with scrollable list
    if (neighbors && neighbors.length > 0) {
        html += `
            <div class="inspector-connections-section">
                <div class="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-2">Connections (${neighbors.length})</div>
                <div class="connection-list">
                    ${neighbors.map(neighbor => `
                        <button onclick="window.kg_selectNodeById('${neighbor.id}')"
                                class="connection-item">
                            <span class="connection-label">${escapeHtml(neighbor.label)}</span>
                            <span class="connection-type">${neighbor.entity_type}</span>
                        </button>
                    `).join('')}
                </div>
            </div>
        `;
    }

    inspectorContent.innerHTML = html;
}

function showInspector() {
    const inspector = document.getElementById('kg-node-inspector');
    inspector?.classList.add('open');
}

function closeInspector() {
    const inspector = document.getElementById('kg-node-inspector');
    inspector?.classList.remove('open');

    // Clear highlights using graph module
    if (graphModule && graphModule.clearHighlights) {
        graphModule.clearHighlights();
    }

    // Deselect nodes in graph
    if (state.cytoscapeInstance) {
        state.cytoscapeInstance.nodes().removeClass('selected');
    }

    state.selectedNodeData = null;
}

async function selectNodeById(nodeId) {
    if (!state.kgCurrentProjectId) return;

    try {
        // Find node in graph
        if (state.cytoscapeInstance) {
            const node = state.cytoscapeInstance.nodes(`[id = "${nodeId}"]`);
            if (node.length > 0) {
                // Center on node
                state.cytoscapeInstance.animate({
                    center: { eles: node },
                    zoom: 1.5
                }, {
                    duration: 300
                });

                // Trigger selection
                state.selectedNodeData = node.data();
                await selectNode(state.selectedNodeData);
            }
        }
    } catch (e) {
        console.error('Failed to select node by ID:', e);
    }
}

export { selectNode, updateInspector, showInspector, closeInspector, selectNodeById, setGraphModule };
