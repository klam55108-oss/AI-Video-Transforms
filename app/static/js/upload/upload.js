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

// ============================================
// Element References (Lazy Lookup)
// ============================================

function getAttachBtn() {
    return document.getElementById('attach-btn');
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

            // Trigger transcription request using session-specific upload directory
            const message = `Please transcribe this uploaded video file: uploads/${state.sessionId}/${data.file_id}_${file.name}`;
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

    // Reset file input
    fileInput.value = '';
}
