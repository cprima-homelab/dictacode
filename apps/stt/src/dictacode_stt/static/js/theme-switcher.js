/**
 * Theme Switcher with localStorage persistence (v0.3.0 Phase 3)
 */

(function() {
    'use strict';

    const STORAGE_KEY = 'dictacode-theme';
    const DEFAULT_THEME = 'solarized-light';

    /**
     * Get saved theme from localStorage or use default
     */
    function getSavedTheme() {
        try {
            return localStorage.getItem(STORAGE_KEY) || DEFAULT_THEME;
        } catch (e) {
            console.warn('localStorage not available, using default theme:', e);
            return DEFAULT_THEME;
        }
    }

    /**
     * Save theme to localStorage
     */
    function saveTheme(theme) {
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch (e) {
            console.warn('Failed to save theme to localStorage:', e);
        }
    }

    /**
     * Apply theme to document
     */
    function applyTheme(theme) {
        const html = document.documentElement;
        html.setAttribute('data-theme', theme);
        updateActiveButton(theme);
    }

    /**
     * Update active state on theme switcher buttons
     */
    function updateActiveButton(theme) {
        const buttons = document.querySelectorAll('.theme-switcher button');
        buttons.forEach(button => {
            const buttonTheme = button.getAttribute('data-theme');
            if (buttonTheme === theme) {
                button.style.fontWeight = 'bold';
                button.style.borderWidth = '2px';
            } else {
                button.style.fontWeight = 'normal';
                button.style.borderWidth = '1px';
            }
        });
    }

    /**
     * Handle theme button clicks
     */
    function handleThemeClick(event) {
        const button = event.currentTarget;
        const theme = button.getAttribute('data-theme');

        if (theme) {
            applyTheme(theme);
            saveTheme(theme);
            console.log('Theme changed to:', theme);
        }
    }

    /**
     * Initialize theme switcher
     */
    function init() {
        // Apply saved theme immediately (before DOMContentLoaded to avoid flash)
        const savedTheme = getSavedTheme();
        applyTheme(savedTheme);

        // Attach click handlers when DOM is ready
        document.addEventListener('DOMContentLoaded', function() {
            const buttons = document.querySelectorAll('.theme-switcher button');
            buttons.forEach(button => {
                button.addEventListener('click', handleThemeClick);
            });

            console.log('Theme switcher initialized with theme:', savedTheme);
        });
    }

    // Initialize immediately
    init();

    // Expose API for debugging
    window.dictacodeTheme = {
        getCurrent: () => document.documentElement.getAttribute('data-theme'),
        set: applyTheme,
        reset: () => {
            applyTheme(DEFAULT_THEME);
            saveTheme(DEFAULT_THEME);
        }
    };
})();

/**
 * Badge Display - fetch and show license badge status (v0.3.11)
 */
(function() {
    'use strict';

    const ALL_TIERS = ['free', 'supporter', 'donor', 'contributor', 'multiplicator'];

    /**
     * Fetch badge state from API and update display
     */
    async function loadBadges() {
        try {
            const response = await fetch('/v1/api/license');
            if (!response.ok) {
                console.warn('Failed to fetch badge state:', response.status);
                return;
            }

            const data = await response.json();
            const activeTiers = data.tiers || [];

            // Update each tier display
            ALL_TIERS.forEach(tier => {
                const span = document.getElementById('badge-' + tier);
                if (span) {
                    const hasIt = activeTiers.includes(tier) || (tier === 'free' && activeTiers.length === 0);
                    span.textContent = hasIt ? 'y' : 'n';
                    span.style.color = hasIt ? 'var(--green, #859900)' : 'var(--base01, #586e75)';
                }
            });

        } catch (e) {
            console.warn('Badge load failed:', e);
        }
    }

    // Load badges when DOM ready
    document.addEventListener('DOMContentLoaded', loadBadges);

    // Expose for debugging
    window.dictacodeBadges = { refresh: loadBadges };
})();
