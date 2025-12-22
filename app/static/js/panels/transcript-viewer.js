// ============================================
// Transcript Viewer Modal
// Full transcript display with search and highlighting
// ============================================

import { escapeHtml } from '../core/utils.js';
import { showToast } from '../ui/toast.js';
import { highlightMatches } from './transcript-search.js';

// ============================================
// State
// ============================================

let currentTranscriptId = null;
let currentTranscriptContent = null;

// ============================================
// Element References (Lazy Lookup)
// ============================================

function getModal() {
    return document.getElementById('transcript-viewer-modal');
}

function getModalTitle() {
    return document.getElementById('transcript-viewer-title');
}

function getModalContent() {
    return document.getElementById('transcript-viewer-content');
}

function getSearchInput() {
    return document.getElementById('transcript-viewer-search');
}

// ============================================
// Initialization
// ============================================

export function initTranscriptViewer() {
    // Modal structure is in index.html
    // Add event listeners for search
    const searchInput = getSearchInput();
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.trim();
            searchInTranscript(query);
        });
    }
}

// ============================================
// Open Transcript Viewer
// ============================================

export async function openTranscriptViewer(transcriptId, searchQuery = '') {
    currentTranscriptId = transcriptId;

    try {
        // Fetch transcript content
        const response = await fetch(`/transcripts/${transcriptId}`);
        if (!response.ok) {
            if (response.status === 404) {
                showToast('Transcript not found', 'error');
            } else {
                showToast('Failed to load transcript', 'error');
            }
            return;
        }

        const data = await response.json();
        currentTranscriptContent = data;

        // Render in modal
        renderTranscriptModal(data);

        // Show modal
        showModal('transcript-viewer-modal');

        // If search query provided, search and highlight
        if (searchQuery) {
            const searchInput = getSearchInput();
            if (searchInput) {
                searchInput.value = searchQuery;
            }
            searchInTranscript(searchQuery);
        }

    } catch (e) {
        console.error('Failed to load transcript:', e);
        showToast('Failed to load transcript', 'error');
    }
}

// ============================================
// Render Modal Content
// ============================================

function renderTranscriptModal(data) {
    const modalTitle = getModalTitle();
    const modalContent = getModalContent();

    if (!modalTitle || !modalContent) return;

    // Set title
    modalTitle.textContent = data.filename || 'Transcript';

    // Render content (use .content or .text field)
    const text = data.content || data.text || '';
    modalContent.innerHTML = `<pre class="whitespace-pre-wrap text-sm leading-relaxed">${escapeHtml(text)}</pre>`;
}

// ============================================
// Search in Transcript
// ============================================

export function searchInTranscript(query) {
    if (!currentTranscriptContent) return;

    const modalContent = getModalContent();
    if (!modalContent) return;

    const text = currentTranscriptContent.content || currentTranscriptContent.text || '';

    if (!query) {
        // No query - show plain text
        modalContent.innerHTML = `<pre class="whitespace-pre-wrap text-sm leading-relaxed">${escapeHtml(text)}</pre>`;
        return;
    }

    // Highlight matches
    const highlighted = highlightMatches(text, query);
    modalContent.innerHTML = `<pre class="whitespace-pre-wrap text-sm leading-relaxed">${highlighted}</pre>`;

    // Scroll to first match
    setTimeout(() => {
        const firstMatch = modalContent.querySelector('mark');
        if (firstMatch) {
            firstMatch.scrollIntoView({ behavior: 'smooth', block: 'center' });
            // Add pulse animation to first match
            firstMatch.style.animation = 'pulse-highlight 1s ease-in-out';
        }
    }, 100);
}

// ============================================
// Close Modal
// ============================================

export function closeTranscriptViewer() {
    const modal = getModal();
    if (modal) {
        modal.classList.add('hidden');
    }

    // Reset state
    currentTranscriptId = null;
    currentTranscriptContent = null;

    const searchInput = getSearchInput();
    if (searchInput) {
        searchInput.value = '';
    }
}

// ============================================
// Modal Utility (if not already global)
// ============================================

function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('hidden');
    }
}

export function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('hidden');
    }

    // If it's the transcript viewer, clean up
    if (modalId === 'transcript-viewer-modal') {
        closeTranscriptViewer();
    }
}

// ============================================
// Global Exports
// ============================================

// Export for window binding (cross-panel linking)
window.openTranscriptViewer = openTranscriptViewer;
window.searchInTranscript = searchInTranscript;
window.closeModal = closeModal;
