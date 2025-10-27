/**
 * Keyboard Shortcuts Manager
 *
 * Handles global keyboard shortcuts for the application
 */

class ShortcutManager {
    constructor() {
        this.shortcuts = new Map();
        this.enabled = true;
        this.sequenceTimeout = null;
        this.sequence = [];
        this.init();
    }

    /**
     * Initialize the shortcut manager
     */
    init() {
        document.addEventListener('keydown', this.handleKeydown.bind(this));
        this.registerDefaultShortcuts();
    }

    /**
     * Register a keyboard shortcut
     * @param {string} key - Key combination (e.g., 'Ctrl+K', '/', 'G D')
     * @param {Function} action - Action to execute
     * @param {string} description - Description for help modal
     * @param {string} category - Category for organization
     */
    register(key, action, description = '', category = 'General') {
        this.shortcuts.set(key.toLowerCase(), {
            action,
            description,
            category
        });
    }

    /**
     * Unregister a keyboard shortcut
     * @param {string} key - Key combination to unregister
     */
    unregister(key) {
        this.shortcuts.delete(key.toLowerCase());
    }

    /**
     * Handle keydown events
     * @param {KeyboardEvent} event - Keyboard event
     */
    handleKeydown(event) {
        if (!this.enabled) return;

        // Ignore shortcuts when typing in inputs, textareas, or contenteditable
        const target = event.target;
        if (
            target.tagName === 'INPUT' ||
            target.tagName === 'TEXTAREA' ||
            target.isContentEditable
        ) {
            // Allow '/' to focus search even in inputs (except when typing)
            if (event.key === '/' && target.tagName === 'INPUT' && target.value === '') {
                // Allow the '/' shortcut
            } else {
                return;
            }
        }

        // Build key combination string
        const keys = [];
        if (event.ctrlKey || event.metaKey) keys.push('ctrl');
        if (event.shiftKey) keys.push('shift');
        if (event.altKey) keys.push('alt');

        // Add the actual key
        let key = event.key.toLowerCase();
        if (key !== 'control' && key !== 'shift' && key !== 'alt' && key !== 'meta') {
            keys.push(key);
        }

        const combination = keys.join('+');

        // Check for direct match
        if (this.shortcuts.has(combination)) {
            event.preventDefault();
            this.shortcuts.get(combination).action(event);
            return;
        }

        // Handle key sequences (e.g., 'G D' for 'Go to Dashboard')
        if (!event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
            this.sequence.push(key);

            // Clear sequence after timeout
            clearTimeout(this.sequenceTimeout);
            this.sequenceTimeout = setTimeout(() => {
                this.sequence = [];
            }, 1000);

            // Check for sequence match
            const sequenceKey = this.sequence.join(' ');
            if (this.shortcuts.has(sequenceKey)) {
                event.preventDefault();
                this.shortcuts.get(sequenceKey).action(event);
                this.sequence = [];
                clearTimeout(this.sequenceTimeout);
            }
        }
    }

    /**
     * Register default application shortcuts
     */
    registerDefaultShortcuts() {
        // Navigation shortcuts
        this.register('/', () => {
            const searchInput = document.querySelector('input[type="search"], input[placeholder*="search" i]');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }, 'Focus search input', 'Navigation');

        this.register('ctrl+k', () => {
            // Show command palette (if implemented)
            console.log('Command palette');
        }, 'Open command palette', 'Navigation');

        this.register('g d', () => {
            window.location.href = '/dashboard';
        }, 'Go to dashboard', 'Navigation');

        this.register('g n', () => {
            window.location.href = '/networks';
        }, 'Go to networks', 'Navigation');

        this.register('g s', () => {
            window.location.href = '/search/new';
        }, 'Go to new search', 'Navigation');

        // Action shortcuts
        this.register('ctrl+n', (e) => {
            window.location.href = '/search/new';
        }, 'New search session', 'Actions');

        this.register('ctrl+e', (e) => {
            // Trigger export on current page
            const exportBtn = document.querySelector('[data-action="export"]');
            if (exportBtn) exportBtn.click();
        }, 'Export current view', 'Actions');

        this.register('ctrl+r', (e) => {
            // Refresh current data
            const refreshBtn = document.querySelector('[data-action="refresh"]');
            if (refreshBtn) {
                refreshBtn.click();
            } else {
                window.location.reload();
            }
        }, 'Refresh data', 'Actions');

        // Modal/Overlay shortcuts
        this.register('escape', () => {
            // Close modals, dropdowns, etc.
            const closeBtn = document.querySelector('[data-dismiss="modal"], [x-on\\:click*="open = false"]');
            if (closeBtn) closeBtn.click();
        }, 'Close modal/dropdown', 'General');

        this.register('?', () => {
            if (window.showShortcutsModal) {
                window.showShortcutsModal();
            }
        }, 'Show keyboard shortcuts', 'General');

        // Network visualization shortcuts
        this.register('+', () => {
            if (window.currentNetworkVisualizer) {
                window.currentNetworkVisualizer.zoomIn();
            }
        }, 'Zoom in (network)', 'Network');

        this.register('-', () => {
            if (window.currentNetworkVisualizer) {
                window.currentNetworkVisualizer.zoomOut();
            }
        }, 'Zoom out (network)', 'Network');

        this.register('0', () => {
            if (window.currentNetworkVisualizer) {
                window.currentNetworkVisualizer.fit();
            }
        }, 'Reset view (network)', 'Network');

        this.register('p', () => {
            if (window.currentNetworkVisualizer) {
                window.currentNetworkVisualizer.togglePhysics();
            }
        }, 'Toggle physics (network)', 'Network');

        this.register('ctrl+shift+s', () => {
            if (window.currentNetworkVisualizer) {
                window.currentNetworkVisualizer.exportAsPNG();
            }
        }, 'Export network as PNG', 'Network');

        // Table navigation shortcuts
        this.register('arrowup', () => {
            const selected = document.querySelector('tr.selected, [data-selected="true"]');
            if (selected) {
                const prev = selected.previousElementSibling;
                if (prev) {
                    selected.classList.remove('selected');
                    prev.classList.add('selected');
                    prev.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
                }
            }
        }, 'Navigate up (table)', 'Table');

        this.register('arrowdown', () => {
            const selected = document.querySelector('tr.selected, [data-selected="true"]');
            if (selected) {
                const next = selected.nextElementSibling;
                if (next) {
                    selected.classList.remove('selected');
                    next.classList.add('selected');
                    next.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
                }
            }
        }, 'Navigate down (table)', 'Table');

        this.register('enter', () => {
            const selected = document.querySelector('tr.selected, [data-selected="true"]');
            if (selected) {
                const link = selected.querySelector('a');
                if (link) link.click();
            }
        }, 'Select/activate (table)', 'Table');

        this.register(' ', (e) => {
            const selected = document.querySelector('tr.selected, [data-selected="true"]');
            if (selected) {
                const checkbox = selected.querySelector('input[type="checkbox"]');
                if (checkbox) {
                    checkbox.checked = !checkbox.checked;
                    checkbox.dispatchEvent(new Event('change'));
                }
            }
        }, 'Toggle selection (table)', 'Table');
    }

    /**
     * Enable shortcuts
     */
    enable() {
        this.enabled = true;
    }

    /**
     * Disable shortcuts
     */
    disable() {
        this.enabled = false;
    }

    /**
     * Get all shortcuts grouped by category
     * @returns {Object} Shortcuts grouped by category
     */
    getShortcutsByCategory() {
        const grouped = {};

        this.shortcuts.forEach((value, key) => {
            const category = value.category || 'General';
            if (!grouped[category]) {
                grouped[category] = [];
            }

            grouped[category].push({
                key,
                description: value.description
            });
        });

        return grouped;
    }

    /**
     * Show shortcuts help modal
     */
    showHelp() {
        if (window.showShortcutsModal) {
            window.showShortcutsModal();
        }
    }
}

// Initialize global shortcut manager
const shortcutManager = new ShortcutManager();

// Export to window
window.shortcutManager = shortcutManager;
