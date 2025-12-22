// ============================================
// Evidence Module
// Evidence citations and cross-panel navigation
// ============================================

import { escapeHtml } from '../core/utils.js';
import { showToast } from '../ui/toast.js';

// ============================================
// Fetch Evidence for Node
// ============================================

export async function fetchNodeEvidence(projectId, nodeId) {
    try {
        const response = await fetch(`/kg/projects/${projectId}/nodes/${nodeId}/evidence`);

        if (!response.ok) {
            if (response.status === 404) {
                // API endpoint not available yet
                return null;
            }
            throw new Error('Failed to fetch evidence');
        }

        const data = await response.json();
        return data.evidence || [];

    } catch (e) {
        console.error('Failed to fetch evidence:', e);
        return null;
    }
}

// ============================================
// Render Evidence Section
// ============================================

export function renderEvidenceSection(evidence) {
    if (!evidence || evidence.length === 0) {
        return `
            <div class="inspector-evidence-section">
                <span class="label text-[10px] font-semibold text-[var(--text-muted)] uppercase">Supporting Evidence</span>
                <p class="text-xs text-[var(--text-muted)] mt-2">
                    No citation data available (extracted before citation tracking)
                </p>
            </div>
        `;
    }

    const items = evidence.map(e => {
        // Truncate text for preview
        const previewText = e.text.length > 200
            ? e.text.substring(0, 200) + '...'
            : e.text;

        // Encode search text for URL parameter
        const searchText = encodeURIComponent(e.text.substring(0, 100));

        return `
            <div class="evidence-item bg-[var(--bg-tertiary)] hover:bg-[var(--bg-elevated)] p-3 rounded-lg mb-2 transition-colors">
                <blockquote class="text-xs italic border-l-2 border-[var(--accent-primary)] pl-3 text-[var(--text-secondary)]">
                    "${escapeHtml(previewText)}"
                </blockquote>
                <div class="flex justify-between items-center mt-2 gap-2">
                    <span class="text-[10px] text-[var(--text-muted)] truncate" title="${escapeHtml(e.source_title)}">
                        ${escapeHtml(e.source_title)}
                    </span>
                    <button
                        onclick="kg_jumpToEvidence('${e.source_id}', '${searchText}')"
                        class="text-[10px] text-[var(--accent-primary)] hover:text-[var(--accent-primary-hover)] font-medium flex items-center gap-1 flex-shrink-0"
                        title="View in transcript"
                    >
                        View <i class="ph-bold ph-arrow-right"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');

    return `
        <div class="inspector-evidence-section mt-3 pt-3 border-t border-[var(--divider)]">
            <span class="label text-[10px] font-semibold text-[var(--text-muted)] uppercase">
                Supporting Evidence (${evidence.length})
            </span>
            <div class="mt-2 space-y-2 max-h-64 overflow-y-auto">
                ${items}
            </div>
        </div>
    `;
}

// ============================================
// Cross-Panel Navigation
// ============================================

export async function jumpToEvidence(sourceId, encodedSearchText) {
    try {
        // Decode search text
        const searchText = decodeURIComponent(encodedSearchText);

        // Open transcript viewer with search query
        if (typeof window.openTranscriptViewer === 'function') {
            await window.openTranscriptViewer(sourceId, searchText);
        } else {
            console.error('openTranscriptViewer not available');
            showToast('Transcript viewer not available', 'error');
        }

    } catch (e) {
        console.error('Failed to jump to evidence:', e);
        showToast('Failed to open transcript', 'error');
    }
}

// ============================================
// Global Exports
// ============================================

// Export for window binding (onclick handlers)
window.kg_jumpToEvidence = jumpToEvidence;
