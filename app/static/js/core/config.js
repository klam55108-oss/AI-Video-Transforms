// ============================================
// Configuration Constants and Server Config
// ============================================

// Retry configuration
export const MAX_RETRIES = 2;
export const RETRY_DELAY_MS = 1000;

// Storage keys
export const THEME_STORAGE_KEY = 'videoagent-theme';
export const KG_PROJECT_STORAGE_KEY = 'kg_current_project';
export const KG_VIEW_STORAGE_KEY = 'kg_current_view';

// DOMPurify configuration for safe markdown rendering
export const PURIFY_CONFIG = {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li',
                   'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'a', 'table',
                   'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'span', 'div'],
    ALLOWED_ATTR: ['href', 'class', 'target', 'rel'],
    ALLOW_DATA_ATTR: false
};

// Poll intervals from server config (with fallbacks)
export function getKGPollInterval() {
    return window.APP_CONFIG?.KG_POLL_INTERVAL_MS || 5000;
}

export function getStatusPollInterval() {
    return window.APP_CONFIG?.STATUS_POLL_INTERVAL_MS || 3000;
}

export function getJobPollInterval() {
    return window.APP_CONFIG?.JOB_POLL_INTERVAL_MS || 1000;
}
