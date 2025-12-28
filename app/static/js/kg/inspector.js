// Node Inspector Panel
// ============================================

import { state } from '../core/state.js';
import { escapeHtml } from '../core/utils.js';
import { showToast } from '../ui/toast.js';
import { fetchNodeEvidence, renderEvidenceSection } from './evidence.js';
import { getPendingMerges } from './api.js';
import { showMergeModal, getConfidenceLevel } from './merge-modal.js';

// Circular dependency resolution - graph module will call setGraphModule
let graphModule = null;

function setGraphModule(module) {
    graphModule = module;
}

async function selectNode(nodeData) {
    if (!state.kgCurrentProjectId || !nodeData) return;

    try {
        // Highlight selected node
        if (state.cytoscapeInstance) {
            state.cytoscapeInstance.nodes().removeClass('selected');
            state.cytoscapeInstance.nodes(`[id = "${nodeData.id}"]`).addClass('selected');
        }

        // Fetch neighbors, evidence, and duplicates in parallel
        const [neighborsResponse, evidence, duplicates] = await Promise.all([
            fetch(`/kg/projects/${state.kgCurrentProjectId}/nodes/${nodeData.id}/neighbors`),
            fetchNodeEvidence(state.kgCurrentProjectId, nodeData.id),
            loadPotentialDuplicates(nodeData.id, state.kgCurrentProjectId)
        ]);

        if (!neighborsResponse.ok) {
            throw new Error('Failed to load node neighbors');
        }

        const neighbors = await neighborsResponse.json();
        updateInspector(nodeData, neighbors, evidence, duplicates);
        showInspector();
    } catch (e) {
        console.error('Failed to select node:', e);
        showToast(e.message, 'error');
    }
}

function updateInspector(nodeData, neighbors, evidence = null, duplicates = []) {
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

    // Duplicates Section
    html += renderDuplicatesSection(duplicates, nodeData);

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

// ============================================
// Duplicates Section Functions
// ============================================

/**
 * Load potential duplicate candidates involving a specific node.
 * @param {string} nodeId - The node ID to check for duplicates
 * @param {string} projectId - The project ID
 * @returns {Promise<Array>} Filtered list of candidates involving this node
 */
async function loadPotentialDuplicates(nodeId, projectId) {
    try {
        const response = await getPendingMerges(projectId);
        const candidates = response.candidates || [];

        // Filter candidates that involve this node
        return candidates.filter(candidate =>
            (candidate.node_a_id === nodeId || candidate.node_b_id === nodeId) &&
            candidate.status === 'pending'
        );
    } catch (e) {
        console.error('Failed to load duplicates:', e);
        return [];
    }
}

/**
 * Render the duplicates section for the inspector.
 * @param {Array} candidates - Filtered merge candidates
 * @param {Object} selectedNodeData - The currently selected node
 * @returns {string} HTML string
 */
function renderDuplicatesSection(candidates, selectedNodeData) {
    if (!candidates || candidates.length === 0) {
        return '';
    }

    // Get node data from cytoscape for the other nodes
    const duplicateItems = candidates.map(candidate => {
        // Determine which node is the "other" node
        const otherNodeId = candidate.node_a_id === selectedNodeData.id
            ? candidate.node_b_id
            : candidate.node_a_id;

        // Try to get node data from cytoscape instance
        let otherNodeData = { id: otherNodeId, label: otherNodeId };
        if (state.cytoscapeInstance) {
            const cyNode = state.cytoscapeInstance.nodes(`[id = "${otherNodeId}"]`);
            if (cyNode.length > 0) {
                otherNodeData = cyNode.data();
            }
        }

        const confidenceLevel = getConfidenceLevel(candidate.confidence);
        const confidencePercent = Math.round(candidate.confidence * 100);

        return `
            <div class="duplicate-item" data-candidate-id="${escapeHtml(candidate.id)}">
                <div class="duplicate-info">
                    <button class="duplicate-label" onclick="window.kg_selectNodeById('${escapeHtml(otherNodeId)}')"
                            title="View ${escapeHtml(otherNodeData.label || otherNodeId)}">
                        ${escapeHtml(otherNodeData.label || otherNodeId)}
                    </button>
                    <span class="confidence-badge confidence-${confidenceLevel}"
                          title="${formatSignalTooltip(candidate.signals)}">
                        ${confidencePercent}%
                    </span>
                </div>
                <button class="duplicate-merge-btn"
                        onclick="window.kg_openMergeModal('${escapeHtml(candidate.id)}', '${escapeHtml(selectedNodeData.id)}', '${escapeHtml(otherNodeId)}', ${candidate.confidence})"
                        title="Merge entities">
                    <i class="ph-bold ph-git-merge"></i>
                </button>
            </div>
        `;
    }).join('');

    return `
        <div class="duplicates-section">
            <details open>
                <summary class="duplicates-header">
                    <i class="ph-regular ph-copy-simple"></i>
                    <span>Potential Duplicates</span>
                    <span class="duplicates-count">${candidates.length}</span>
                </summary>
                <div class="duplicates-list">
                    ${duplicateItems}
                </div>
            </details>
        </div>
    `;
}

/**
 * Format signals for tooltip display.
 * @param {Record<string, number>} signals
 * @returns {string}
 */
function formatSignalTooltip(signals) {
    if (!signals || Object.keys(signals).length === 0) {
        return 'Confidence score';
    }

    const signalLabels = {
        fuzzy_label: 'Label',
        alias_overlap: 'Aliases',
        type_match: 'Type',
        shared_connections: 'Connections',
        description_similarity: 'Description'
    };

    return Object.entries(signals)
        .map(([key, value]) => {
            const label = signalLabels[key] || key;
            return `${label}: ${Math.round(value * 100)}%`;
        })
        .join('\n');
}

/**
 * Open the merge modal for a specific candidate.
 * Called from onclick handler.
 */
async function openMergeModalFromInspector(candidateId, nodeAId, nodeBId, confidence) {
    if (!state.kgCurrentProjectId) return;

    // Get node data from cytoscape
    let nodeA = { id: nodeAId, label: nodeAId };
    let nodeB = { id: nodeBId, label: nodeBId };

    if (state.cytoscapeInstance) {
        const cyNodeA = state.cytoscapeInstance.nodes(`[id = "${nodeAId}"]`);
        const cyNodeB = state.cytoscapeInstance.nodes(`[id = "${nodeBId}"]`);

        if (cyNodeA.length > 0) {
            nodeA = cyNodeA.data();
        }
        if (cyNodeB.length > 0) {
            nodeB = cyNodeB.data();
        }
    }

    // Get signals from the pending merges
    try {
        const response = await getPendingMerges(state.kgCurrentProjectId);
        const candidate = (response.candidates || []).find(c => c.id === candidateId);
        const signals = candidate?.signals || {};

        showMergeModal(state.kgCurrentProjectId, nodeA, nodeB, confidence, signals);
    } catch (e) {
        console.error('Failed to open merge modal:', e);
        // Fallback: open modal without signals
        showMergeModal(state.kgCurrentProjectId, nodeA, nodeB, confidence, {});
    }
}

// Window exports for onclick handlers
window.kg_openMergeModal = openMergeModalFromInspector;

export {
    selectNode,
    updateInspector,
    showInspector,
    closeInspector,
    selectNodeById,
    setGraphModule,
    loadPotentialDuplicates,
    renderDuplicatesSection
};
