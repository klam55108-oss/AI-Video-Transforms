// Knowledge Graph API Client
// ============================================

import { showToast } from '../ui/toast.js';

/**
 * Handle KG API errors consistently with unified error schema.
 * Distinguishes network errors from server errors for better user feedback.
 * Parses APIError schema with code, message, detail, hint, and retryable fields.
 */
async function handleKGApiError(response, defaultMessage) {
    // Network error or server unavailable
    if (!response) {
        throw new Error('Network error. Please check your connection and try again.');
    }

    // Try to parse structured error details from response
    let errorMessage = defaultMessage;
    let errorHint = null;
    let errorCode = null;
    let isRetryable = false;

    try {
        const errorData = await response.json();

        // New unified error schema format
        if (errorData.error) {
            const error = errorData.error;
            errorCode = error.code;
            errorMessage = error.message || defaultMessage;
            errorHint = error.hint;
            isRetryable = error.retryable || false;

            // Append detail to message if available (for debugging)
            if (error.detail && error.detail !== errorMessage) {
                errorMessage = `${errorMessage}: ${error.detail}`;
            }
        }
        // Legacy format fallback (for backward compatibility)
        else if (errorData.detail) {
            errorMessage = errorData.detail;
        }
    } catch {
        // Response wasn't JSON, use default message
    }

    // Add status code context for debugging if we don't have structured error
    if (!errorCode) {
        if (response.status === 503) {
            errorMessage = 'Server is busy. Please try again in a moment.';
            isRetryable = true;
        } else if (response.status === 500) {
            errorMessage = 'Server error. Please try again later.';
            isRetryable = true;
        }
    }

    // Create error with hint attached for display
    const error = new Error(errorMessage);
    error.hint = errorHint;
    error.code = errorCode;
    error.retryable = isRetryable;
    throw error;
}

const kgClient = {
    async listProjects() {
        try {
            const response = await fetch('/kg/projects');
            if (!response.ok) {
                await handleKGApiError(response, 'Failed to load projects');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Please check your connection.');
            }
            throw e;
        }
    },

    async createProject(name) {
        try {
            const response = await fetch('/kg/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });
            if (!response.ok) {
                await handleKGApiError(response, 'Failed to create project');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Could not create project.');
            }
            throw e;
        }
    },

    async getProject(projectId) {
        try {
            const response = await fetch(`/kg/projects/${projectId}`);
            if (response.status === 404) return null;
            if (!response.ok) {
                await handleKGApiError(response, 'Failed to load project');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Could not load project.');
            }
            throw e;
        }
    },

    async getConfirmations(projectId) {
        try {
            const response = await fetch(`/kg/projects/${projectId}/confirmations`);
            if (!response.ok) {
                await handleKGApiError(response, 'Failed to load confirmations');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Could not load confirmations.');
            }
            throw e;
        }
    },

    async confirmDiscovery(projectId, discoveryId, confirmed) {
        try {
            const response = await fetch(`/kg/projects/${projectId}/confirm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ discovery_id: discoveryId, confirmed })
            });
            if (!response.ok) {
                await handleKGApiError(response, 'Confirmation failed');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Could not confirm discovery.');
            }
            throw e;
        }
    },

    async getGraphStats(projectId) {
        try {
            const response = await fetch(`/kg/projects/${projectId}/graph`);
            if (response.status === 404) return null;
            if (!response.ok) {
                await handleKGApiError(response, 'Failed to load graph statistics');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Could not load statistics.');
            }
            throw e;
        }
    },

    async exportGraph(projectId, format) {
        try {
            const response = await fetch(`/kg/projects/${projectId}/export`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ format })
            });
            if (!response.ok) {
                await handleKGApiError(response, 'Export failed');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Could not export graph.');
            }
            throw e;
        }
    },

    async deleteProject(projectId) {
        try {
            const response = await fetch(`/kg/projects/${projectId}`, {
                method: 'DELETE'
            });
            if (!response.ok) {
                await handleKGApiError(response, 'Failed to delete project');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Could not delete project.');
            }
            throw e;
        }
    },

    async batchExportProjects(projectIds, format) {
        try {
            const response = await fetch('/kg/projects/batch-export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_ids: projectIds, format })
            });
            if (!response.ok) {
                await handleKGApiError(response, 'Batch export failed');
            }
            return response.json();
        } catch (e) {
            if (e.name === 'TypeError') {
                throw new Error('Network error. Could not export projects.');
            }
            throw e;
        }
    }
};

export { handleKGApiError, kgClient };
