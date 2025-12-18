// ============================================
// Sidebar Collapse/Expand
// ============================================

export function collapseSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar?.classList.add('collapsed');
    document.body.classList.add('sidebar-collapsed');
    localStorage.setItem('sidebar-collapsed', 'true');
}

export function expandSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar?.classList.remove('collapsed');
    document.body.classList.remove('sidebar-collapsed');
    localStorage.setItem('sidebar-collapsed', 'false');
}

export function initSidebarCollapse() {
    const collapseBtn = document.getElementById('sidebar-collapse-btn');
    const expandBtn = document.getElementById('sidebar-expand-btn');

    // Check for stored preference
    const isCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
    if (isCollapsed) {
        collapseSidebar();
    }

    // Collapse button (in sidebar header)
    collapseBtn?.addEventListener('click', collapseSidebar);

    // Expand button (in main header)
    expandBtn?.addEventListener('click', expandSidebar);
}
