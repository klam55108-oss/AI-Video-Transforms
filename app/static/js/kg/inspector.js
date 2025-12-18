// Node Inspector Panel
// ============================================

import { state } from '../core/state.js';
import { showToast } from '../ui/toast.js';

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

        // Fetch neighbors
        const response = await fetch(`/kg/projects/${state.kgCurrentProjectId}/nodes/${nodeData.id}/neighbors`);
        if (!response.ok) {
            throw new Error('Failed to load node neighbors');
        }

        const neighbors = await response.json();
        updateInspector(nodeData, neighbors);
        showInspector();
    } catch (e) {
        console.error('Failed to select node:', e);
        showToast(e.message, 'error');
    }
}

function updateInspector(nodeData, neighbors) {
    const inspectorTitle = document.getElementById('kg-inspector-title');
    const inspectorContent = document.getElementById('kg-inspector-content');

    if (!inspectorTitle || !inspectorContent) return;

    // Update title
    inspectorTitle.textContent = nodeData.label;

    // Build inspector content - using flex layout for proper space distribution
    // Static fields (Type, Description, Aliases) stay fixed, Connections fills remaining space
    let html = `
        <div class="inspector-static-fields flex-shrink-0">
            <div class="inspector-field">
                <span class="label text-[10px] font-semibold text-[var(--text-muted)] uppercase">Type</span>
                <span class="badge badge-${nodeData.type.toLowerCase()} mt-1 inline-block px-2 py-1 text-[10px] font-medium rounded">${nodeData.type}</span>
            </div>
    `;

    // Description
    if (nodeData.description) {
        html += `
            <div class="inspector-field mt-3">
                <span class="label text-[10px] font-semibold text-[var(--text-muted)] uppercase">Description</span>
                <p class="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">${escapeHtml(nodeData.description)}</p>
            </div>
        `;
    }

    // Aliases
    if (nodeData.aliases && nodeData.aliases.length > 0) {
        html += `
            <div class="inspector-field mt-3">
                <span class="label text-[10px] font-semibold text-[var(--text-muted)] uppercase">Aliases</span>
                <div class="flex flex-wrap gap-1 mt-1">
                    ${nodeData.aliases.map(alias => `<span class="text-[10px] px-2 py-0.5 rounded bg-[var(--bg-tertiary)] text-[var(--text-secondary)]">${escapeHtml(alias)}</span>`).join('')}
                </div>
            </div>
        `;
    }

    html += `</div>`; // Close static fields wrapper

    // Connections - this section grows to fill available space
    if (neighbors && neighbors.length > 0) {
        html += `
            <div class="inspector-connections-section flex-1 min-h-0 mt-3 flex flex-col">
                <span class="label text-[10px] font-semibold text-[var(--text-muted)] uppercase flex-shrink-0">Connections (${neighbors.length})</span>
                <div class="mt-2 space-y-1 flex-1 overflow-y-auto min-h-0 pr-1">
                    ${neighbors.map(neighbor => `
                        <button onclick="window.kg_selectNodeById('${neighbor.id}')"
                                class="w-full text-left text-xs px-2 py-1.5 rounded bg-[var(--bg-tertiary)] hover:bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">
                            <span class="font-medium">${escapeHtml(neighbor.label)}</span>
                            <span class="text-[10px] text-[var(--text-muted)] ml-1">(${neighbor.entity_type})</span>
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
