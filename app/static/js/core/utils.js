// ============================================
// Utility Functions
// ============================================

export function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

export function formatRelativeTime(isoString) {
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

export function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Format duration in seconds for human readability.
 * Converts milliseconds to a readable seconds format with adaptive precision.
 *
 * @param {number} durationMs - Duration in milliseconds
 * @returns {string} Formatted duration (e.g., "0s", "<0.01s", "0.05s", "1.2s", "15s")
 *
 * @example
 * formatDuration(0)      // → '0s'
 * formatDuration(5)      // → '<0.01s'
 * formatDuration(50)     // → '0.05s'
 * formatDuration(1234)   // → '1.2s'
 * formatDuration(15000)  // → '15s'
 */
export function formatDuration(durationMs) {
    if (durationMs === null || durationMs === undefined) return '';

    // Zero is a valid duration (instant/cached operations)
    if (durationMs === 0) return '0s';

    const seconds = durationMs / 1000;

    // For sub-10ms durations, show "<0.01s" rather than misleading "0.00s"
    if (seconds < 0.01) {
        return '<0.01s';
    }
    // For durations 10-99ms, show two decimals (e.g., "0.05s")
    if (seconds < 0.1) {
        return `${seconds.toFixed(2)}s`;
    }
    // For durations 100ms-10s, show one decimal (e.g., "1.2s")
    if (seconds < 10) {
        return `${seconds.toFixed(1)}s`;
    }
    // For longer durations, show whole seconds (e.g., "15s")
    return `${Math.round(seconds)}s`;
}

export function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        return navigator.clipboard.writeText(text);
    } else {
        // Fallback for non-secure context
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-9999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            document.execCommand('copy');
            return Promise.resolve();
        } catch (err) {
            return Promise.reject(err);
        } finally {
            document.body.removeChild(textArea);
        }
    }
}
