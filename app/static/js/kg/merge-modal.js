// Entity Merge Modal
// ============================================
// Modal for merging duplicate entities in the Knowledge Graph

import { escapeHtml } from '../core/utils.js';
import { showToast } from '../ui/toast.js';
import { mergeEntities } from './api.js';
import { initKGGraph } from './graph.js';
import { state } from '../core/state.js';
import { closeInspector } from './inspector.js';

// ============================================
// Confidence Level Helpers
// ============================================

/**
 * Get the confidence level category based on score.
 * @param {number} confidence - Confidence score 0.0-1.0
 * @returns {'high' | 'medium' | 'low'}
 */
function getConfidenceLevel(confidence) {
    if (confidence >= 0.9) return 'high';
    if (confidence >= 0.7) return 'medium';
    return 'low';
}

/**
 * Get human-readable confidence label.
 * @param {number} confidence - Confidence score 0.0-1.0
 * @returns {string}
 */
function getConfidenceLabel(confidence) {
    const level = getConfidenceLevel(confidence);
    const labels = {
        high: 'High Confidence',
        medium: 'Medium Confidence',
        low: 'Low Confidence'
    };
    return labels[level];
}

// ============================================
// Signal Formatting
// ============================================

/**
 * Format signal breakdown for tooltip display.
 * @param {Record<string, number>} signals - Signal scores
 * @returns {string} HTML string for tooltip
 */
function formatSignals(signals) {
    if (!signals || Object.keys(signals).length === 0) {
        return 'No signals available';
    }

    const signalLabels = {
        fuzzy_label: 'Label Similarity',
        alias_overlap: 'Alias Overlap',
        type_match: 'Type Match',
        shared_connections: 'Shared Connections',
        description_similarity: 'Description Similarity'
    };

    return Object.entries(signals)
        .map(([key, value]) => {
            const label = signalLabels[key] || key.replace(/_/g, ' ');
            const percentage = Math.round(value * 100);
            return `<div class="signal-row">
                <span class="signal-label">${escapeHtml(label)}</span>
                <span class="signal-value">${percentage}%</span>
            </div>`;
        })
        .join('');
}

// ============================================
// Alias Rendering
// ============================================

/**
 * Render aliases as tags.
 * @param {string[]} aliases - Array of alias strings
 * @returns {string} HTML string
 */
function renderAliases(aliases) {
    if (!aliases || aliases.length === 0) {
        return '<span class="text-xs text-[var(--text-muted)]">No aliases</span>';
    }

    return `
        <div class="merge-node-aliases">
            ${aliases.slice(0, 5).map(alias =>
                `<span class="alias-tag">${escapeHtml(alias)}</span>`
            ).join('')}
            ${aliases.length > 5 ? `<span class="alias-more">+${aliases.length - 5} more</span>` : ''}
        </div>
    `;
}

// ============================================
// Modal Creation and Management
// ============================================

/**
 * Create the merge modal HTML structure.
 * @param {Object} nodeA - First node data
 * @param {Object} nodeB - Second node data
 * @param {number} confidence - Match confidence score
 * @param {Record<string, number>} signals - Signal breakdown
 * @returns {string} HTML string
 */
function createMergeModalHTML(nodeA, nodeB, confidence, signals = {}) {
    const confidenceLevel = getConfidenceLevel(confidence);
    const confidencePercent = Math.round(confidence * 100);

    return `
        <div class="merge-modal-overlay" id="merge-modal" role="dialog" aria-modal="true" aria-labelledby="merge-modal-title">
            <div class="merge-modal">
                <div class="merge-modal-header">
                    <h3 id="merge-modal-title">Merge Entities</h3>
                    <div class="merge-modal-header-right">
                        <span class="confidence-badge confidence-${confidenceLevel}"
                              title="${getConfidenceLabel(confidence)}">
                            ${confidencePercent}% match
                        </span>
                        <button class="merge-modal-close" onclick="window.kg_closeMergeModal()" aria-label="Close">
                            <i class="ph-bold ph-x"></i>
                        </button>
                    </div>
                </div>

                <p class="merge-modal-description">
                    Select which entity to keep. The other entity's aliases and connections will be merged.
                </p>

                <div class="merge-comparison">
                    <label class="merge-node" data-node-id="${escapeHtml(nodeA.id)}">
                        <input type="radio" name="survivor" value="${escapeHtml(nodeA.id)}" checked>
                        <div class="merge-node-content">
                            <div class="merge-node-header">
                                <span class="merge-node-radio"></span>
                                <h4 class="merge-node-label">${escapeHtml(nodeA.label || nodeA.id)}</h4>
                            </div>
                            <span class="merge-node-type">${escapeHtml(nodeA.type || nodeA.entity_type || 'Unknown')}</span>
                            ${nodeA.description ? `<p class="merge-node-description">${escapeHtml(nodeA.description)}</p>` : ''}
                            ${renderAliases(nodeA.aliases)}
                        </div>
                    </label>

                    <div class="merge-vs">
                        <span>VS</span>
                    </div>

                    <label class="merge-node" data-node-id="${escapeHtml(nodeB.id)}">
                        <input type="radio" name="survivor" value="${escapeHtml(nodeB.id)}">
                        <div class="merge-node-content">
                            <div class="merge-node-header">
                                <span class="merge-node-radio"></span>
                                <h4 class="merge-node-label">${escapeHtml(nodeB.label || nodeB.id)}</h4>
                            </div>
                            <span class="merge-node-type">${escapeHtml(nodeB.type || nodeB.entity_type || 'Unknown')}</span>
                            ${nodeB.description ? `<p class="merge-node-description">${escapeHtml(nodeB.description)}</p>` : ''}
                            ${renderAliases(nodeB.aliases)}
                        </div>
                    </label>
                </div>

                ${Object.keys(signals).length > 0 ? `
                    <details class="merge-signals-details">
                        <summary>
                            <i class="ph-regular ph-info"></i>
                            Match signals
                        </summary>
                        <div class="merge-signals-content">
                            ${formatSignals(signals)}
                        </div>
                    </details>
                ` : ''}

                <div class="merge-modal-actions">
                    <button class="btn-secondary" onclick="window.kg_closeMergeModal()">Cancel</button>
                    <button class="btn-primary" id="merge-execute-btn" onclick="window.kg_executeMerge()">
                        <i class="ph-bold ph-git-merge"></i>
                        Merge
                    </button>
                </div>
            </div>
        </div>
    `;
}

// Store current merge context
let currentMergeContext = null;

/**
 * Show the merge modal for two entities.
 * @param {string} projectId - The project ID
 * @param {Object} nodeA - First node data
 * @param {Object} nodeB - Second node data
 * @param {number} confidence - Match confidence score
 * @param {Record<string, number>} signals - Signal breakdown
 */
function showMergeModal(projectId, nodeA, nodeB, confidence, signals = {}) {
    // Remove any existing modal
    closeMergeModal();

    // Store merge context
    currentMergeContext = {
        projectId,
        nodeA,
        nodeB
    };

    // Create and insert modal
    const modalHTML = createMergeModalHTML(nodeA, nodeB, confidence, signals);
    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Focus the modal for accessibility
    const modal = document.getElementById('merge-modal');
    modal?.focus();

    // Add keyboard event listener
    modal?.addEventListener('keydown', handleModalKeydown);

    // Trap focus within modal
    trapFocus(modal);
}

/**
 * Close the merge modal.
 */
function closeMergeModal() {
    const modal = document.getElementById('merge-modal');
    if (modal) {
        modal.removeEventListener('keydown', handleModalKeydown);
        modal.remove();
    }
    currentMergeContext = null;
}

/**
 * Handle keyboard events in the modal.
 * @param {KeyboardEvent} e
 */
function handleModalKeydown(e) {
    if (e.key === 'Escape') {
        e.preventDefault();
        closeMergeModal();
    }
}

/**
 * Trap focus within the modal for accessibility.
 * @param {HTMLElement} modal
 */
function trapFocus(modal) {
    if (!modal) return;

    const focusableElements = modal.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    modal.addEventListener('keydown', (e) => {
        if (e.key !== 'Tab') return;

        if (e.shiftKey) {
            if (document.activeElement === firstElement) {
                e.preventDefault();
                lastElement.focus();
            }
        } else {
            if (document.activeElement === lastElement) {
                e.preventDefault();
                firstElement.focus();
            }
        }
    });
}

/**
 * Execute the merge operation.
 */
async function executeMerge() {
    if (!currentMergeContext) {
        showToast('No merge context available', 'error');
        return;
    }

    const { projectId, nodeA, nodeB } = currentMergeContext;
    const selectedRadio = document.querySelector('input[name="survivor"]:checked');

    if (!selectedRadio) {
        showToast('Please select which entity to keep', 'warning');
        return;
    }

    const survivorId = selectedRadio.value;
    const mergedId = survivorId === nodeA.id ? nodeB.id : nodeA.id;

    // Disable button and show loading state
    const executeBtn = document.getElementById('merge-execute-btn');
    if (executeBtn) {
        executeBtn.disabled = true;
        executeBtn.innerHTML = '<i class="ph-bold ph-spinner animate-spin"></i> Merging...';
    }

    try {
        const result = await mergeEntities(projectId, survivorId, mergedId);

        // Close modal
        closeMergeModal();

        // Close inspector since node may have changed
        closeInspector();

        // Show success message
        showMergeConfirmation(result);

        // Refresh graph
        if (state.kgCurrentProjectId === projectId) {
            await initKGGraph(projectId);
        }

        // Dispatch event for other components to react
        window.dispatchEvent(new CustomEvent('kg-merge-completed', {
            detail: { projectId, result }
        }));

    } catch (error) {
        console.error('Merge failed:', error);
        showToast(error.message || 'Failed to merge entities', 'error');

        // Re-enable button
        if (executeBtn) {
            executeBtn.disabled = false;
            executeBtn.innerHTML = '<i class="ph-bold ph-git-merge"></i> Merge';
        }
    }
}

/**
 * Show confirmation toast after successful merge.
 * @param {Object} history - Merge history record
 */
function showMergeConfirmation(history) {
    const mergedLabel = history.merged_label || 'Entity';
    showToast(`Merged "${mergedLabel}" into survivor node`, 'success');
}

// ============================================
// Window Exports for onclick handlers
// ============================================
window.kg_closeMergeModal = closeMergeModal;
window.kg_executeMerge = executeMerge;

export {
    showMergeModal,
    closeMergeModal,
    executeMerge,
    showMergeConfirmation,
    getConfidenceLevel,
    getConfidenceLabel
};
