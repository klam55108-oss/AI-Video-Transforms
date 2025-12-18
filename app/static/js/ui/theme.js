// ============================================
// Theme Management
// ============================================

import { THEME_STORAGE_KEY } from '../core/config.js';
import { showToast } from './toast.js';

export function getTheme() {
    return localStorage.getItem(THEME_STORAGE_KEY) || 'dark';
}

export function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_STORAGE_KEY, theme);
}

export function toggleTheme() {
    const currentTheme = getTheme();
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);

    // Optional: Show toast notification
    const themeName = newTheme === 'dark' ? 'Dark' : 'Light';
    showToast(`Switched to ${themeName} theme`, 'info');
}

export function initTheme() {
    // Theme is already set in inline script, but ensure toggle works
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
}
