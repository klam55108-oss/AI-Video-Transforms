// ============================================
// Jobs Module
// Background job progress tracking and UI
// ============================================

import { getJobPollInterval } from '../core/config.js';
import { escapeHtml } from '../core/utils.js';
import { showToast } from '../ui/toast.js';

// ============================================
// Element References (Lazy Lookup)
// ============================================

function getChatMessages() {
    return document.getElementById('chat-messages');
}

function getJobsList() {
    return document.getElementById('jobs-list');
}

function getJobsToggle() {
    return document.getElementById('jobs-toggle');
}

function getJobsCaret() {
    return document.getElementById('jobs-caret');
}

function getJobsCountBadge() {
    return document.getElementById('jobs-count-badge');
}

function getJobsEmpty() {
    return document.getElementById('jobs-empty');
}

// ============================================
// Job State
// ============================================

let jobProgressPollers = new Map();
let sidebarJobPollers = new Map();
let sidebarPollInterval = null;
let isPanelOpen = false;

// Track last known job statuses to detect completion
let lastKnownJobStatuses = new Map();

// ============================================
// Stage Labels
// ============================================

const STAGE_LABELS = {
    'queued': 'Queued',
    'downloading': 'Downloading video',
    'extracting_audio': 'Extracting audio',
    'transcribing': 'Transcribing',
    'processing': 'Processing',
    'finalizing': 'Finalizing'
};

// ============================================
// Job Progress UI
// ============================================

export function createJobProgressUI(jobId, title = 'Processing') {
    const container = document.createElement('div');
    container.id = `job-progress-${jobId}`;
    container.className = 'job-progress-container';
    container.innerHTML = `
        <div class="job-progress-header">
            <div class="job-progress-title">
                <i class="ph-fill ph-spinner animate-spin"></i>
                <span>${escapeHtml(title)}</span>
            </div>
            <button class="job-progress-cancel" data-job-id="${jobId}">
                <i class="ph-bold ph-x-circle"></i> Cancel
            </button>
        </div>
        <div class="job-progress-bar-container">
            <div class="job-progress-bar animated" style="width: 0%"></div>
        </div>
        <div class="job-progress-info">
            <span class="job-progress-stage">Initializing...</span>
            <span class="job-progress-percent">0%</span>
        </div>
    `;

    const cancelBtn = container.querySelector('.job-progress-cancel');
    cancelBtn?.addEventListener('click', () => cancelJob(jobId));

    const chatMessages = getChatMessages();
    const messageContainer = chatMessages?.querySelector('div.space-y-6');
    if (messageContainer && chatMessages) {
        messageContainer.appendChild(container);
        // Scroll to bottom
        const scrollHeight = chatMessages.scrollHeight;
        chatMessages.scrollTo({
            top: scrollHeight,
            behavior: 'smooth'
        });
    }

    startJobPolling(jobId);

    return jobId;
}

// ============================================
// Job Polling
// ============================================

export async function startJobPolling(jobId) {
    if (jobProgressPollers.has(jobId)) {
        return;
    }

    const pollerId = setInterval(() => updateJobProgress(jobId), getJobPollInterval());
    jobProgressPollers.set(jobId, pollerId);

    await updateJobProgress(jobId);
}

export function stopJobPolling(jobId) {
    const pollerId = jobProgressPollers.get(jobId);
    if (pollerId) {
        clearInterval(pollerId);
        jobProgressPollers.delete(jobId);
    }
}

export async function updateJobProgress(jobId) {
    try {
        const response = await fetch(`/jobs/${jobId}`);

        if (!response.ok) {
            if (response.status === 404) {
                stopJobPolling(jobId);
                return;
            }
            throw new Error('Failed to fetch job status');
        }

        const job = await response.json();
        renderJobProgress(job);

        if (job.status === 'completed' || job.status === 'failed') {
            stopJobPolling(jobId);
            setTimeout(() => {
                const container = document.getElementById(`job-progress-${jobId}`);
                if (container) {
                    container.style.opacity = '0';
                    container.style.transform = 'translateY(-10px)';
                    container.style.transition = 'all 0.3s ease';
                    setTimeout(() => container.remove(), 300);
                }
            }, 3000);

            if (job.status === 'completed') {
                // Refresh transcripts list if available
                if (window.loadTranscripts && typeof window.loadTranscripts === 'function') {
                    window.loadTranscripts();
                }

                // Auto-continue conversation: notify agent that job completed
                // This allows the agent to show the result and offer next steps
                triggerJobCompletionCallback(job);
            } else if (job.status === 'failed') {
                // Notify agent of failure so it can suggest alternatives
                triggerJobFailureCallback(job);
            }
        }

    } catch (e) {
        console.error('Job progress update failed:', e);
    }
}

export function renderJobProgress(job) {
    const container = document.getElementById(`job-progress-${job.id}`);
    if (!container) return;

    const progressBar = container.querySelector('.job-progress-bar');
    const stageEl = container.querySelector('.job-progress-stage');
    const percentEl = container.querySelector('.job-progress-percent');
    const cancelBtn = container.querySelector('.job-progress-cancel');

    if (progressBar) {
        progressBar.style.width = `${job.progress}%`;
        if (job.status === 'running') {
            progressBar.classList.add('animated');
        } else {
            progressBar.classList.remove('animated');
        }
    }

    if (stageEl) {
        stageEl.textContent = STAGE_LABELS[job.stage] || job.stage;
    }

    if (percentEl) {
        percentEl.textContent = `${job.progress}%`;
    }

    if (cancelBtn) {
        cancelBtn.disabled = job.status !== 'pending' && job.status !== 'running';
    }

    if (job.status === 'completed') {
        const existingStatus = container.querySelector('.job-progress-status');
        if (!existingStatus) {
            const statusDiv = document.createElement('div');
            statusDiv.className = 'job-progress-status success';
            statusDiv.innerHTML = '<i class="ph-fill ph-check-circle"></i><span>Completed successfully</span>';
            container.appendChild(statusDiv);
        }
    } else if (job.status === 'failed') {
        const existingStatus = container.querySelector('.job-progress-status');
        if (!existingStatus) {
            const statusDiv = document.createElement('div');
            statusDiv.className = 'job-progress-status error';
            const errorMsg = job.error || 'Job failed';
            statusDiv.innerHTML = `<i class="ph-fill ph-x-circle"></i><span>${escapeHtml(errorMsg)}</span>`;
            container.appendChild(statusDiv);
        }
    }
}

// ============================================
// Job Cancellation
// ============================================

export async function cancelJob(jobId) {
    if (!confirm('Cancel this job?')) return;

    try {
        const response = await fetch(`/jobs/${jobId}`, { method: 'DELETE' });

        if (!response.ok) {
            throw new Error('Failed to cancel job');
        }

        stopJobPolling(jobId);

        const container = document.getElementById(`job-progress-${jobId}`);
        if (container) {
            const statusDiv = document.createElement('div');
            statusDiv.className = 'job-progress-status cancelled';
            statusDiv.innerHTML = '<i class="ph-fill ph-warning-circle"></i><span>Cancelled</span>';
            container.appendChild(statusDiv);

            setTimeout(() => {
                container.style.opacity = '0';
                container.style.transform = 'translateY(-10px)';
                container.style.transition = 'all 0.3s ease';
                setTimeout(() => container.remove(), 300);
            }, 2000);
        }

        showToast('Job cancelled', 'info');

    } catch (e) {
        console.error('Cancel job failed:', e);
        showToast('Failed to cancel job', 'error');
    }
}

// ============================================
// Sidebar Panel Functions
// ============================================

export function toggleJobsPanel() {
    const jobsList = getJobsList();
    const caret = getJobsCaret();

    if (!jobsList) return;

    isPanelOpen = !isPanelOpen;

    if (isPanelOpen) {
        jobsList.classList.add('open');
        caret?.classList.add('rotate-90');
        loadJobs();
        startSidebarPolling();
    } else {
        jobsList.classList.remove('open');
        caret?.classList.remove('rotate-90');
        stopSidebarPolling();
    }
}

export async function loadJobs() {
    const jobsList = getJobsList();
    const emptyEl = getJobsEmpty();
    const badge = getJobsCountBadge();

    if (!jobsList) return;

    try {
        const response = await fetch('/jobs');
        if (!response.ok) throw new Error('Failed to fetch jobs');

        const data = await response.json();
        const jobs = data.jobs || [];

        // Check for job completion transitions and trigger callbacks
        for (const job of jobs) {
            const lastStatus = lastKnownJobStatuses.get(job.id);
            if (lastStatus && lastStatus !== job.status) {
                // Status changed - check if it's a completion
                if (job.status === 'completed') {
                    console.log(`Sidebar detected job ${job.id} completed`);
                    triggerJobCompletionCallback(job);
                } else if (job.status === 'failed') {
                    console.log(`Sidebar detected job ${job.id} failed`);
                    triggerJobFailureCallback(job);
                }
            }
            lastKnownJobStatuses.set(job.id, job.status);
        }

        // Filter to show only active jobs (pending or running)
        const activeJobs = jobs.filter(j => j.status === 'pending' || j.status === 'running');

        // Update badge
        if (badge) {
            if (activeJobs.length > 0) {
                badge.textContent = activeJobs.length.toString();
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }

        // Show empty state if no jobs
        if (jobs.length === 0) {
            if (emptyEl) {
                emptyEl.classList.remove('hidden');
                emptyEl.textContent = 'No active jobs';
            }
            // Clear any existing job items (but keep the empty message)
            const existingItems = jobsList.querySelectorAll('.sidebar-job-item');
            existingItems.forEach(item => item.remove());
            return;
        }

        // Hide empty state
        if (emptyEl) {
            emptyEl.classList.add('hidden');
        }

        // Render job items
        renderJobsSidebar(jobs);

    } catch (e) {
        console.error('Failed to load jobs:', e);
        if (emptyEl) {
            emptyEl.textContent = 'Failed to load jobs';
            emptyEl.classList.remove('hidden');
        }
    }
}

function renderJobsSidebar(jobs) {
    const jobsList = getJobsList();
    if (!jobsList) return;

    // Keep track of existing items to avoid flicker
    const existingIds = new Set();
    jobsList.querySelectorAll('.sidebar-job-item').forEach(el => {
        existingIds.add(el.dataset.jobId);
    });

    // Add or update job items
    jobs.forEach(job => {
        let item = jobsList.querySelector(`.sidebar-job-item[data-job-id="${job.id}"]`);

        if (!item) {
            item = createSidebarJobItem(job);
            jobsList.appendChild(item);
        } else {
            updateSidebarJobItem(item, job);
        }
    });

    // Remove jobs that no longer exist
    const currentIds = new Set(jobs.map(j => j.id));
    jobsList.querySelectorAll('.sidebar-job-item').forEach(el => {
        if (!currentIds.has(el.dataset.jobId)) {
            el.remove();
        }
    });
}

function createSidebarJobItem(job) {
    const item = document.createElement('div');
    item.className = 'sidebar-job-item';
    item.dataset.jobId = job.id;

    const statusIcon = getStatusIcon(job.status);
    const stageLabel = STAGE_LABELS[job.stage] || job.stage;

    item.innerHTML = `
        <div class="sidebar-job-header">
            <span class="sidebar-job-icon">${statusIcon}</span>
            <span class="sidebar-job-type">${escapeHtml(job.type)}</span>
            ${job.status === 'pending' || job.status === 'running' ? `
                <button class="sidebar-job-cancel" onclick="cancelJob('${job.id}')" title="Cancel job">
                    <i class="ph-bold ph-x text-xs"></i>
                </button>
            ` : ''}
        </div>
        <div class="sidebar-job-progress">
            <div class="sidebar-job-progress-bar ${job.status === 'running' ? 'animated' : ''}" style="width: ${job.progress}%"></div>
        </div>
        <div class="sidebar-job-info">
            <span class="sidebar-job-stage">${escapeHtml(stageLabel)}</span>
            <span class="sidebar-job-percent">${job.progress}%</span>
        </div>
        ${job.status === 'failed' && job.error ? `
            <div class="sidebar-job-error">${escapeHtml(job.error)}</div>
        ` : ''}
    `;

    return item;
}

function updateSidebarJobItem(item, job) {
    const iconEl = item.querySelector('.sidebar-job-icon');
    const progressBar = item.querySelector('.sidebar-job-progress-bar');
    const stageEl = item.querySelector('.sidebar-job-stage');
    const percentEl = item.querySelector('.sidebar-job-percent');

    if (iconEl) {
        iconEl.innerHTML = getStatusIcon(job.status);
    }

    if (progressBar) {
        progressBar.style.width = `${job.progress}%`;
        if (job.status === 'running') {
            progressBar.classList.add('animated');
        } else {
            progressBar.classList.remove('animated');
        }
    }

    if (stageEl) {
        stageEl.textContent = STAGE_LABELS[job.stage] || job.stage;
    }

    if (percentEl) {
        percentEl.textContent = `${job.progress}%`;
    }

    // Update or add error message
    let errorEl = item.querySelector('.sidebar-job-error');
    if (job.status === 'failed' && job.error) {
        if (!errorEl) {
            errorEl = document.createElement('div');
            errorEl.className = 'sidebar-job-error';
            item.appendChild(errorEl);
        }
        errorEl.textContent = job.error;
    } else if (errorEl) {
        errorEl.remove();
    }

    // Update cancel button visibility
    const cancelBtn = item.querySelector('.sidebar-job-cancel');
    if (cancelBtn) {
        cancelBtn.style.display = (job.status === 'pending' || job.status === 'running') ? '' : 'none';
    }
}

function getStatusIcon(status) {
    switch (status) {
        case 'pending':
            return '<i class="ph-fill ph-clock text-[var(--text-muted)]"></i>';
        case 'running':
            return '<i class="ph-fill ph-spinner animate-spin text-[var(--accent-primary)]"></i>';
        case 'completed':
            return '<i class="ph-fill ph-check-circle text-[var(--status-success)]"></i>';
        case 'failed':
            return '<i class="ph-fill ph-x-circle text-[var(--status-error)]"></i>';
        default:
            return '<i class="ph-fill ph-circle text-[var(--text-muted)]"></i>';
    }
}

function startSidebarPolling() {
    if (sidebarPollInterval) return;

    sidebarPollInterval = setInterval(() => {
        if (isPanelOpen) {
            loadJobs();
        }
    }, getJobPollInterval());
}

function stopSidebarPolling() {
    if (sidebarPollInterval) {
        clearInterval(sidebarPollInterval);
        sidebarPollInterval = null;
    }
}

// ============================================
// Job Completion Callbacks
// ============================================

// Track jobs that have already triggered callbacks to prevent duplicates
const completedJobCallbacks = new Set();

/**
 * Trigger agent callback when a job completes successfully
 * @param {Object} job - The completed job object
 */
function triggerJobCompletionCallback(job) {
    // Prevent duplicate callbacks
    if (completedJobCallbacks.has(job.id)) {
        return;
    }
    completedJobCallbacks.add(job.id);

    // Don't trigger if sendMessage isn't available
    if (typeof window.sendMessage !== 'function') {
        console.warn('sendMessage not available for job completion callback');
        return;
    }

    // Build a natural message to continue the conversation
    let message;
    if (job.type === 'transcription') {
        message = `The transcription job has completed successfully. Please show me the transcript and let me know what I can do with it (save it, create a knowledge graph, etc.).`;
    } else {
        message = `The background job "${job.type}" has completed successfully. Please show me the result and what options I have next.`;
    }

    // Send the message but don't show it as a user message (internal trigger)
    // Using false for showInUI so it appears seamless
    console.log(`Job ${job.id} completed, triggering agent continuation`);
    window.sendMessage(message, false);
}

/**
 * Trigger agent callback when a job fails
 * @param {Object} job - The failed job object
 */
function triggerJobFailureCallback(job) {
    // Prevent duplicate callbacks
    if (completedJobCallbacks.has(job.id)) {
        return;
    }
    completedJobCallbacks.add(job.id);

    // Don't trigger if sendMessage isn't available
    if (typeof window.sendMessage !== 'function') {
        console.warn('sendMessage not available for job failure callback');
        return;
    }

    const errorMsg = job.error || 'Unknown error';
    const message = `The ${job.type} job failed with error: "${errorMsg}". What should I do? Can you suggest alternatives or help me troubleshoot?`;

    console.log(`Job ${job.id} failed, triggering agent error handling`);
    window.sendMessage(message, false);
}

// ============================================
// Cleanup
// ============================================

export function cleanupAllJobPollers() {
    jobProgressPollers.forEach((pollerId) => clearInterval(pollerId));
    jobProgressPollers.clear();
    stopSidebarPolling();
    completedJobCallbacks.clear();
    lastKnownJobStatuses.clear();
}
