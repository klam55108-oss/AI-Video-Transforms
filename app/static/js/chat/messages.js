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
// Loading Indicator with Neural Activity Streaming
// Enhanced "Command Center" aesthetic
// ============================================

/** @type {Map<string, string[]>} */
const activityHistories = new Map();

/** Maximum number of timeline items to show */
const MAX_TIMELINE_ITEMS = 3;

/**
 * Get the icon class for an activity type
 * @param {string} activityType - The activity type
 * @returns {string} Phosphor icon class
 */
function getActivityIconClass(activityType) {
    switch (activityType) {
        case 'thinking':
            return 'ph-bold ph-brain';
        case 'tool_use':
            return 'ph-bold ph-wrench';
        case 'tool_result':
            return 'ph-bold ph-check-circle';
        case 'subagent':
            return 'ph-bold ph-users-three';
        case 'file_save':
            return 'ph-bold ph-floppy-disk';
        case 'completed':
            return 'ph-bold ph-sparkle';
        default:
            return 'ph-bold ph-circle-notch';
    }
}

/**
 * Get human-readable label for activity type
 * @param {string} activityType - The activity type
 * @returns {string} Human-readable label
 */
function getActivityTypeLabel(activityType) {
    switch (activityType) {
        case 'thinking':
            return 'Analyzing';
        case 'tool_use':
            return 'Executing';
        case 'tool_result':
            return 'Processing';
        case 'subagent':
            return 'Delegating';
        case 'file_save':
            return 'Saving';
        case 'completed':
            return 'Complete';
        default:
            return 'Working';
    }
}

/**
 * Strip emoji prefix from activity text for cleaner display
 * @param {string} text - Activity text with potential emoji
 * @returns {string} Clean text without leading emoji
 */
function stripEmojiPrefix(text) {
    // Remove leading emoji (handles most Unicode emoji patterns)
    return text.replace(/^[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]\s*/u, '').trim();
}

export function showLoading() {
    const id = 'loading-' + Date.now();
    activityHistories.set(id, []);

    const container = document.createElement('div');
    container.id = id;
    container.className = "flex items-start gap-4";

    container.innerHTML = `
        <div class="avatar avatar-agent">
            <i class="ph-fill ph-robot text-lg" style="color: var(--accent-primary);"></i>
        </div>
        <div class="activity-indicator" data-loading-id="${id}">
            <!-- Neural Orb with orbital rings -->
            <div class="neural-orb" data-activity="thinking">
                <div class="neural-orb-ring"></div>
                <div class="neural-orb-ring"></div>
                <div class="neural-orb-ring"></div>
                <div class="neural-orb-core">
                    <i class="ph-bold ph-brain"></i>
                </div>
            </div>
            <!-- Activity Content -->
            <div class="activity-content">
                <div class="activity-type-label">Initializing</div>
                <div class="activity-text-main">Preparing response</div>
                <div class="activity-timeline"></div>
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
 * Update the loading indicator with activity information
 * @param {string} loadingId - The loading element ID
 * @param {string} activityText - Activity message to display
 * @param {string|null} activityType - Activity type (thinking, tool_use, tool_result, subagent)
 */
export function updateLoadingActivity(loadingId, activityText, activityType = null) {
    const container = document.getElementById(loadingId);
    if (!container) return;

    const indicator = container.querySelector('.activity-indicator');
    if (!indicator) return;

    const orbEl = indicator.querySelector('.neural-orb');
    const orbIcon = indicator.querySelector('.neural-orb-core i');
    const typeLabelEl = indicator.querySelector('.activity-type-label');
    const textMainEl = indicator.querySelector('.activity-text-main');
    const timelineEl = indicator.querySelector('.activity-timeline');

    if (!textMainEl) return;

    // Determine activity type from text if not provided
    const detectedType = activityType || detectActivityType(activityText);

    // Update orb appearance based on activity type
    if (orbEl) {
        orbEl.setAttribute('data-activity', detectedType);
    }

    // Update orb icon
    if (orbIcon) {
        orbIcon.className = getActivityIconClass(detectedType);
    }

    // Update type label
    if (typeLabelEl) {
        typeLabelEl.textContent = getActivityTypeLabel(detectedType);
    }

    // Update main activity text (strip emoji for cleaner look)
    const cleanText = stripEmojiPrefix(activityText) || activityText;
    textMainEl.textContent = cleanText;

    // Add to activity history for timeline
    const history = activityHistories.get(loadingId) || [];
    const lastItem = history[history.length - 1];

    // Only add if different from last item
    if (cleanText && cleanText !== lastItem) {
        history.push(cleanText);
        activityHistories.set(loadingId, history);

        // Update timeline display
        if (timelineEl) {
            updateActivityTimeline(timelineEl, history);
        }
    }

    scrollToBottom();
}

/**
 * Detect activity type from activity text
 * @param {string} text - Activity text
 * @returns {string} Detected activity type
 */
function detectActivityType(text) {
    if (!text) return 'thinking';

    const lowerText = text.toLowerCase();

    if (lowerText.includes('thinking') || lowerText.includes('analyzing') || lowerText.includes('🧠')) {
        return 'thinking';
    }
    if (lowerText.includes('complete') || lowerText.includes('done') || lowerText.includes('✨')) {
        return 'completed';
    }
    if (lowerText.includes('result') || lowerText.includes('received') || lowerText.includes('✅')) {
        return 'tool_result';
    }
    if (lowerText.includes('subagent') || lowerText.includes('delegat') || lowerText.includes('👥')) {
        return 'subagent';
    }
    // File save operations - check before generic tool_use
    if (lowerText.includes('💾') || lowerText.includes('saving') || lowerText.includes('writing file') ||
        lowerText.includes('editing file') || lowerText.includes('save transcript')) {
        return 'file_save';
    }
    if (lowerText.includes('🔧') || lowerText.includes('tool') || lowerText.includes('using') ||
        lowerText.includes('running') || lowerText.includes('executing')) {
        return 'tool_use';
    }

    return 'tool_use'; // Default for active operations
}

/**
 * Update the activity timeline display
 * @param {HTMLElement} timelineEl - Timeline container element
 * @param {string[]} history - Activity history array
 */
function updateActivityTimeline(timelineEl, history) {
    // Only show last N items (excluding the current one which is in main text)
    const itemsToShow = history.slice(0, -1).slice(-MAX_TIMELINE_ITEMS);

    if (itemsToShow.length === 0) {
        timelineEl.innerHTML = '';
        return;
    }

    timelineEl.innerHTML = itemsToShow.map(item => `
        <div class="activity-timeline-item">
            <i class="ph-bold ph-check"></i>
            <span>${escapeHtmlForTimeline(item)}</span>
        </div>
    `).join('');
}

/**
 * Simple HTML escape for timeline items
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtmlForTimeline(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

export function removeLoading(id) {
    const el = document.getElementById(id);
    if (el) el.remove();

    // Clean up activity history
    activityHistories.delete(id);
}
