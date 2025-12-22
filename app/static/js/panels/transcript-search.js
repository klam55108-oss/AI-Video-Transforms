// ============================================
// Transcript Search Module
// Client-side search and filtering for transcripts
// ============================================

import { escapeHtml } from '../core/utils.js';
import { renderTranscriptsList } from './transcripts.js';

// ============================================
// Search State
// ============================================

let allTranscripts = [];
let searchDebounceTimer = null;
const DEBOUNCE_DELAY = 300; // ms

// ============================================
// Element References (Lazy Lookup)
// ============================================

function getSearchInput() {
    return document.getElementById('transcript-search');
}

function getClearButton() {
    return document.getElementById('transcript-search-clear');
}

function getTranscriptsList() {
    return document.getElementById('transcripts-list');
}

// ============================================
// Initialization
// ============================================

export function initTranscriptSearch() {
    const searchInput = getSearchInput();
    const clearButton = getClearButton();

    if (!searchInput) return;

    // Debounced search on input
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value;

        // Show/hide clear button
        if (clearButton) {
            if (query.length > 0) {
                clearButton.classList.remove('hidden');
            } else {
                clearButton.classList.add('hidden');
            }
        }

        // Debounce search
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
            searchTranscripts(query);
        }, DEBOUNCE_DELAY);
    });

    // Clear button
    if (clearButton) {
        clearButton.addEventListener('click', clearSearch);
    }

    // Clear on Escape key
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            clearSearch();
            searchInput.blur();
        }
    });
}

// ============================================
// Search Logic
// ============================================

export function searchTranscripts(query) {
    const trimmedQuery = query.trim().toLowerCase();

    if (!trimmedQuery) {
        // Show all transcripts if query is empty
        renderTranscriptsList(allTranscripts);
        return;
    }

    // Filter transcripts by filename (case-insensitive)
    const filtered = allTranscripts.filter(t => {
        return t.filename.toLowerCase().includes(trimmedQuery);
    });

    // Render filtered results with highlighted matches
    renderFilteredTranscripts(filtered, trimmedQuery);
}

// ============================================
// Rendering
// ============================================

function renderFilteredTranscripts(transcripts, query) {
    const transcriptsList = getTranscriptsList();
    if (!transcriptsList) return;

    if (transcripts.length === 0) {
        transcriptsList.innerHTML = `
            <div class="px-2 py-3 text-center">
                <i class="ph-light ph-magnifying-glass text-xl text-[var(--sidebar-text-muted)] opacity-50"></i>
                <p class="text-[10px] text-[var(--sidebar-text-muted)] mt-1">No matches found</p>
            </div>
        `;
        return;
    }

    const items = transcripts.map(t => {
        const highlightedFilename = highlightMatches(t.filename, query);
        const escapedTitle = escapeHtml(t.filename);
        const sizeText = formatFileSize(t.file_size);
        const timeText = formatRelativeTime(t.created_at);

        return `
            <div class="flex items-center justify-between px-2 py-1.5 text-xs rounded-md group
                        text-[var(--sidebar-text-secondary)] hover:bg-[var(--sidebar-hover)]">
                <div class="truncate flex-1 mr-2" title="${escapedTitle}">
                    <div class="font-medium truncate">${highlightedFilename}</div>
                    <div class="text-[var(--sidebar-text-muted)] text-[10px]">${sizeText} · ${timeText}</div>
                </div>
                <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onclick="window.downloadTranscript('${t.id}')" title="Download"
                            class="p-1 hover:text-[var(--sidebar-text-primary)] transition-colors">
                        <i class="ph-bold ph-download-simple text-sm"></i>
                    </button>
                    <button onclick="window.deleteTranscript('${t.id}')" title="Delete"
                            class="p-1 hover:text-[var(--status-error)] transition-colors">
                        <i class="ph-bold ph-trash text-sm"></i>
                    </button>
                </div>
            </div>
        `;
    });

    transcriptsList.innerHTML = items.join('');
}

// ============================================
// Highlighting
// ============================================

export function highlightMatches(text, query) {
    if (!query) return escapeHtml(text);

    const escapedText = escapeHtml(text);
    const escapedQuery = escapeHtml(query);

    // Case-insensitive replace
    const regex = new RegExp(`(${escapedQuery})`, 'gi');
    return escapedText.replace(regex, '<mark class="transcript-search-highlight">$1</mark>');
}

// ============================================
// Clear Search
// ============================================

export function clearSearch() {
    const searchInput = getSearchInput();
    const clearButton = getClearButton();

    if (searchInput) {
        searchInput.value = '';
    }

    if (clearButton) {
        clearButton.classList.add('hidden');
    }

    // Show all transcripts
    renderTranscriptsList(allTranscripts);
}

// ============================================
// Cache Management
// ============================================

export function updateTranscriptsCache(transcripts) {
    allTranscripts = transcripts;
}

// ============================================
// Helper Functions (from utils.js pattern)
// ============================================

function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatRelativeTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
}
