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

// ============================================
// Entity Resolution API Functions
// ============================================

/**
 * Scan a project for potential duplicate entities.
 * @param {string} projectId - The project ID
 * @returns {Promise<{candidates: ResolutionCandidate[]}>}
 */
async function scanForDuplicates(projectId) {
    try {
        const response = await fetch(`/kg/projects/${projectId}/duplicates`);
        if (!response.ok) {
            await handleKGApiError(response, 'Failed to scan for duplicates');
        }
        return response.json();
    } catch (e) {
        if (e.name === 'TypeError') {
            throw new Error('Network error. Could not scan for duplicates.');
        }
        throw e;
    }
}

/**
 * Merge two entities, keeping the survivor and absorbing the merged entity.
 * @param {string} projectId - The project ID
 * @param {string} survivorId - The entity to keep
 * @param {string} mergedId - The entity to merge into survivor
 * @returns {Promise<MergeHistory>}
 */
async function mergeEntities(projectId, survivorId, mergedId) {
    try {
        const response = await fetch(`/kg/projects/${projectId}/merge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ survivor_id: survivorId, merged_id: mergedId })
        });
        if (!response.ok) {
            await handleKGApiError(response, 'Failed to merge entities');
        }
        return response.json();
    } catch (e) {
        if (e.name === 'TypeError') {
            throw new Error('Network error. Could not merge entities.');
        }
        throw e;
    }
}

/**
 * Get all pending merge candidates for a project.
 * @param {string} projectId - The project ID
 * @returns {Promise<{candidates: ResolutionCandidate[]}>}
 */
async function getPendingMerges(projectId) {
    try {
        const response = await fetch(`/kg/projects/${projectId}/merge-candidates`);
        if (!response.ok) {
            await handleKGApiError(response, 'Failed to get pending merges');
        }
        return response.json();
    } catch (e) {
        if (e.name === 'TypeError') {
            throw new Error('Network error. Could not get pending merges.');
        }
        throw e;
    }
}

/**
 * Review a merge candidate (approve or reject).
 * @param {string} projectId - The project ID
 * @param {string} candidateId - The candidate ID
 * @param {boolean} approved - Whether to approve the merge
 * @returns {Promise<{success: boolean}>}
 */
async function reviewMergeCandidate(projectId, candidateId, approved) {
    try {
        const response = await fetch(`/kg/projects/${projectId}/merge-candidates/${candidateId}/review`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ approved })
        });
        if (!response.ok) {
            await handleKGApiError(response, 'Failed to review merge candidate');
        }
        return response.json();
    } catch (e) {
        if (e.name === 'TypeError') {
            throw new Error('Network error. Could not review merge candidate.');
        }
        throw e;
    }
}

/**
 * Get merge history for a project.
 * @param {string} projectId - The project ID
 * @returns {Promise<{history: MergeHistory[]}>}
 */
async function getMergeHistory(projectId) {
    try {
        const response = await fetch(`/kg/projects/${projectId}/merge-history`);
        if (!response.ok) {
            await handleKGApiError(response, 'Failed to get merge history');
        }
        return response.json();
    } catch (e) {
        if (e.name === 'TypeError') {
            throw new Error('Network error. Could not get merge history.');
        }
        throw e;
    }
}

export {
    handleKGApiError,
    kgClient,
    scanForDuplicates,
    mergeEntities,
    getPendingMerges,
    reviewMergeCandidate,
    getMergeHistory
};
