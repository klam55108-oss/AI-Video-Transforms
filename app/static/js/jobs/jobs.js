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

// ============================================
// Job State
// ============================================

let jobProgressPollers = new Map();

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
// Cleanup
// ============================================

export function cleanupAllJobPollers() {
    jobProgressPollers.forEach((pollerId) => clearInterval(pollerId));
    jobProgressPollers.clear();
}
