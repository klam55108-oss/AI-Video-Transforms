// ============================================
// Toast Notifications
// ============================================

import { escapeHtml, copyToClipboard } from '../core/utils.js';

// Toast container initialization
let toastContainer = null;

export function initToastContainer() {
    toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container';
        document.body.appendChild(toastContainer);
    }
}

export function showToast(message, type = 'info', options = {}) {
    const { hint = null, code = null, detail = null } = options;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const iconMap = {
        'info': 'ph-info',
        'success': 'ph-check-circle',
        'error': 'ph-warning-circle',
        'warning': 'ph-warning'
    };

    const iconClass = iconMap[type] || 'ph-info';

    // Build toast content
    let toastContent = `
        <div class="flex items-start gap-3 flex-1">
            <i class="ph-fill ${iconClass} text-lg opacity-80 mt-0.5"></i>
            <div class="flex-1 min-w-0">
                <div class="text-sm font-medium">${escapeHtml(message)}</div>
    `;

    // Add hint if available
    if (hint) {
        toastContent += `
                <div class="text-xs mt-1 opacity-75">
                    <i class="ph-bold ph-lightbulb text-xs mr-1"></i>${escapeHtml(hint)}
                </div>
        `;
    }

    toastContent += `
            </div>
        </div>
    `;

    // Add action buttons container
    toastContent += `<div class="flex items-center gap-2 ml-2">`;

    // Add "Copy Debug Info" button for errors with code
    if (type === 'error' && (code || detail)) {
        toastContent += `
            <button class="copy-debug-btn opacity-60 hover:opacity-100 transition-opacity text-xs px-2 py-1 rounded hover:bg-black/10" title="Copy debug info">
                <i class="ph-bold ph-copy text-sm"></i>
            </button>
        `;
    }

    // Close button
    toastContent += `
            <button class="close-btn opacity-60 hover:opacity-100 transition-opacity">
                <i class="ph-bold ph-x"></i>
            </button>
        </div>
    `;

    toast.innerHTML = toastContent;

    // Close button handler
    const closeBtn = toast.querySelector('.close-btn');
    if (closeBtn) {
        closeBtn.onclick = () => {
            toast.style.animation = 'toastFadeOut 0.2s forwards';
            setTimeout(() => toast.remove(), 200);
        };
    }

    // Copy debug info handler
    const copyBtn = toast.querySelector('.copy-debug-btn');
    if (copyBtn) {
        copyBtn.onclick = async () => {
            const debugInfo = {
                message,
                code,
                detail,
                timestamp: new Date().toISOString()
            };
            const debugText = JSON.stringify(debugInfo, null, 2);

            try {
                await copyToClipboard(debugText);
                copyBtn.innerHTML = '<i class="ph-bold ph-check text-sm"></i>';
                setTimeout(() => {
                    copyBtn.innerHTML = '<i class="ph-bold ph-copy text-sm"></i>';
                }, 1500);
            } catch (err) {
                console.error('Failed to copy debug info:', err);
            }
        };
    }

    toastContainer.appendChild(toast);

    // Auto dismiss after 4 seconds (6 seconds for errors with hints)
    const dismissDelay = (type === 'error' && hint) ? 6000 : 4000;
    setTimeout(() => {
        if (toast.isConnected) {
            toast.style.animation = 'toastFadeOut 0.2s forwards';
            setTimeout(() => toast.remove(), 200);
        }
    }, dismissDelay);
}
