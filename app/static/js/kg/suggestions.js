// ============================================
// KG Insights Suggestion Cards
// Renders interactive suggestion cards in agent messages for exploring knowledge graphs.
// ============================================

import { escapeHtml } from '../core/utils.js';
import { showToast } from '../ui/toast.js';

// ============================================
// Constants
// ============================================

/**
 * Debounce delay for suggestion card clicks (ms)
 * Prevents accidental double-clicks from sending duplicate messages
 * @type {number}
 */
const CARD_CLICK_DEBOUNCE_MS = 500;

/**
 * Tracks if a card click is currently being processed (debounce guard)
 * @type {boolean}
 */
let isProcessingCardClick = false;

/**
 * Patterns that indicate a message contains KG insight content
 * @type {RegExp[]}
 */
const INSIGHT_PATTERNS = [
    /key\s*players/i,
    /suggested\s*explorations?/i,
    /your\s*.{0,50}knowledge\s*graph/i,  // Allow text between "your" and "knowledge graph"
    /graph\s*insights?/i,
    /explore\s*further/i,
    /explore\s*your\s*graph/i,           // "Explore Your Graph" heading
    /here\s*are\s*some\s*.*\s*to\s*explore/i,
    /you\s*might\s*want\s*to\s*ask/i,
    /try\s*asking/i,
    /what\s*you\s*can\s*do\s*with/i,     // "what you can do with your..."
    /why\s*this\s*matters/i,             // "Why This Matters" section
    /query\s*type/i                       // Table header "Query Type"
];

/**
 * Pattern to match suggestion lines in markdown
 * Matches: - "Query text here" or * "Query text here"
 * Also matches arrow patterns like: -> "Query text"
 */
const SUGGESTION_LINE_PATTERN = /^[\s]*[-*>]+\s*[""]([^""]+)[""][\s]*$/;

/**
 * Pattern to match emoji + bold title format
 * Matches: **icon Title** description
 */
const CARD_HEADER_PATTERN = /\*\*([^\s*]+)\s+([^*]+)\*\*/;

// ============================================
// Main Functions
// ============================================

/**
 * Check if message contains KG insight content.
 * @param {string} text - Raw message text
 * @returns {boolean}
 */
export function isInsightMessage(text) {
    if (!text || typeof text !== 'string') {
        return false;
    }

    // Check for insight patterns
    for (const pattern of INSIGHT_PATTERNS) {
        if (pattern.test(text)) {
            return true;
        }
    }

    // Check for suggestion arrow patterns
    if (/[-*>]+\s*[""][^""]+[""]/.test(text)) {
        return true;
    }

    return false;
}

/**
 * Parse suggestion data from rendered markdown content.
 * Extracts icon, title, description, and query from structured patterns.
 * @param {HTMLElement} element - The element containing markdown content
 * @returns {Array<{icon: string, title: string, description: string, query: string}>}
 */
function parseSuggestions(element) {
    const suggestions = [];

    // Strategy 1: Look for list items with quoted queries
    const listItems = element.querySelectorAll('li');
    listItems.forEach(li => {
        const text = li.textContent || '';

        // Check for quoted suggestion pattern
        const quoteMatch = text.match(/[""]([^""]+)[""]/);
        if (quoteMatch) {
            const query = quoteMatch[1].trim();

            // Try to extract icon and title from the line
            const beforeQuote = text.split(/[""]/)[0];
            const iconMatch = beforeQuote.match(/^[\s]*([^\s\w])/u);
            const icon = iconMatch ? iconMatch[1] : getDefaultIcon(query);

            // Extract title from bold text or use a default
            const boldEl = li.querySelector('strong, b');
            const title = boldEl ? boldEl.textContent.trim() : extractTitle(query);

            // Description is text after the quote or title
            const descMatch = text.match(/[""]\s*[-:]+\s*(.+)$/);
            const description = descMatch ? descMatch[1].trim() : '';

            suggestions.push({ icon, title, description, query });
        }
    });

    // Strategy 2: Look for paragraphs with arrow patterns
    if (suggestions.length === 0) {
        const paragraphs = element.querySelectorAll('p');
        paragraphs.forEach(p => {
            const text = p.textContent || '';
            const lines = text.split('\n');

            lines.forEach(line => {
                // Match arrow patterns: -> "query" or - "query"
                const arrowMatch = line.match(/[-*>]+\s*[""]([^""]+)[""]/);
                if (arrowMatch) {
                    const query = arrowMatch[1].trim();
                    suggestions.push({
                        icon: getDefaultIcon(query),
                        title: extractTitle(query),
                        description: '',
                        query
                    });
                }
            });
        });
    }

    // Strategy 3: Look for emphasized/italic text with quotes (common in markdown)
    if (suggestions.length === 0) {
        const emphElements = element.querySelectorAll('em, i');
        emphElements.forEach(em => {
            const text = (em.textContent || '').trim();
            // Check if it looks like a query (starts with quote or contains question mark)
            if (text.startsWith('"') || text.startsWith("'") || text.includes('?') || text.length > 10) {
                const query = text.replace(/^["'"'\s]+|["'"'\s]+$/g, '');
                if (query.length > 5) {
                    suggestions.push({
                        icon: getDefaultIcon(query),
                        title: extractTitle(query),
                        description: '',
                        query
                    });
                }
            }
        });
    }

    // Strategy 4: Parse tables with "Example" or query columns
    // This handles the "Explore Your Graph" table format
    if (suggestions.length === 0) {
        const tables = element.querySelectorAll('table');
        tables.forEach(table => {
            // Find header row to identify column indices
            const headerRow = table.querySelector('thead tr, tr:first-child');
            if (!headerRow) return;

            const headers = Array.from(headerRow.querySelectorAll('th, td'));
            let queryTypeIdx = -1;
            let descriptionIdx = -1;
            let exampleIdx = -1;

            headers.forEach((header, idx) => {
                const text = (header.textContent || '').toLowerCase().trim();
                if (text.includes('query') && text.includes('type')) queryTypeIdx = idx;
                if (text.includes('what') || text.includes('description') || text.includes('does')) descriptionIdx = idx;
                if (text.includes('example') || text.includes('try') || text.includes('ask')) exampleIdx = idx;
            });

            // If we found an example column, parse the data rows
            if (exampleIdx >= 0) {
                const dataRows = table.querySelectorAll('tbody tr, tr:not(:first-child)');
                dataRows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length <= exampleIdx) return;

                    const exampleText = (cells[exampleIdx]?.textContent || '').trim();
                    // Extract quoted query from example cell
                    const quoteMatch = exampleText.match(/[""]([^""]+)[""]/);
                    if (quoteMatch) {
                        const query = quoteMatch[1].trim();
                        const title = queryTypeIdx >= 0 && cells[queryTypeIdx]
                            ? cells[queryTypeIdx].textContent.trim()
                            : extractTitle(query);
                        const description = descriptionIdx >= 0 && cells[descriptionIdx]
                            ? cells[descriptionIdx].textContent.trim()
                            : '';

                        suggestions.push({
                            icon: getDefaultIcon(query),
                            title,
                            description,
                            query
                        });
                    }
                });
            }
        });
    }

    return suggestions;
}

/**
 * Get a default icon based on query content
 * @param {string} query - The query text
 * @returns {string} An appropriate emoji icon
 */
function getDefaultIcon(query) {
    const lowerQuery = query.toLowerCase();

    // KG-specific query types
    if (lowerQuery.includes('key') || lowerQuery.includes('main') || lowerQuery.includes('important') || lowerQuery.includes('central')) {
        return '\u{2B50}'; // Star - key players
    }
    if (lowerQuery.includes('connect') || lowerQuery.includes('relation') || lowerQuery.includes('link') || lowerQuery.includes('how is')) {
        return '\u{1F517}'; // Link - connections
    }
    if (lowerQuery.includes('common') || lowerQuery.includes('shared') || lowerQuery.includes('have in common')) {
        return '\u{1F91D}'; // Handshake - common ground
    }
    if (lowerQuery.includes('cluster') || lowerQuery.includes('group') || lowerQuery.includes('topic')) {
        return '\u{1F4CA}'; // Bar chart - clusters/groups
    }
    if (lowerQuery.includes('evidence') || lowerQuery.includes('proof') || lowerQuery.includes('source') || lowerQuery.includes('quote')) {
        return '\u{1F4DD}'; // Memo - evidence
    }
    if (lowerQuery.includes('mention') || lowerQuery.includes('appear') || lowerQuery.includes('used') || lowerQuery.includes('where is')) {
        return '\u{1F4CD}'; // Pin - mentions/locations
    }
    if (lowerQuery.includes('isolat') || lowerQuery.includes('disconnect') || lowerQuery.includes('separate')) {
        return '\u{1F3DD}'; // Island - isolated topics
    }

    // General query types
    if (lowerQuery.includes('who') || lowerQuery.includes('person') || lowerQuery.includes('people')) {
        return '\u{1F464}'; // Bust silhouette
    }
    if (lowerQuery.includes('where') || lowerQuery.includes('location') || lowerQuery.includes('place')) {
        return '\u{1F4CD}'; // Pin
    }
    if (lowerQuery.includes('when') || lowerQuery.includes('time') || lowerQuery.includes('date')) {
        return '\u{1F4C5}'; // Calendar
    }
    if (lowerQuery.includes('how') || lowerQuery.includes('process') || lowerQuery.includes('method')) {
        return '\u{2699}'; // Gear
    }
    if (lowerQuery.includes('explore') || lowerQuery.includes('discover') || lowerQuery.includes('find')) {
        return '\u{1F50D}'; // Magnifying glass
    }
    if (lowerQuery.includes('summary') || lowerQuery.includes('overview')) {
        return '\u{1F4CB}'; // Clipboard
    }

    return '\u{1F4AC}'; // Speech bubble (default)
}

/**
 * Extract a short title from a query
 * @param {string} query - The full query text
 * @returns {string} A shortened title
 */
function extractTitle(query) {
    // If query starts with a common question word, use it as context
    const questionWords = ['who', 'what', 'where', 'when', 'why', 'how', 'show', 'tell', 'list', 'find'];
    const lowerQuery = query.toLowerCase();

    for (const word of questionWords) {
        if (lowerQuery.startsWith(word)) {
            // Return first 4-6 words as title
            const words = query.split(/\s+/).slice(0, 5);
            return words.join(' ') + (query.split(/\s+/).length > 5 ? '...' : '');
        }
    }

    // Default: truncate to reasonable length
    if (query.length > 40) {
        return query.substring(0, 37) + '...';
    }
    return query;
}

/**
 * Render suggestion cards from structured suggestion data.
 * @param {HTMLElement} container - Container to render cards into
 * @param {Array<{icon: string, title: string, description: string, query: string}>} suggestions - Array of suggestions
 */
export function renderSuggestionCards(container, suggestions) {
    if (!container || !suggestions || suggestions.length === 0) {
        return;
    }

    // Create grid container with data attribute fallback for CSS selector reliability
    const grid = document.createElement('div');
    grid.className = 'kg-suggestion-cards';
    grid.setAttribute('data-component', 'kg-suggestion-cards');
    grid.setAttribute('role', 'group');
    grid.setAttribute('aria-label', 'Suggested explorations');

    // Create cards
    suggestions.forEach((suggestion, index) => {
        const card = document.createElement('button');
        card.type = 'button';
        card.className = 'suggestion-card';
        card.setAttribute('data-component', 'suggestion-card');
        card.setAttribute('data-query', suggestion.query);
        card.setAttribute('tabindex', '0');
        card.setAttribute('aria-label', `Ask: ${suggestion.query}`);

        // Sanitize content
        const safeIcon = escapeHtml(suggestion.icon);
        const safeTitle = escapeHtml(suggestion.title);
        const safeDesc = escapeHtml(suggestion.description);

        card.innerHTML = `
            <span class="icon" aria-hidden="true">${safeIcon}</span>
            <span class="title">${safeTitle}</span>
            ${safeDesc ? `<span class="desc">${safeDesc}</span>` : ''}
        `;

        // Click handler sends the query with graceful degradation and debouncing
        card.addEventListener('click', () => {
            // Debounce guard: prevent rapid double-clicks
            if (isProcessingCardClick) {
                return;
            }
            isProcessingCardClick = true;
            setTimeout(() => { isProcessingCardClick = false; }, CARD_CLICK_DEBOUNCE_MS);

            if (typeof window.sendMessage === 'function') {
                window.sendMessage(suggestion.query);
            } else {
                // Fallback: copy query to clipboard and notify user
                navigator.clipboard?.writeText(suggestion.query).then(() => {
                    showToast('Query copied to clipboard. Paste it in the chat input.', 'info');
                }).catch(() => {
                    showToast('Chat not ready. Please try again.', 'warning');
                });
                console.warn('sendMessage not available on window');
            }
        });

        // Keyboard support
        card.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                card.click();
            }
        });

        grid.appendChild(card);
    });

    container.appendChild(grid);
}

/**
 * Parse agent message for suggestion patterns and enhance with interactive UI.
 * Looks for markdown patterns and replaces them with interactive card components.
 * @param {HTMLElement} messageEl - The message element to enhance
 */
export function enhanceInsightMessage(messageEl) {
    if (!messageEl) {
        return;
    }

    // Parse suggestions from the rendered content
    const suggestions = parseSuggestions(messageEl);

    if (suggestions.length === 0) {
        return;
    }

    // Find or create a container for the suggestion cards
    // We'll append after any existing content
    // First, check if we already enhanced this message (use data attribute as fallback)
    if (messageEl.querySelector('.kg-suggestion-cards, [data-component="kg-suggestion-cards"]')) {
        return;
    }

    // Find the section containing suggestions to potentially hide/replace
    const lists = messageEl.querySelectorAll('ul, ol');
    let suggestionList = null;

    lists.forEach(list => {
        const items = list.querySelectorAll('li');
        let hasSuggestionItems = false;

        items.forEach(item => {
            const text = item.textContent || '';
            if (/[""][^""]+[""]/.test(text)) {
                hasSuggestionItems = true;
            }
        });

        if (hasSuggestionItems) {
            suggestionList = list;
        }
    });

    // If we found a suggestion list, replace it with cards
    if (suggestionList) {
        const cardContainer = document.createElement('div');
        renderSuggestionCards(cardContainer, suggestions);

        // Insert cards before the list and hide the list
        suggestionList.parentNode.insertBefore(cardContainer.firstChild, suggestionList);
        suggestionList.style.display = 'none';
        suggestionList.classList.add('suggestion-list-hidden');
        return;
    }

    // Check for suggestion tables (e.g., "Explore Your Graph" format)
    const tables = messageEl.querySelectorAll('table');
    let suggestionTable = null;

    tables.forEach(table => {
        const headerRow = table.querySelector('thead tr, tr:first-child');
        if (!headerRow) return;

        const headerText = (headerRow.textContent || '').toLowerCase();
        // Check if this table has query-related columns
        if (headerText.includes('example') || headerText.includes('query') ||
            headerText.includes('try') || headerText.includes('ask')) {
            suggestionTable = table;
        }
    });

    // If we found a suggestion table, add cards after it
    if (suggestionTable) {
        const cardContainer = document.createElement('div');
        renderSuggestionCards(cardContainer, suggestions);

        // Insert cards after the table
        if (suggestionTable.nextSibling) {
            suggestionTable.parentNode.insertBefore(cardContainer.firstChild, suggestionTable.nextSibling);
        } else {
            suggestionTable.parentNode.appendChild(cardContainer.firstChild);
        }

        // Optionally hide the table since cards provide the same functionality
        suggestionTable.style.display = 'none';
        suggestionTable.classList.add('suggestion-table-hidden');
        return;
    }

    // Fallback: Append cards at the end of the message
    renderSuggestionCards(messageEl, suggestions);
}
