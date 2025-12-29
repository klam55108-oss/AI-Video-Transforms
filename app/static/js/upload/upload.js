// ============================================
// Upload Module
// File upload handling with progress feedback
// ============================================

import { state } from '../core/state.js';
import { formatFileSize } from '../core/utils.js';
import { showToast } from '../ui/toast.js';
import { addMessage, showLoading, removeLoading } from '../chat/messages.js';
import { sendMessage } from '../chat/send.js';

// ============================================
// File Upload State
// ============================================

let fileInput = null;
let pendingFile = null;  // File waiting for modal confirmation

// ============================================
// Element References (Lazy Lookup)
// ============================================

function getAttachBtn() {
    return document.getElementById('attach-btn');
}

function getModal() {
    return document.getElementById('upload-options-modal');
}

function getFilenameEl() {
    return document.getElementById('upload-filename');
}

function getFilesizeEl() {
    return document.getElementById('upload-filesize');
}

function getLanguageSelect() {
    return document.getElementById('upload-language');
}

function getDomainTextarea() {
    return document.getElementById('upload-domain');
}

function getCancelBtn() {
    return document.getElementById('upload-modal-cancel');
}

function getStartBtn() {
    return document.getElementById('upload-modal-start');
}

function getCloseBtn() {
    return document.getElementById('upload-modal-close');
}

// ============================================
// Upload Initialization
// ============================================

export function initFileUpload() {
    // Create hidden file input
    fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.mp4,.mkv,.avi,.mov,.webm,.m4v';
    fileInput.style.display = 'none';
    document.body.appendChild(fileInput);

    // Wire up attachment button
    const attachBtn = getAttachBtn();
    if (attachBtn) {
        attachBtn.addEventListener('click', () => {
            if (state.isProcessing) {
                showToast('Please wait for the current operation to complete', 'warning');
                return;
            }
            fileInput.click();
        });
    }

    // Handle file selection
    fileInput.addEventListener('change', handleFileSelect);

    // Wire up modal buttons
    initModalHandlers();
}

// ============================================
// Modal Handlers
// ============================================

function initModalHandlers() {
    const cancelBtn = getCancelBtn();
    const startBtn = getStartBtn();
    const closeBtn = getCloseBtn();
    const modal = getModal();

    if (cancelBtn) {
        cancelBtn.addEventListener('click', hideUploadModal);
    }

    if (startBtn) {
        startBtn.addEventListener('click', handleStartTranscription);
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', hideUploadModal);
    }

    // Close on backdrop click
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                hideUploadModal();
            }
        });
    }

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && getModal()?.classList.contains('flex')) {
            hideUploadModal();
        }
    });
}

// ============================================
// Modal Control
// ============================================

function showUploadModal(file) {
    const modal = getModal();
    const filenameEl = getFilenameEl();
    const filesizeEl = getFilesizeEl();
    const languageSelect = getLanguageSelect();
    const domainTextarea = getDomainTextarea();

    if (!modal) return;

    // Store pending file
    pendingFile = file;

    // Populate file info
    if (filenameEl) {
        filenameEl.textContent = file.name;
    }
    if (filesizeEl) {
        filesizeEl.textContent = formatFileSize(file.size);
    }

    // Reset form fields
    if (languageSelect) {
        languageSelect.value = '';
    }
    if (domainTextarea) {
        domainTextarea.value = '';
    }

    // Show modal with flex display
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    // Focus language dropdown (first form field for natural tab order)
    setTimeout(() => {
        languageSelect?.focus();
    }, 100);
}

function hideUploadModal() {
    const modal = getModal();
    if (!modal) return;

    modal.classList.add('hidden');
    modal.classList.remove('flex');

    // Clear pending file
    pendingFile = null;

    // Reset file input
    if (fileInput) {
        fileInput.value = '';
    }
}

// ============================================
// File Selection Handler
// ============================================

export async function handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    // Validate file size (500MB limit)
    const MAX_SIZE = 500 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
        showToast('File too large. Maximum size is 500MB.', 'error');
        fileInput.value = '';
        return;
    }

    // Show modal instead of immediately uploading
    showUploadModal(file);
}

// ============================================
// Start Transcription Handler
// ============================================

async function handleStartTranscription() {
    if (!pendingFile) {
        hideUploadModal();
        return;
    }

    // Capture file and clear immediately to prevent double-submit on rapid clicks
    const file = pendingFile;
    pendingFile = null;

    const languageSelect = getLanguageSelect();
    const domainTextarea = getDomainTextarea();

    // Get optional params before hiding modal
    const language = languageSelect?.value || '';
    const domain = domainTextarea?.value?.trim() || '';

    // Hide modal
    hideUploadModal();

    // Show upload message
    addMessage(`Uploading: ${file.name} (${formatFileSize(file.size)})...`, 'user');
    const loadingId = showLoading();

    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('session_id', state.sessionId);

        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        // Check response.ok before parsing JSON to handle non-JSON error responses
        if (!response.ok) {
            let errorMessage = 'Upload failed';
            try {
                const errorData = await response.json();
                errorMessage = errorData.error || errorData.detail || errorMessage;
            } catch {
                // Response wasn't JSON - use status text
                errorMessage = `Upload failed: ${response.status} ${response.statusText}`;
            }
            removeLoading(loadingId);
            showToast(errorMessage, 'error');
            addMessage(`**Upload Error:** ${errorMessage}`, 'agent');
            return;
        }

        const data = await response.json();
        removeLoading(loadingId);

        if (data.success) {
            showToast('File uploaded successfully', 'success');
            addMessage(`File uploaded successfully. Starting transcription...`, 'agent');

            // Construct message with optional params
            const filePath = `uploads/${state.sessionId}/${data.file_id}_${file.name}`;
            const message = buildTranscriptionMessage(filePath, language, domain);
            await sendMessage(message, false);
        } else {
            showToast(data.error || 'Upload failed', 'error');
            addMessage(`**Upload Error:** ${data.error || 'Unknown error'}`, 'agent');
        }
    } catch (e) {
        removeLoading(loadingId);
        showToast('Upload failed', 'error');
        addMessage(`**Upload Error:** ${e.message}`, 'agent');
    }
    // Note: fileInput is already reset by hideUploadModal()
}

// ============================================
// Message Construction
// ============================================

/**
 * Build a transcription request message with optional params.
 * Format provides structured context for the agent to extract parameters.
 */
function buildTranscriptionMessage(filePath, language, domain) {
    let message = `Please transcribe this uploaded video file: ${filePath}`;

    // Add language if specified
    if (language) {
        message += `\n\nLanguage: ${language}`;
    }

    // Add domain hints if specified
    if (domain) {
        message += `\n\nDomain/vocabulary hints: ${domain}`;
    }

    return message;
}
