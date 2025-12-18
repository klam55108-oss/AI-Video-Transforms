// Knowledge Graph Module - Main Entry Point
// ============================================
// Aggregates all KG submodules and resolves circular dependencies

// Import all modules
import * as api from './api.js';
import * as ui from './ui.js';
import * as polling from './polling.js';
import * as actions from './actions.js';
import * as inspector from './inspector.js';
import * as graph from './graph.js';
import * as search from './search.js';
import * as panel from './panel.js';

// Resolve circular dependencies between graph and inspector
graph.setInspectorModule(inspector);
inspector.setGraphModule(graph);

// Re-export all public APIs
export { handleKGApiError, kgClient } from './api.js';
export { updateKGUI, updateKGStateBadge, updateKGActionButton, updateKGConfirmations, renderKGConfirmations, updateKGStats } from './ui.js';
export { startKGPolling, stopKGPolling, refreshKGProjectStatus } from './polling.js';
export { createKGProject, confirmKGDiscovery, exportKGGraph, batchExportKGProjects } from './actions.js';
export { selectNode, updateInspector, showInspector, closeInspector, selectNodeById } from './inspector.js';
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
    updateGraphStats
} from './graph.js';
export { initGraphSearch, performGraphSearch, navigateToNode, hideSearchResults, toggleTypeFilter, clearAllFilters } from './search.js';
export {
    toggleKGPanel,
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
} from './panel.js';

// Expose key functions to window for onclick handlers (temporary - will refactor to event delegation)
window.kg_confirmKGDiscovery = actions.confirmKGDiscovery;
window.kg_filterByType = graph.filterByType;
window.kg_clearTypeFilter = graph.clearTypeFilter;
window.kg_toggleTypeFilter = search.toggleTypeFilter;
window.kg_clearAllFilters = search.clearAllFilters;
window.kg_navigateToNode = search.navigateToNode;
window.kg_selectNodeById = inspector.selectNodeById;
window.kg_handleDropdownSelect = panel.handleDropdownSelect;
window.kg_deleteKGProject = panel.deleteKGProject;
window.kg_loadKGProjects = panel.loadKGProjects;
window.kg_selectKGProject = panel.selectKGProject;
