// ============================================
// Header Dropdowns
// ============================================

export function initHeaderDropdowns() {
    const layoutBtn = document.getElementById('header-layout-btn');
    const layoutMenu = document.getElementById('header-layout-menu');

    // Toggle layout dropdown
    layoutBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        layoutMenu?.classList.toggle('hidden');
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        const dropdown = document.getElementById('header-layout-dropdown');
        if (dropdown && !dropdown.contains(e.target)) {
            layoutMenu?.classList.add('hidden');
        }
    });

    // Update active state on layout change
    document.querySelectorAll('.header-dropdown-item[data-layout]').forEach(item => {
        item.addEventListener('click', () => {
            // Update active state
            document.querySelectorAll('.header-dropdown-item[data-layout]').forEach(i => {
                i.classList.remove('active');
            });
            item.classList.add('active');

            // Close dropdown
            layoutMenu?.classList.add('hidden');
        });
    });
}
