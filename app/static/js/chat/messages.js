// ============================================
// Chat Messages Module
// Message rendering, markdown enhancement, and UI state
// ============================================

import { PURIFY_CONFIG } from '../core/config.js';
import { copyToClipboard } from '../core/utils.js';
import { showToast } from '../ui/toast.js';

// ============================================
// Element References (Lazy Lookup)
// ============================================

function getChatMessages() {
    return document.getElementById('chat-messages');
}

// ============================================
// Empty State Management
// ============================================

export function showEmptyState() {
    const chatMessages = getChatMessages();
    const emptyState = document.getElementById('empty-state');
    const messageContainer = chatMessages?.querySelector('div.space-y-6');
    if (emptyState) {
        emptyState.classList.remove('hidden');
    }
    if (messageContainer) {
        messageContainer.classList.add('hidden');
    }
}

export function hideEmptyState() {
    const chatMessages = getChatMessages();
    const emptyState = document.getElementById('empty-state');
    const messageContainer = chatMessages?.querySelector('div.space-y-6');
    if (emptyState) {
        emptyState.classList.add('hidden');
    }
    if (messageContainer) {
        messageContainer.classList.remove('hidden');
    }
}

// ============================================
// Scroll Management
// ============================================

export function scrollToBottom() {
    const chatMessages = getChatMessages();
    if (!chatMessages) return;
    const scrollHeight = chatMessages.scrollHeight;
    chatMessages.scrollTo({
        top: scrollHeight,
        behavior: 'smooth'
    });
}

// ============================================
// Usage Stats Formatting
// ============================================

export function formatUsageStats(usage) {
    if (!usage) return null;

    const totalTokens = (usage.input_tokens || 0) + (usage.output_tokens || 0);
    const cost = usage.total_cost_usd || 0;

    const costStr = cost < 0.01
        ? `$${cost.toFixed(4)}`
        : `$${cost.toFixed(2)}`;

    return {
        input: usage.input_tokens || 0,
        output: usage.output_tokens || 0,
        total: totalTokens,
        cost: costStr,
        cacheCreation: usage.cache_creation_tokens || 0,
        cacheRead: usage.cache_read_tokens || 0
    };
}

// ============================================
// Markdown Enhancement
// ============================================

export function enhanceMarkdown(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    // Process all code blocks
    const preTags = doc.querySelectorAll('pre');
    preTags.forEach(pre => {
        // Create wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'code-block-wrapper';

        // Wrap pre
        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(pre);

        // Add copy button (will be re-attached after innerHTML)
        const btn = document.createElement('button');
        btn.className = 'code-copy-btn';
        btn.setAttribute('data-copy-btn', 'true');
        btn.innerHTML = '<i class="ph-bold ph-copy"></i> Copy';
        wrapper.appendChild(btn);
    });

    return doc.body.innerHTML;
}

// ============================================
// Message Rendering
// ============================================

export function addMessage(text, sender, usage = null) {
    hideEmptyState();

    const isUser = sender === 'user';

    // Outer Container
    const container = document.createElement('div');
    container.className = isUser
        ? "flex items-start gap-4 flex-row-reverse"
        : "flex items-start gap-4";

    // Avatar
    const avatar = document.createElement('div');

    if (isUser) {
        avatar.className = "avatar avatar-user";
        avatar.innerHTML = `<span class="text-sm font-bold text-white">U</span>`;
    } else {
        avatar.className = "avatar avatar-agent";
        avatar.innerHTML = `<i class="ph-fill ph-robot text-lg" style="color: var(--accent-primary);"></i>`;
    }

    // Message Content Wrapper
    const contentWrapper = document.createElement('div');
    contentWrapper.className = "flex-1 min-w-0";

    // Bubble
    const bubble = document.createElement('div');

    if (isUser) {
        bubble.className = "message-user text-sm leading-relaxed";
        bubble.textContent = text;
    } else {
        bubble.className = "message-agent prose prose-sm max-w-none";

        // Sanitize and enhance markdown
        const safeHtml = DOMPurify.sanitize(marked.parse(text), PURIFY_CONFIG);
        bubble.innerHTML = enhanceMarkdown(safeHtml);

        // Re-attach copy button event listeners
        const copyBtns = bubble.querySelectorAll('[data-copy-btn]');
        copyBtns.forEach(btn => {
            btn.onclick = async () => {
                const pre = btn.parentElement.querySelector('pre');
                const code = pre.querySelector('code')?.innerText || pre.innerText;
                try {
                    await copyToClipboard(code);
                    btn.innerHTML = '<i class="ph-bold ph-check"></i> Copied!';
                    setTimeout(() => {
                        btn.innerHTML = '<i class="ph-bold ph-copy"></i> Copy';
                    }, 2000);
                } catch (err) {
                    console.error('Copy failed', err);
                    showToast('Failed to copy to clipboard', 'error');
                }
            };
        });
    }

    // Footer container
    const footer = document.createElement('div');
    footer.className = `flex items-center gap-3 mt-2 ${isUser ? 'flex-row-reverse mr-1' : 'ml-1'}`;

    // Timestamp
    const timestamp = document.createElement('span');
    timestamp.className = 'text-[10px] font-medium';
    timestamp.style.color = 'var(--text-muted)';
    timestamp.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    footer.appendChild(timestamp);

    // Usage Stats (for agent messages)
    if (!isUser && usage) {
        const stats = formatUsageStats(usage);
        if (stats) {
            const usageEl = document.createElement('span');
            usageEl.className = 'cost-badge';
            usageEl.innerHTML = `
                <i class="ph-fill ph-coins text-xs"></i>
                <span title="Total API cost for this session">${stats.cost}</span>
            `;
            footer.appendChild(usageEl);
        }
    }

    contentWrapper.appendChild(bubble);
    contentWrapper.appendChild(footer);

    container.appendChild(avatar);
    container.appendChild(contentWrapper);

    const chatMessages = getChatMessages();
    if (!chatMessages) return;

    let listContainer = chatMessages.querySelector('div.space-y-6');
    if (!listContainer) {
        listContainer = document.createElement('div');
        listContainer.className = "max-w-3xl mx-auto space-y-6";
        chatMessages.appendChild(listContainer);
    }
    listContainer.appendChild(container);

    scrollToBottom();
}

// ============================================
// Loading Indicator with Activity Streaming
// ============================================

export function showLoading() {
    const id = 'loading-' + Date.now();
    const container = document.createElement('div');
    container.id = id;
    container.className = "flex items-start gap-4";

    container.innerHTML = `
        <div class="avatar avatar-agent">
            <i class="ph-fill ph-robot text-lg" style="color: var(--accent-primary);"></i>
        </div>
        <div class="message-agent loading-bubble" style="padding: 16px 24px; min-width: 120px;">
            <div class="loading-content">
                <div class="loading-dots">
                    <div class="loading-dot"></div>
                    <div class="loading-dot"></div>
                    <div class="loading-dot"></div>
                </div>
                <div class="loading-activity hidden" style="display: none;">
                    <span class="activity-text text-sm" style="color: var(--text-secondary);"></span>
                </div>
            </div>
        </div>
    `;

    const chatMessages = getChatMessages();
    if (!chatMessages) return id;

    let listContainer = chatMessages.querySelector('div.space-y-6');
    if (!listContainer) {
         listContainer = document.createElement('div');
         listContainer.className = "max-w-3xl mx-auto space-y-6";
         chatMessages.appendChild(listContainer);
    }
    listContainer.appendChild(container);
    scrollToBottom();
    return id;
}

/**
 * Update the loading indicator with activity text
 * @param {string} loadingId - The loading element ID
 * @param {string} activityText - Activity message to display (with emoji)
 * @param {string|null} toolName - Optional tool name for context
 */
export function updateLoadingActivity(loadingId, activityText, toolName = null) {
    const container = document.getElementById(loadingId);
    if (!container) return;

    const dotsEl = container.querySelector('.loading-dots');
    const activityEl = container.querySelector('.loading-activity');
    const textEl = container.querySelector('.activity-text');

    if (!activityEl || !textEl) return;

    if (activityText) {
        // Hide dots, show activity text
        if (dotsEl) dotsEl.style.display = 'none';
        activityEl.style.display = 'flex';
        activityEl.classList.remove('hidden');

        // Update text with smooth transition
        textEl.style.opacity = '0';
        setTimeout(() => {
            textEl.textContent = activityText;
            textEl.style.opacity = '1';
        }, 100);

        scrollToBottom();
    } else {
        // Show dots, hide activity
        if (dotsEl) dotsEl.style.display = 'flex';
        activityEl.style.display = 'none';
        activityEl.classList.add('hidden');
    }
}

export function removeLoading(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}
