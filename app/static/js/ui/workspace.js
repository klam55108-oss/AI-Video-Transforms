/**
 * Workspace Layout Management
 *
 * Manages the 3-panel workspace layout with resizable dividers.
 * Panels: Chat | KG Graph | Inspector
 */

import { state } from '../core/state.js';

// Layout modes
const LAYOUTS = {
    CHAT_ONLY: 'chat-only',
    CHAT_KG: 'chat-kg',
    CHAT_KG_INSPECTOR: 'chat-kg-inspector'
};

// Default panel widths (percentages)
const DEFAULT_WIDTHS = {
    chat: 50,
    kg: 50
};

// Minimum panel widths in pixels
const MIN_WIDTH = 300;

// DOM references (lazy lookup)
function getChatPanel() { return document.getElementById('chat-panel'); }
function getKGPanel() { return document.getElementById('kg-panel'); }
function getResizeHandle() { return document.querySelector('.resize-handle'); }
function getInputArea() { return document.querySelector('.input-area'); }

/**
 * Initialize workspace layout and resize handles
 */
export function initWorkspace() {
    initResizeHandles();
    // Load saved widths from localStorage
    const saved = localStorage.getItem('panelWidths');
    if (saved) {
        try {
            state.panelWidths = JSON.parse(saved);
        } catch (e) {
            state.panelWidths = { ...DEFAULT_WIDTHS };
        }
    } else {
        state.panelWidths = { ...DEFAULT_WIDTHS };
    }
    state.workspaceLayout = LAYOUTS.CHAT_ONLY;
}

/**
 * Show the KG panel in FULL WIDTH mode (hide chat)
 */
export function showKGPanel() {
    const kgPanel = getKGPanel();
    const chatPanel = getChatPanel();
    const resizeHandle = getResizeHandle();
    const inputArea = getInputArea();

    if (kgPanel) {
        // Hide chat panel completely
        if (chatPanel) {
            chatPanel.classList.add('hidden');
            chatPanel.classList.remove('flex');
        }

        // Hide resize handle (not needed in exclusive mode)
        if (resizeHandle) {
            resizeHandle.classList.add('hidden');
        }

        // Hide input area (not needed in graph mode)
        if (inputArea) {
            inputArea.classList.add('hidden');
        }

        // Show KG panel full width
        kgPanel.classList.remove('hidden');
        kgPanel.classList.add('flex');
        kgPanel.style.flex = '1';
        state.workspaceLayout = LAYOUTS.CHAT_KG;

        // Resize Cytoscape after layout change
        setTimeout(() => {
            if (state.cytoscapeInstance) {
                state.cytoscapeInstance.resize();
                state.cytoscapeInstance.fit();
            }
        }, 350);
    }
}

/**
 * Hide the KG panel (show chat full width)
 */
export function hideKGPanel() {
    const kgPanel = getKGPanel();
    const chatPanel = getChatPanel();
    const resizeHandle = getResizeHandle();
    const inputArea = getInputArea();

    // Hide KG panel
    if (kgPanel) {
        kgPanel.classList.add('hidden');
        kgPanel.classList.remove('flex');
        kgPanel.style.flex = '';
    }

    // Hide resize handle
    if (resizeHandle) {
        resizeHandle.classList.add('hidden');
    }

    // Show chat panel full width
    if (chatPanel) {
        chatPanel.classList.remove('hidden');
        chatPanel.classList.add('flex');
        chatPanel.style.flex = '1';
    }

    // Show input area (needed for chat mode)
    if (inputArea) {
        inputArea.classList.remove('hidden');
    }

    state.workspaceLayout = LAYOUTS.CHAT_ONLY;
}

/**
 * Apply saved panel widths
 */
function applyPanelWidths() {
    const chatPanel = getChatPanel();
    const kgPanel = getKGPanel();

    if (chatPanel && kgPanel && state.workspaceLayout !== LAYOUTS.CHAT_ONLY) {
        chatPanel.style.flex = `0 0 ${state.panelWidths.chat}%`;
        kgPanel.style.flex = `0 0 ${state.panelWidths.kg}%`;
    }
}

/**
 * Initialize resize handle drag behavior
 */
function initResizeHandles() {
    const handle = getResizeHandle();
    if (!handle) return;

    let isResizing = false;
    let startX = 0;
    let startWidths = { chat: 0, kg: 0 };

    handle.addEventListener('mousedown', (e) => {
        const chatPanel = getChatPanel();
        const kgPanel = getKGPanel();
        if (!chatPanel || !kgPanel || kgPanel.classList.contains('hidden')) return;

        isResizing = true;
        startX = e.clientX;
        startWidths = {
            chat: chatPanel.offsetWidth,
            kg: kgPanel.offsetWidth
        };

        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        handle.classList.add('active');

        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;

        const delta = e.clientX - startX;
        const newChatWidth = Math.max(MIN_WIDTH, startWidths.chat + delta);
        const newKGWidth = Math.max(MIN_WIDTH, startWidths.kg - delta);

        const totalWidth = newChatWidth + newKGWidth;
        state.panelWidths = {
            chat: (newChatWidth / totalWidth) * 100,
            kg: (newKGWidth / totalWidth) * 100
        };

        applyPanelWidths();
    });

    document.addEventListener('mouseup', () => {
        if (!isResizing) return;

        isResizing = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';

        const handle = getResizeHandle();
        if (handle) handle.classList.remove('active');

        // Save to localStorage
        localStorage.setItem('panelWidths', JSON.stringify(state.panelWidths));

        // Trigger Cytoscape resize
        if (state.cytoscapeInstance) {
            state.cytoscapeInstance.resize();
        }
    });
}

export { LAYOUTS };
