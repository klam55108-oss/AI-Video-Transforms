// KG Graph Visualization
// ============================================

import { state } from '../core/state.js';
import { showToast } from '../ui/toast.js';

// Circular dependency resolution - inspector module will call setInspectorModule
let inspectorModule = null;

function setInspectorModule(module) {
    inspectorModule = module;
}

// escapeHtml utility (temporary - will import from utils once available)
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// KG View Toggle (List/Graph)
// ============================================

function toggleKGView(view) {
    if (view === state.kgCurrentView) return;

    state.kgCurrentView = view;
    localStorage.setItem(state.KG_VIEW_STORAGE_KEY, view);

    const chatContainer = document.getElementById('chat-messages');
    const graphView = document.getElementById('kg-graph-view');
    const listViewToggle = document.getElementById('kg-view-list-btn');
    const graphViewToggle = document.getElementById('kg-view-graph-btn');
    const headerControls = document.getElementById('graph-header-controls');
    const headerTitle = document.getElementById('header-title');
    const headerIcon = document.getElementById('header-icon');

    if (view === 'graph') {
        // Hide chat, show graph
        chatContainer?.classList.add('hidden');
        graphView?.classList.remove('hidden');

        // Update button states
        listViewToggle?.classList.remove('active');
        graphViewToggle?.classList.add('active');

        // Show header controls
        headerControls?.classList.remove('hidden');
        headerControls?.classList.add('flex');

        // Update header title
        if (headerTitle) headerTitle.textContent = 'Knowledge Graph';
        if (headerIcon) {
            headerIcon.className = 'ph-regular ph-graph text-[var(--text-tertiary)]';
        }

        // Initialize graph if project selected
        if (state.kgCurrentProjectId) {
            initKGGraph(state.kgCurrentProjectId);
        }
    } else {
        // Show chat, hide graph
        chatContainer?.classList.remove('hidden');
        graphView?.classList.add('hidden');

        // Update button states
        listViewToggle?.classList.add('active');
        graphViewToggle?.classList.remove('active');

        // Hide header controls
        headerControls?.classList.add('hidden');
        headerControls?.classList.remove('flex');

        // Restore header title
        if (headerTitle) headerTitle.textContent = 'Transcription & Analysis';
        if (headerIcon) {
            headerIcon.className = 'ph-regular ph-hash text-[var(--text-tertiary)]';
        }

        // Close inspector when switching to list view
        if (inspectorModule && inspectorModule.closeInspector) {
            inspectorModule.closeInspector();
        }
    }
}

// KG Graph Visualization
// ============================================

async function initKGGraph(projectId) {
    if (!window.cytoscape) {
        showToast('Cytoscape library not loaded', 'error');
        return;
    }

    try {
        const response = await fetch(`/kg/projects/${projectId}/graph-data`);
        if (!response.ok) {
            if (response.status === 404) {
                renderEmptyGraph();
                return;
            }
            throw new Error('Failed to load graph data');
        }

        const graphData = await response.json();
        renderGraph(graphData);
        updateGraphStats(graphData);
    } catch (e) {
        console.error('Failed to initialize graph:', e);
        showToast(e.message, 'error');
        renderEmptyGraph();
    }
}

function renderGraph(data) {
    const container = document.getElementById('kg-graph-container');
    if (!container) return;

    // Clear existing instance and observer
    if (state.graphResizeObserver) {
        state.graphResizeObserver.disconnect();
        state.graphResizeObserver = null;
    }
    if (state.cytoscapeInstance) {
        state.cytoscapeInstance.destroy();
        state.cytoscapeInstance = null;
    }

    // Calculate node degrees for size scaling
    const nodeDegrees = {};
    data.nodes.forEach(n => { nodeDegrees[n.data.id] = 0; });
    data.edges.forEach(e => {
        nodeDegrees[e.data.source] = (nodeDegrees[e.data.source] || 0) + 1;
        nodeDegrees[e.data.target] = (nodeDegrees[e.data.target] || 0) + 1;
    });

    // Find max degree for scaling
    const maxDegree = Math.max(...Object.values(nodeDegrees), 1);
    const minNodeSize = 30;
    const maxNodeSize = 70;

    // Add degree to node data
    data.nodes.forEach(n => {
        n.data.degree = nodeDegrees[n.data.id] || 0;
    });

    // Entity type colors (vibrant, accessible palette)
    const typeColors = {
        'Person': '#3b82f6',
        'Character': '#3b82f6',
        'Organization': '#10b981',
        'Group': '#10b981',
        'Event': '#f59e0b',
        'Location': '#ef4444',
        'Place': '#ef4444',
        'Concept': '#8b5cf6',
        'Theme': '#8b5cf6',
        'Technology': '#06b6d4',
        'Product': '#ec4899',
        'Object': '#ec4899',
        'default': '#64748b'
    };

    // Helper to get color for a type
    const getTypeColor = (type) => typeColors[type] || typeColors.default;

    // Helper to calculate node size based on degree
    const getNodeSize = (degree) => {
        const normalized = degree / maxDegree;
        return minNodeSize + (maxNodeSize - minNodeSize) * Math.sqrt(normalized);
    };

    // Helper to truncate label
    const truncateLabel = (label, maxLen = 12) => {
        if (!label) return '';
        return label.length > maxLen ? label.slice(0, maxLen - 1) + '…' : label;
    };

    // Initialize Cytoscape
    state.cytoscapeInstance = cytoscape({
        container: container,
        elements: [...data.nodes, ...data.edges],
        style: [
            // Base node style
            {
                selector: 'node',
                style: {
                    'background-color': (ele) => getTypeColor(ele.data('type')),
                    'background-opacity': 0.9,
                    'label': (ele) => truncateLabel(ele.data('label')),
                    'width': (ele) => getNodeSize(ele.data('degree')),
                    'height': (ele) => getNodeSize(ele.data('degree')),
                    'font-size': (ele) => Math.max(10, Math.min(14, 10 + ele.data('degree') * 0.3)),
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'color': '#ffffff',
                    'text-outline-width': 2,
                    'text-outline-color': (ele) => getTypeColor(ele.data('type')),
                    'text-outline-opacity': 1,
                    'overlay-padding': 6,
                    'border-width': 2,
                    'border-color': (ele) => getTypeColor(ele.data('type')),
                    'border-opacity': 0.3,
                    'transition-property': 'background-opacity, border-width, border-opacity, width, height',
                    'transition-duration': '0.2s',
                    'transition-timing-function': 'ease-out'
                }
            },
            // Node hover state
            {
                selector: 'node:active',
                style: {
                    'overlay-opacity': 0.1
                }
            },
            // Node selected state
            {
                selector: 'node:selected',
                style: {
                    'border-width': 4,
                    'border-color': '#ffffff',
                    'border-opacity': 1,
                    'background-opacity': 1
                }
            },
            // Highlighted node (neighbor of selected)
            {
                selector: 'node.highlighted',
                style: {
                    'border-width': 3,
                    'border-color': '#ffffff',
                    'border-opacity': 0.7,
                    'background-opacity': 1
                }
            },
            // Dimmed node (not connected to selected)
            {
                selector: 'node.dimmed',
                style: {
                    'background-opacity': 0.25,
                    'text-opacity': 0.4,
                    'border-opacity': 0.1
                }
            },
            // Base edge style
            {
                selector: 'edge',
                style: {
                    'width': 2,
                    'line-color': '#64748b',
                    'line-opacity': 0.4,
                    'target-arrow-color': '#64748b',
                    'target-arrow-shape': 'triangle',
                    'arrow-scale': 0.8,
                    'curve-style': 'bezier',
                    'control-point-step-size': 40,
                    'transition-property': 'line-opacity, width, line-color',
                    'transition-duration': '0.2s'
                }
            },
            // Edge hover - show label with proper colors (NO CSS VARIABLES - Cytoscape uses Canvas!)
            {
                selector: 'edge:active',
                style: {
                    'label': 'data(label)',
                    'font-size': 11,
                    'font-weight': 'bold',
                    'text-rotation': 'autorotate',
                    'text-margin-y': -10,
                    'color': '#ffffff',
                    'text-outline-color': '#1e293b',
                    'text-outline-width': 2,
                    'text-background-color': '#1e293b',
                    'text-background-opacity': 0.95,
                    'text-background-padding': 6,
                    'text-background-shape': 'roundrectangle',
                    'line-opacity': 1,
                    'width': 3,
                    'z-index': 999
                }
            },
            // Highlighted edge (connected to selected node) - FIXED: Use hex colors
            {
                selector: 'edge.highlighted',
                style: {
                    'line-color': '#f59e0b',
                    'target-arrow-color': '#f59e0b',
                    'line-opacity': 1,
                    'width': 3,
                    'label': 'data(label)',
                    'font-size': 11,
                    'font-weight': 'bold',
                    'text-rotation': 'autorotate',
                    'text-margin-y': -10,
                    'color': '#ffffff',
                    'text-outline-color': '#78350f',
                    'text-outline-width': 2,
                    'text-background-color': '#78350f',
                    'text-background-opacity': 0.95,
                    'text-background-padding': 6,
                    'text-background-shape': 'roundrectangle',
                    'z-index': 999
                }
            },
            // Dimmed edge
            {
                selector: 'edge.dimmed',
                style: {
                    'line-opacity': 0.1,
                    'label': ''
                }
            }
        ],
        layout: {
            name: 'cose',
            animate: true,
            animationDuration: 800,
            animationEasing: 'ease-out-cubic',
            nodeRepulsion: function(node) {
                // Higher repulsion for high-degree nodes
                return 10000 + (node.data('degree') || 0) * 500;
            },
            idealEdgeLength: 120,
            edgeElasticity: 80,
            nestingFactor: 1.2,
            gravity: 0.8,
            numIter: 1500,
            initialTemp: 250,
            coolingFactor: 0.95,
            minTemp: 1.0,
            fit: true,
            padding: 40
        },
        // Performance options
        minZoom: 0.2,
        maxZoom: 3,
        wheelSensitivity: 0.3
    });

    // Node hover effect - highlight neighbors
    state.cytoscapeInstance.on('mouseover', 'node', (evt) => {
        const node = evt.target;
        highlightNodeNeighborhood(node);
    });

    state.cytoscapeInstance.on('mouseout', 'node', () => {
        // Only clear hover highlight if no node is selected
        if (!state.selectedNodeData) {
            clearHighlights();
        }
    });

    // Node click handler
    state.cytoscapeInstance.on('tap', 'node', async (evt) => {
        const node = evt.target;
        state.selectedNodeData = node.data();
        highlightNodeNeighborhood(node, true); // Persistent highlight
        if (inspectorModule && inspectorModule.selectNode) {
            await inspectorModule.selectNode(state.selectedNodeData);
        }
    });

    // Edge hover - show relationship type
    state.cytoscapeInstance.on('mouseover', 'edge', (evt) => {
        evt.target.addClass('hovered');
    });

    state.cytoscapeInstance.on('mouseout', 'edge', (evt) => {
        evt.target.removeClass('hovered');
    });

    // Click on background to deselect
    state.cytoscapeInstance.on('tap', (evt) => {
        if (evt.target === state.cytoscapeInstance) {
            clearHighlights();
            if (inspectorModule && inspectorModule.closeInspector) {
                inspectorModule.closeInspector();
            }
        }
    });

    // Set up ResizeObserver to handle container size changes
    // This ensures cytoscape redraws correctly when inspector panel opens/closes
    state.graphResizeObserver = new ResizeObserver(() => {
        if (state.cytoscapeInstance) {
            state.cytoscapeInstance.resize();
            // Optional: re-fit after resize for better UX (commented out to preserve user's zoom/pan)
            // state.cytoscapeInstance.fit(null, 30);
        }
    });
    state.graphResizeObserver.observe(container);

    // Build type legend
    buildTypeLegend(data.nodes);
}

// Highlight a node and its neighborhood
function highlightNodeNeighborhood(node, persistent = false) {
    if (!state.cytoscapeInstance) return;

    const neighborhood = node.neighborhood().add(node);
    const connectedEdges = node.connectedEdges();

    // Clear previous highlights
    state.cytoscapeInstance.elements().removeClass('highlighted dimmed');

    // Dim all elements
    state.cytoscapeInstance.elements().addClass('dimmed');

    // Highlight neighborhood
    neighborhood.removeClass('dimmed').addClass('highlighted');
    connectedEdges.removeClass('dimmed').addClass('highlighted');

    // The selected node itself shouldn't have .highlighted class, just .selected
    node.removeClass('highlighted');
}

// Clear all highlights
function clearHighlights() {
    if (!state.cytoscapeInstance) return;
    state.cytoscapeInstance.elements().removeClass('highlighted dimmed');
}

// Build the type legend based on actual types in the graph
function buildTypeLegend(nodes) {
    const legendContainer = document.getElementById('kg-type-legend');
    if (!legendContainer) return;

    // Count entities per type
    const typeCounts = {};
    nodes.forEach(n => {
        const type = n.data.type || 'Unknown';
        typeCounts[type] = (typeCounts[type] || 0) + 1;
    });

    // Sort by count descending
    const sortedTypes = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);

    // Type colors
    const typeColors = {
        'Person': '#3b82f6',
        'Character': '#3b82f6',
        'Organization': '#10b981',
        'Group': '#10b981',
        'Event': '#f59e0b',
        'Location': '#ef4444',
        'Place': '#ef4444',
        'Concept': '#8b5cf6',
        'Theme': '#8b5cf6',
        'Technology': '#06b6d4',
        'Product': '#ec4899',
        'Object': '#ec4899',
        'default': '#64748b'
    };

    // Build legend HTML
    let html = '<div class="legend-title">Entity Types</div><div class="legend-items">';
    sortedTypes.forEach(([type, count]) => {
        const color = typeColors[type] || typeColors.default;
        html += `
            <button class="legend-item" data-type="${escapeHtml(type)}" onclick="window.kg_filterByType('${escapeHtml(type)}')">
                <span class="legend-dot" style="background-color: ${color}"></span>
                <span class="legend-label">${escapeHtml(type)}</span>
                <span class="legend-count">${count}</span>
            </button>
        `;
    });
    html += `
        <button class="legend-item legend-reset" onclick="window.kg_clearTypeFilter()">
            <i class="ph-bold ph-arrow-counter-clockwise"></i>
            <span class="legend-label">Show All</span>
        </button>
    </div>`;

    legendContainer.innerHTML = html;
    legendContainer.classList.remove('hidden');
}

// Filter graph by entity type
function filterByType(type) {
    if (!state.cytoscapeInstance) return;

    // Update active state in legend
    document.querySelectorAll('.legend-item').forEach(item => {
        item.classList.toggle('active', item.dataset.type === type);
    });

    // Show only nodes of this type and their edges
    const matchingNodes = state.cytoscapeInstance.nodes().filter(n => n.data('type') === type);
    const connectedEdges = matchingNodes.connectedEdges();
    const connectedNodes = connectedEdges.connectedNodes();

    state.cytoscapeInstance.elements().addClass('dimmed');
    matchingNodes.removeClass('dimmed').addClass('filtered');
    connectedEdges.removeClass('dimmed');
    connectedNodes.removeClass('dimmed');
}

// Clear type filter
function clearTypeFilter() {
    if (!state.cytoscapeInstance) return;

    document.querySelectorAll('.legend-item').forEach(item => {
        item.classList.remove('active');
    });

    state.cytoscapeInstance.elements().removeClass('dimmed filtered');
}

function renderEmptyGraph() {
    const container = document.getElementById('kg-graph-container');
    if (!container) return;

    // Clean up observer and instance
    if (state.graphResizeObserver) {
        state.graphResizeObserver.disconnect();
        state.graphResizeObserver = null;
    }
    if (state.cytoscapeInstance) {
        state.cytoscapeInstance.destroy();
        state.cytoscapeInstance = null;
    }

    container.innerHTML = `
        <div class="flex items-center justify-center h-full text-center">
            <div>
                <i class="ph-light ph-graph text-6xl text-[var(--text-muted)] opacity-50"></i>
                <p class="text-sm text-[var(--text-secondary)] mt-4">No graph data yet</p>
                <p class="text-xs text-[var(--text-muted)] mt-2">Extract entities from a video to populate the graph</p>
            </div>
        </div>
    `;
}

function changeGraphLayout(layout) {
    if (!state.cytoscapeInstance) return;

    const layoutOptions = {
        name: layout,
        animate: true,
        animationDuration: 500,
        fit: true,
        padding: 30
    };

    if (layout === 'cose') {
        layoutOptions.nodeRepulsion = 8000;
        layoutOptions.idealEdgeLength = 100;
        layoutOptions.edgeElasticity = 100;
    }

    state.cytoscapeInstance.layout(layoutOptions).run();

    document.querySelectorAll('.graph-layout-option').forEach(opt => {
        opt.classList.toggle('active', opt.dataset.layout === layout);
    });

    document.getElementById('graph-layout-dropdown')?.classList.add('hidden');
}

function fitGraphView() {
    if (!state.cytoscapeInstance) return;
    state.cytoscapeInstance.fit(null, 30);
}

function resetGraphView() {
    if (!state.cytoscapeInstance) return;
    state.cytoscapeInstance.zoom(1);
    state.cytoscapeInstance.center();
}

function updateGraphStats(data) {
    const nodes = data.nodes || [];
    const edges = data.edges || [];

    // Count unique entity types
    const types = new Set(nodes.map(n => n.data.type));

    document.getElementById('kg-stat-nodes').textContent = nodes.length;
    document.getElementById('kg-stat-edges').textContent = edges.length;
}

export {
    initKGGraph,
    renderGraph,
    highlightNodeNeighborhood,
    clearHighlights,
    buildTypeLegend,
    filterByType,
    clearTypeFilter,
    toggleKGView,
    changeGraphLayout,
    fitGraphView,
    resetGraphView,
    renderEmptyGraph,
    updateGraphStats,
    setInspectorModule
};
