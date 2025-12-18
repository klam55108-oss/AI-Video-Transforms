// Graph Search Functionality
// ============================================

import { state } from '../core/state.js';
import { highlightNodeNeighborhood, clearHighlights } from './graph.js';
import { selectNode } from './inspector.js';

// Search state
let graphSearchData = []; // Cache of all nodes for searching
let searchSelectedIndex = -1;
let activeTypeFilters = new Set(); // Active entity type filters

// escapeHtml utility (temporary - will import from utils once available)
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function updateSearchSelection(results) {
    results.forEach((item, idx) => {
        item.classList.toggle('selected', idx === searchSelectedIndex);
    });

    // Scroll selected item into view
    if (searchSelectedIndex >= 0 && results[searchSelectedIndex]) {
        results[searchSelectedIndex].scrollIntoView({ block: 'nearest' });
    }
}

function initGraphSearch() {
    const searchInput = document.getElementById('kg-graph-search');
    const clearBtn = document.getElementById('kg-search-clear');
    const resultsContainer = document.getElementById('kg-search-results');

    if (!searchInput) return;

    // Debounced search
    let searchTimeout;
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();

        // Show/hide clear button
        clearBtn?.classList.toggle('hidden', !query);

        // Reset selection
        searchSelectedIndex = -1;

        // Debounce search
        clearTimeout(searchTimeout);
        if (query.length >= 1) {
            searchTimeout = setTimeout(() => performGraphSearch(query), 150);
        } else {
            hideSearchResults();
            clearHighlights();
        }
    });

    // Keyboard navigation
    searchInput.addEventListener('keydown', (e) => {
        const results = resultsContainer?.querySelectorAll('.search-result-item') || [];

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            searchSelectedIndex = Math.min(searchSelectedIndex + 1, results.length - 1);
            updateSearchSelection(results);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            searchSelectedIndex = Math.max(searchSelectedIndex - 1, 0);
            updateSearchSelection(results);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (searchSelectedIndex >= 0 && results[searchSelectedIndex]) {
                const nodeId = results[searchSelectedIndex].dataset.nodeId;
                navigateToNode(nodeId);
            } else if (results.length > 0) {
                const nodeId = results[0].dataset.nodeId;
                navigateToNode(nodeId);
            }
        } else if (e.key === 'Escape') {
            hideSearchResults();
            searchInput.blur();
        }
    });

    // Clear button
    clearBtn?.addEventListener('click', () => {
        searchInput.value = '';
        clearBtn.classList.add('hidden');
        hideSearchResults();
        clearHighlights();
        searchInput.focus();
    });

    // Click outside to close
    document.addEventListener('click', (e) => {
        const container = document.getElementById('kg-search-container');
        if (container && !container.contains(e.target)) {
            hideSearchResults();
        }
    });
}

function performGraphSearch(query) {
    if (!state.cytoscapeInstance) return;

    const resultsContainer = document.getElementById('kg-search-results');
    if (!resultsContainer) return;

    const lowerQuery = query.toLowerCase();

    // Search through nodes
    const matches = [];
    state.cytoscapeInstance.nodes().forEach(node => {
        const data = node.data();
        const label = (data.label || '').toLowerCase();
        const aliases = (data.aliases || []).map(a => a.toLowerCase());
        const type = (data.type || '').toLowerCase();

        // Apply type filters if active
        if (activeTypeFilters.size > 0 && !activeTypeFilters.has(data.type)) {
            return;
        }

        // Check label, aliases, and type
        if (label.includes(lowerQuery) ||
            aliases.some(a => a.includes(lowerQuery)) ||
            type.includes(lowerQuery)) {
            matches.push({
                id: data.id,
                label: data.label,
                type: data.type,
                degree: data.degree || 0,
                matchScore: label.startsWith(lowerQuery) ? 2 : 1
            });
        }
    });

    // Sort by match score (prefix matches first), then by degree
    matches.sort((a, b) => {
        if (b.matchScore !== a.matchScore) return b.matchScore - a.matchScore;
        return b.degree - a.degree;
    });

    // Update match count display
    updateMatchCount(matches.length);

    // Limit results
    const topMatches = matches.slice(0, 8);

    if (topMatches.length === 0) {
        resultsContainer.innerHTML = '<div class="search-no-results">No entities found</div>';
    } else {
        // Type colors for result dots
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

        resultsContainer.innerHTML = topMatches.map((match, idx) => {
            const color = typeColors[match.type] || typeColors.default;
            return `
                <div class="search-result-item ${idx === searchSelectedIndex ? 'selected' : ''}"
                     data-node-id="${escapeHtml(match.id)}"
                     onclick="window.kg_navigateToNode('${escapeHtml(match.id)}')">
                    <span class="result-dot" style="background-color: ${color}"></span>
                    <div class="result-info">
                        <div class="result-name">${escapeHtml(match.label)}</div>
                        <div class="result-type">${escapeHtml(match.type)}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    resultsContainer.classList.remove('hidden');
}

function navigateToNode(nodeId) {
    if (!state.cytoscapeInstance) return;

    const node = state.cytoscapeInstance.nodes(`[id = "${nodeId}"]`);
    if (node.length === 0) return;

    // Hide search results
    hideSearchResults();

    // Clear search input
    const searchInput = document.getElementById('kg-graph-search');
    if (searchInput) {
        searchInput.value = '';
        document.getElementById('kg-search-clear')?.classList.add('hidden');
    }

    // Animate to node
    state.cytoscapeInstance.animate({
        center: { eles: node },
        zoom: 1.8
    }, {
        duration: 400,
        easing: 'ease-out-cubic',
        complete: async () => {
            // Select the node
            state.selectedNodeData = node.data();
            highlightNodeNeighborhood(node, true);
            await selectNode(state.selectedNodeData);
        }
    });
}

function hideSearchResults() {
    const resultsContainer = document.getElementById('kg-search-results');
    resultsContainer?.classList.add('hidden');
    searchSelectedIndex = -1;
}

function updateMatchCount(matchCount) {
    const matchCountEl = document.getElementById('kg-match-count');
    if (!matchCountEl) return;

    if (!state.cytoscapeInstance) {
        matchCountEl.classList.add('hidden');
        return;
    }

    const totalNodes = state.cytoscapeInstance.nodes().length;

    if (activeTypeFilters.size > 0 || document.getElementById('kg-graph-search')?.value.trim()) {
        matchCountEl.textContent = `${matchCount} of ${totalNodes} entities`;
        matchCountEl.classList.remove('hidden');
    } else {
        matchCountEl.classList.add('hidden');
    }
}

function toggleTypeFilter(type) {
    if (activeTypeFilters.has(type)) {
        activeTypeFilters.delete(type);
    } else {
        activeTypeFilters.add(type);
    }

    // Update filter chips UI
    updateFilterChips();

    // Apply visual filtering to graph
    applyGraphFilters();

    // Re-run search if there's a query
    const searchInput = document.getElementById('kg-graph-search');
    const query = searchInput?.value.trim();
    if (query) {
        performGraphSearch(query);
    } else {
        updateMatchCount(getFilteredNodeCount());
    }
}

function updateFilterChips() {
    const chipsContainer = document.getElementById('kg-filter-chips');
    if (!chipsContainer) return;

    if (activeTypeFilters.size === 0) {
        chipsContainer.innerHTML = '';
        chipsContainer.classList.add('hidden');
        return;
    }

    chipsContainer.classList.remove('hidden');
    const typeColors = getTypeColors();

    chipsContainer.innerHTML = Array.from(activeTypeFilters).map(type => {
        const color = typeColors[type] || typeColors.default;
        return `
            <button class="filter-chip"
                    onclick="window.kg_toggleTypeFilter('${escapeHtml(type)}')"
                    style="--chip-color: ${color}">
                <span>${escapeHtml(type)}</span>
                <i class="ph-bold ph-x"></i>
            </button>
        `;
    }).join('');
}

function clearAllFilters() {
    activeTypeFilters.clear();
    updateFilterChips();
    applyGraphFilters();

    const searchInput = document.getElementById('kg-graph-search');
    if (searchInput?.value.trim()) {
        performGraphSearch(searchInput.value.trim());
    } else {
        updateMatchCount(0);
    }
}

function applyGraphFilters() {
    if (!state.cytoscapeInstance) return;

    if (activeTypeFilters.size === 0) {
        // No filters - show all
        state.cytoscapeInstance.elements().removeClass('dimmed filtered');
        return;
    }

    // Dim all nodes first
    state.cytoscapeInstance.nodes().addClass('dimmed');

    // Highlight filtered nodes and their connections
    activeTypeFilters.forEach(type => {
        const matchingNodes = state.cytoscapeInstance.nodes().filter(n => n.data('type') === type);
        const connectedEdges = matchingNodes.connectedEdges();
        const connectedNodes = connectedEdges.connectedNodes();

        matchingNodes.removeClass('dimmed').addClass('filtered');
        connectedEdges.removeClass('dimmed');
        connectedNodes.removeClass('dimmed');
    });
}

function getFilteredNodeCount() {
    if (!state.cytoscapeInstance) return 0;

    if (activeTypeFilters.size === 0) return 0;

    let count = 0;
    state.cytoscapeInstance.nodes().forEach(node => {
        if (activeTypeFilters.has(node.data('type'))) {
            count++;
        }
    });
    return count;
}

function getTypeColors() {
    return {
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
}

export {
    initGraphSearch,
    performGraphSearch,
    navigateToNode,
    hideSearchResults,
    toggleTypeFilter,
    clearAllFilters,
    graphSearchData,
    searchSelectedIndex
};
