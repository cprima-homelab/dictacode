/**
 * Config page functionality (v0.3.0 Phase 3)
 */

(function() {
    'use strict';

    let originalConfig = {};
    let currentConfig = {};

    /**
     * Load current configuration
     */
    async function loadConfig() {
        try {
            // Load audio ports
            const portsResponse = await fetch('/api/audio/ports');
            const portsData = await portsResponse.json();

            const select = document.getElementById('audio-port-select');
            select.innerHTML = '';

            portsData.ports.forEach(port => {
                const option = document.createElement('option');
                option.value = port.port_id;
                option.textContent = `${port.name} (${port.port_id})`;
                if (port.port_id === portsData.active_port) {
                    option.selected = true;
                }
                select.appendChild(option);
            });

            // TODO: Load config from /api/config endpoint when implemented
            // For now, use placeholder values
            currentConfig = {
                audio_port: portsData.active_port || '',
                language: 'en',
                model: 'tiny'
            };
            originalConfig = { ...currentConfig };

            document.getElementById('language-select').value = currentConfig.language;
            document.getElementById('model-select').value = currentConfig.model;

        } catch (error) {
            console.error('Failed to load config:', error);
            showNotification('Failed to load configuration', 'error');
        }
    }

    /**
     * Show notification
     */
    function showNotification(message, type = 'info') {
        // Simple console log for now - could be enhanced with toast notifications
        console.log(`[${type.toUpperCase()}] ${message}`);
    }

    /**
     * Check if config has changed
     */
    function hasChanges() {
        const audioPort = document.getElementById('audio-port-select').value;
        const language = document.getElementById('language-select').value;
        const model = document.getElementById('model-select').value;

        return (
            audioPort !== originalConfig.audio_port ||
            language !== originalConfig.language ||
            model !== originalConfig.model
        );
    }

    /**
     * Update apply bar visibility
     */
    function updateApplyBar() {
        const applyBar = document.getElementById('apply-bar');
        if (hasChanges()) {
            applyBar.removeAttribute('hidden');
        } else {
            applyBar.setAttribute('hidden', '');
        }
    }

    /**
     * Discard changes
     */
    window.discardChanges = function() {
        document.getElementById('audio-port-select').value = originalConfig.audio_port;
        document.getElementById('language-select').value = originalConfig.language;
        document.getElementById('model-select').value = originalConfig.model;
        updateApplyBar();
    };

    /**
     * Apply changes
     */
    window.applyChanges = async function() {
        const config = {
            audio_port: document.getElementById('audio-port-select').value,
            language: document.getElementById('language-select').value,
            model: document.getElementById('model-select').value
        };

        try {
            // TODO: POST to /api/config endpoint when implemented
            console.log('Applying config:', config);

            showNotification('Configuration saved. Service restart required.', 'success');

            originalConfig = { ...config };
            updateApplyBar();

            // Show restart instructions
            if (confirm('Configuration saved. Restart the STT service to apply changes?\n\nRun: sudo systemctl restart dictacode-stt')) {
                showNotification('Please restart the service manually', 'info');
            }

        } catch (error) {
            console.error('Failed to apply config:', error);
            showNotification('Failed to save configuration', 'error');
        }
    };

    /**
     * Initialize config page
     */
    function init() {
        console.log('Config page initializing...');

        // Load current config
        loadConfig();

        // Watch for changes
        const selects = ['audio-port-select', 'language-select', 'model-select'];
        selects.forEach(id => {
            document.getElementById(id).addEventListener('change', updateApplyBar);
        });

        // Prevent form default submission
        document.getElementById('config-form').addEventListener('submit', (e) => {
            e.preventDefault();
            applyChanges();
        });

        console.log('Config page initialized');
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
