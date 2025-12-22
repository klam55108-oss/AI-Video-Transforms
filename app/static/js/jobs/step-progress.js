// ============================================
// Step-Based Progress Indicator
// Visual step indicator for job progress tracking
// ============================================

import { escapeHtml } from '../core/utils.js';

// ============================================
// Job Stage Definitions
// ============================================

const JOB_STEPS = {
    transcription: [
        { stage: 'queued', label: 'Queued' },
        { stage: 'downloading', label: 'Download' },
        { stage: 'extracting_audio', label: 'Extract' },
        { stage: 'transcribing', label: 'Transcribe' },
        { stage: 'processing', label: 'Process' },
        { stage: 'finalizing', label: 'Finalize' }
    ],
    bootstrap: [
        { stage: 'queued', label: 'Queued' },
        { stage: 'processing', label: 'Analyzing' },
        { stage: 'finalizing', label: 'Complete' }
    ],
    extraction: [
        { stage: 'queued', label: 'Queued' },
        { stage: 'processing', label: 'Extracting' },
        { stage: 'finalizing', label: 'Complete' }
    ]
};

// Stage labels for detailed status text
const STAGE_LABELS = {
    'queued': 'Queued',
    'downloading': 'Downloading video',
    'extracting_audio': 'Extracting audio',
    'transcribing': 'Transcribing',
    'processing': 'Processing',
    'finalizing': 'Finalizing'
};

// ============================================
// Step Progress Rendering
// ============================================

export function renderStepProgress(job) {
    const steps = getJobSteps(job.type);
    const currentStepIndex = getCurrentStepIndex(job.stage, steps);

    const stepsHTML = steps.map((step, index) => {
        const isCompleted = index < currentStepIndex;
        const isActive = index === currentStepIndex;

        const dotClass = isActive ? 'active' : (isCompleted ? 'completed' : '');
        const lineClass = isCompleted ? 'completed' : '';

        return `
            <div class="step-dot ${dotClass}" title="${escapeHtml(step.label)}"></div>
            ${index < steps.length - 1 ? `<div class="step-line ${lineClass}"></div>` : ''}
        `;
    }).join('');

    return `
        <div class="step-progress" title="${job.progress}% complete">
            ${stepsHTML}
        </div>
        <div class="step-label">
            ${escapeHtml(getCurrentStepLabel(job.stage))}
            ${job.stage === 'transcribing' && job.metadata?.current_chunk ?
                `<span class="step-segment">(chunk ${job.metadata.current_chunk}/${job.metadata.total_chunks})</span>` :
                ''}
        </div>
    `;
}

// ============================================
// Step Resolution
// ============================================

export function getJobSteps(jobType) {
    return JOB_STEPS[jobType] || JOB_STEPS.transcription;
}

export function getCurrentStepIndex(stage, steps) {
    const index = steps.findIndex(s => s.stage === stage);
    return index >= 0 ? index : 0;
}

export function getCurrentStepLabel(stage) {
    return STAGE_LABELS[stage] || stage;
}

// ============================================
// Sidebar Step Progress (Compact)
// ============================================

export function renderSidebarStepProgress(job) {
    const steps = getJobSteps(job.type);
    const currentStepIndex = getCurrentStepIndex(job.stage, steps);

    const dotsHTML = steps.map((step, index) => {
        const isCompleted = index < currentStepIndex;
        const isActive = index === currentStepIndex;

        const dotClass = isActive ? 'active' : (isCompleted ? 'completed' : '');

        return `<div class="sidebar-step-dot ${dotClass}" title="${escapeHtml(step.label)}"></div>`;
    }).join('');

    return `
        <div class="sidebar-step-progress" title="${job.progress}% complete">
            ${dotsHTML}
        </div>
    `;
}
