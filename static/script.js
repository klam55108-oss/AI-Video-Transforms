// Generate or retrieve Session ID
function getSessionId() {
    let sessionId = localStorage.getItem('agent_session_id');
    if (!sessionId) {
        sessionId = crypto.randomUUID();
        localStorage.setItem('agent_session_id', sessionId);
    }
    return sessionId;
}

const sessionId = getSessionId();
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const chatMessages = document.getElementById('chat-messages');
const sendBtn = document.getElementById('send-btn');
const resetBtn = document.getElementById('reset-btn');

// Auto-resize textarea
userInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
    if(this.value === '') {
        this.style.height = '44px'; // Reset to min-height
    }
});

// Handle Enter to submit (Shift+Enter for newline)
userInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.requestSubmit();
    }
});

function scrollToBottom() {
    // Smooth scroll to bottom
    const scrollHeight = chatMessages.scrollHeight;
    chatMessages.scrollTo({
        top: scrollHeight,
        behavior: 'smooth'
    });
}

// Add Message to UI
function addMessage(text, sender) {
    const isUser = sender === 'user';
    
    // Outer Container
    const container = document.createElement('div');
    container.className = isUser 
        ? "flex items-start gap-4 flex-row-reverse"
        : "flex items-start gap-4";

    // Avatar
    const avatar = document.createElement('div');
    avatar.className = "flex-shrink-0";
    
    if (isUser) {
        avatar.innerHTML = `
            <div class="w-8 h-8 rounded-lg bg-blue-600 shadow-highlight-strong flex items-center justify-center">
                <span class="text-xs font-bold text-white">C</span>
            </div>
        `;
    } else {
        avatar.innerHTML = `
            <div class="w-8 h-8 rounded-lg bg-white border border-slate-200 shadow-sm flex items-center justify-center">
                <i class="ph-fill ph-robot text-blue-600"></i>
            </div>
        `;
    }

    // Message Content Wrapper
    const contentWrapper = document.createElement('div');
    contentWrapper.className = "flex-1 min-w-0";

    // Bubble
    const bubble = document.createElement('div');
    
    if (isUser) {
        // User Styling: Blue background, Top Highlight, Shadow MD
        bubble.className = "bg-blue-600 text-white rounded-xl rounded-tr-none p-4 shadow-md shadow-highlight-strong text-sm leading-relaxed";
        bubble.textContent = text;
    } else {
        // Agent Styling: White Card, Ring, Prose
        bubble.className = "message-agent relative bg-white rounded-xl rounded-tl-none p-5 shadow-sm ring-1 ring-slate-900/5 text-sm text-slate-700 prose prose-slate max-w-none";
        bubble.innerHTML = marked.parse(text);
    }

    // Timestamp
    const timestamp = document.createElement('span');
    timestamp.className = `text-[10px] text-slate-400 font-medium mt-1 block ${isUser ? 'text-right mr-1' : 'ml-1'}`;
    timestamp.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    contentWrapper.appendChild(bubble);
    contentWrapper.appendChild(timestamp);

    container.appendChild(avatar);
    container.appendChild(contentWrapper);

    // Append to chat area
    // The container is inside the main chatMessages div now, but let's stick to the inner wrapper if it exists.
    // In the HTML we have <div class="max-w-3xl mx-auto space-y-8">.
    let listContainer = chatMessages.querySelector('div.space-y-8');
    if (!listContainer) {
        // Create if missing (e.g. if we cleared HTML)
        listContainer = document.createElement('div');
        listContainer.className = "max-w-3xl mx-auto space-y-8";
        chatMessages.appendChild(listContainer);
    }
    listContainer.appendChild(container);
    
    scrollToBottom();
}

// Add Loading Indicator
function showLoading() {
    const id = 'loading-' + Date.now();
    const container = document.createElement('div');
    container.id = id;
    container.className = "flex items-start gap-4";
    
    container.innerHTML = `
        <div class="flex-shrink-0">
            <div class="w-8 h-8 rounded-lg bg-white border border-slate-200 shadow-sm flex items-center justify-center">
                <i class="ph-fill ph-robot text-blue-600"></i>
            </div>
        </div>
        <div class="bg-white rounded-xl rounded-tl-none p-4 shadow-sm ring-1 ring-slate-900/5">
            <div class="flex space-x-1.5 items-center h-5">
                <div class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"></div>
                <div class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
                <div class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
            </div>
        </div>
    `;
    
    let listContainer = chatMessages.querySelector('div.space-y-8');
    if (!listContainer) {
         listContainer = document.createElement('div');
         listContainer.className = "max-w-3xl mx-auto space-y-8";
         chatMessages.appendChild(listContainer);
    }
    listContainer.appendChild(container);
    scrollToBottom();
    return id;
}

function removeLoading(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

// Initialization: Fetch Greeting
async function initSession() {
    // Only init if the chat is empty (new session or refresh)
    // Actually, we should check if we already have history.
    // For now, let's assume if we are loading this script, we want to sync.
    // But we don't want to double-init if the user just refreshed and session is alive?
    // If backend is alive, `get_greeting` returns the stored greeting?
    // Wait, `get_greeting` consumes the queue item. It works once.
    // If we refresh, we might want to just show "Ready" or nothing if we have history.
    // But we don't persist history in frontend yet.
    // So every refresh IS a fresh UI.
    
    // Clear any hardcoded placeholder if we want dynamic.
    const listContainer = chatMessages.querySelector('div.space-y-8');
    if (listContainer) {
        listContainer.innerHTML = ''; // Clear hardcoded placeholder
    }

    const loadingId = showLoading();
    
    try {
        const response = await fetch('/chat/init', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId })
        });
        
        if (!response.ok) throw new Error('Failed to init session');
        
        const data = await response.json();
        removeLoading(loadingId);
        addMessage(data.response, 'agent');
        
    } catch (e) {
        console.error("Init failed", e);
        removeLoading(loadingId);
        // Fallback or silent fail
        addMessage("Checking system status...", 'agent'); 
        // Retry logic or just let user type.
    }
}

// Handle Form Submit
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message) return;

    // Clear input
    userInput.value = '';
    userInput.style.height = '44px'; // Reset height
    userInput.disabled = true;
    sendBtn.disabled = true;

    // Add User Message
    addMessage(message, 'user');

    // Show Loading
    const loadingId = showLoading();

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionId,
                message: message
            }),
        });

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();
        removeLoading(loadingId);
        addMessage(data.response, 'agent');

    } catch (error) {
        console.error('Error:', error);
        removeLoading(loadingId);
        addMessage(`**Error:** ${error.message}. Please try again.`, 'agent');
    } finally {
        userInput.disabled = false;
        sendBtn.disabled = false;
        userInput.focus();
    }
});

// Handle Reset
resetBtn.addEventListener('click', async () => {
    if (confirm('Start a new transcription session? Current history will be cleared.')) {
        try {
            await fetch(`/chat/${sessionId}`, { method: 'DELETE' });
        } catch (e) {
            console.warn('Failed to close session on server', e);
        }
        
        localStorage.removeItem('agent_session_id');
        window.location.reload();
    }
});

// Run Init
initSession();