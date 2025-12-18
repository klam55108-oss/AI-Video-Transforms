// ============================================
// Transcripts Management
// ============================================

import { escapeHtml, formatRelativeTime, formatFileSize } from '../core/utils.js';
import { showToast } from '../ui/toast.js';

export async function loadTranscripts() {
    const transcriptsList = document.getElementById('transcripts-list');

    // Show skeleton loader
    if (transcriptsList) {
        transcriptsList.innerHTML = `
            <div class="skeleton-loader">
                <div class="skeleton-line h-4 w-2/3"></div>
                <div class="skeleton-line h-3 w-1/2 mt-1"></div>
            </div>
            <div class="skeleton-loader">
                <div class="skeleton-line h-4 w-3/4"></div>
                <div class="skeleton-line h-3 w-1/2 mt-1"></div>
            </div>
        `;
    }

    try {
        const response = await fetch('/transcripts');
        if (!response.ok) throw new Error('Failed to load transcripts');
        const data = await response.json();
        renderTranscriptsList(data.transcripts);
    } catch (e) {
        console.error('Transcripts load failed:', e);
        if (transcriptsList) {
            transcriptsList.innerHTML = '<p class="text-xs text-[var(--sidebar-text-muted)] px-2 py-1">Failed to load</p>';
        }
    }
}

export function renderTranscriptsList(transcripts) {
    const transcriptsList = document.getElementById('transcripts-list');
    if (!transcriptsList) return;

    if (transcripts.length === 0) {
        transcriptsList.innerHTML = '<p class="text-xs text-[var(--sidebar-text-muted)] px-2 py-1">No transcripts yet</p>';
        return;
    }

    transcriptsList.innerHTML = transcripts.map(t => `
        <div class="flex items-center justify-between px-2 py-1.5 text-xs rounded-md group
                    text-[var(--sidebar-text-secondary)] hover:bg-[var(--sidebar-hover)]">
            <div class="truncate flex-1 mr-2" title="${escapeHtml(t.filename)}">
                <div class="font-medium truncate">${escapeHtml(t.filename)}</div>
                <div class="text-[var(--sidebar-text-muted)] text-[10px]">${formatFileSize(t.file_size)} · ${formatRelativeTime(t.created_at)}</div>
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
    `).join('');
}

export function toggleTranscriptsPanel() {
    const transcriptsList = document.getElementById('transcripts-list');
    const transcriptsCaret = document.getElementById('transcripts-caret');

    if (!transcriptsList || !transcriptsCaret) return;

    const isOpen = transcriptsList.classList.contains('open');

    if (isOpen) {
        transcriptsList.classList.remove('open');
        transcriptsCaret.classList.remove('open');
    } else {
        transcriptsList.classList.add('open');
        transcriptsCaret.classList.add('open');
        loadTranscripts();
    }
}

export function downloadTranscript(id) {
    window.open(`/transcripts/${id}/download`, '_blank');
}

export async function deleteTranscript(id) {
    if (!confirm('Delete this transcript? The file will be removed.')) return;

    try {
        await fetch(`/transcripts/${id}`, { method: 'DELETE' });
        loadTranscripts();
        showToast('Transcript deleted', 'success');
    } catch (e) {
        console.error('Delete failed:', e);
        showToast('Failed to delete transcript', 'error');
    }
}

// Expose to global scope for onclick handlers
window.downloadTranscript = downloadTranscript;
window.deleteTranscript = deleteTranscript;
