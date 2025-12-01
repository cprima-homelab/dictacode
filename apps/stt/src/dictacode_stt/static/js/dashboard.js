/**
 * Dashboard WebSocket integration and live updates (v0.3.0 Phase 3)
 */

(function() {
    'use strict';

    let ws = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 10;
    const reconnectDelay = 1000;
    let reconnectTimeout = null;
    let transcriptionCount = 0;
    let connectedAt = null;
    let uptimeInterval = null;

    const wsUrl = `ws://${window.location.host}/api/ws`;

    /**
     * Update service status badge
     */
    function updateServiceStatus(mode) {
        const badge = document.getElementById('service-status');
        const modeEl = document.getElementById('service-mode');

        if (!badge || !modeEl) return;

        badge.textContent = `● ${mode}`;
        modeEl.textContent = mode.toUpperCase();

        // Update badge style based on mode
        badge.className = 'badge';
        if (mode === 'LISTENING' || mode === 'listening') {
            badge.classList.add('badge-ok');
        } else if (mode === 'PAUSED' || mode === 'paused') {
            badge.classList.add('badge-warning');
        } else {
            badge.classList.add('badge-error');
        }
    }

    /**
     * Update link health status
     */
    function updateLinkStatus(healthy, lastActivity, reconnects) {
        const badge = document.getElementById('link-status');
        const healthyEl = document.getElementById('link-healthy');
        const activityEl = document.getElementById('link-activity');
        const reconnectsEl = document.getElementById('link-reconnects');

        if (badge) {
            badge.className = 'badge';
            badge.textContent = healthy ? 'Link OK' : 'Reconnecting';
            badge.classList.add(healthy ? 'badge-ok' : 'badge-warning');
        }

        if (healthyEl) {
            healthyEl.textContent = healthy ? 'Connected' : 'Reconnecting';
            healthyEl.className = 'badge';
            healthyEl.classList.add(healthy ? 'badge-ok' : 'badge-warning');
        }

        if (activityEl && lastActivity) {
            const timestamp = new Date(lastActivity);
            const seconds = Math.floor((Date.now() - timestamp.getTime()) / 1000);
            activityEl.textContent = seconds < 60 ? `${seconds}s ago` : `${Math.floor(seconds / 60)}m ago`;
        }

        if (reconnectsEl) {
            reconnectsEl.textContent = reconnects || 0;
        }
    }

    /**
     * Add transcription to live feed
     */
    function addTranscription(text, isFinal) {
        const feed = document.getElementById('transcription-live');
        if (!feed) return;

        const item = document.createElement('div');
        item.className = 'transcription-item' + (isFinal ? ' final' : '');

        const timestamp = document.createElement('span');
        timestamp.className = 'timestamp';
        timestamp.textContent = new Date().toLocaleTimeString();

        const textSpan = document.createElement('span');
        textSpan.textContent = text;

        item.appendChild(timestamp);
        item.appendChild(textSpan);
        feed.appendChild(item);

        // Auto-scroll to bottom
        feed.scrollTop = feed.scrollHeight;

        // Update count
        if (isFinal) {
            transcriptionCount++;
            const countEl = document.getElementById('transcription-count');
            if (countEl) {
                countEl.textContent = transcriptionCount;
            }
        }

        // Keep only last 50 items
        while (feed.children.length > 50) {
            feed.removeChild(feed.firstChild);
        }
    }

    /**
     * Update uptime display
     */
    function updateUptime() {
        if (!connectedAt) return;

        const seconds = Math.floor((Date.now() - connectedAt) / 1000);
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;

        const uptimeEl = document.getElementById('service-uptime');
        if (uptimeEl) {
            if (hours > 0) {
                uptimeEl.textContent = `${hours}h ${mins}m`;
            } else if (mins > 0) {
                uptimeEl.textContent = `${mins}m ${secs}s`;
            } else {
                uptimeEl.textContent = `${secs}s`;
            }
        }
    }

    /**
     * Connect to WebSocket
     */
    function connect() {
        if (ws && ws.readyState !== WebSocket.CLOSED) {
            return;
        }

        console.log(`Connecting to ${wsUrl}...`);

        try {
            ws = new WebSocket(wsUrl);

            ws.onopen = function(event) {
                console.log('WebSocket connected');
                reconnectAttempts = 0;
                connectedAt = Date.now();

                if (!uptimeInterval) {
                    uptimeInterval = setInterval(updateUptime, 1000);
                }

                updateServiceStatus('LISTENING');
                updateLinkStatus(true, null, 0);
            };

            ws.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);

                    if (data.type === 'transcription') {
                        const isFinal = data.data.final || false;
                        const text = data.data.text || '';
                        addTranscription(text, isFinal);
                    } else if (data.type === 'status') {
                        if (data.data.mode) {
                            updateServiceStatus(data.data.mode);
                        }
                    } else if (data.type === 'supervisor' || data.type === 'link_status') {
                        const healthy = data.data.healthy !== undefined ? data.data.healthy : true;
                        const lastActivity = data.data.last_activity;
                        const reconnects = data.data.reconnect_attempts || 0;
                        updateLinkStatus(healthy, lastActivity, reconnects);
                    } else if (data.type === 'error') {
                        console.error('Server error:', data.data.message);
                        addTranscription(`ERROR: ${data.data.message}`, true);
                    }
                } catch (e) {
                    console.error('Failed to parse WebSocket message:', e);
                }
            };

            ws.onerror = function(event) {
                console.error('WebSocket error');
                updateLinkStatus(false, null, reconnectAttempts);
            };

            ws.onclose = function(event) {
                console.log(`WebSocket disconnected (code: ${event.code})`);
                updateLinkStatus(false, null, reconnectAttempts);

                if (uptimeInterval) {
                    clearInterval(uptimeInterval);
                    uptimeInterval = null;
                }

                // Auto-reconnect with exponential backoff
                if (reconnectAttempts < maxReconnectAttempts && event.code !== 1000) {
                    reconnectAttempts++;
                    const delay = Math.min(reconnectDelay * Math.pow(1.5, reconnectAttempts - 1), 30000);

                    console.log(`Reconnecting in ${(delay / 1000).toFixed(1)}s (attempt ${reconnectAttempts}/${maxReconnectAttempts})`);

                    reconnectTimeout = setTimeout(() => {
                        connect();
                    }, delay);
                }
            };
        } catch (e) {
            console.error('Failed to create WebSocket:', e);
        }
    }

    /**
     * Handle tab switching
     */
    function handleTabClick(event) {
        const button = event.currentTarget;
        const tab = button.getAttribute('data-tab');

        // Update tab buttons
        const buttons = document.querySelectorAll('.tablist button');
        buttons.forEach(btn => {
            btn.setAttribute('aria-selected', btn === button ? 'true' : 'false');
        });

        // Update tab panels
        const panels = document.querySelectorAll('.tabpanel');
        panels.forEach(panel => {
            if (panel.id === `${tab}-feed`) {
                panel.classList.add('active');
                panel.removeAttribute('hidden');
            } else {
                panel.classList.remove('active');
                panel.setAttribute('hidden', '');
            }
        });
    }

    /**
     * Initialize dashboard
     */
    function init() {
        console.log('Dashboard initializing...');

        // Connect to WebSocket
        connect();

        // Attach tab click handlers
        const tabButtons = document.querySelectorAll('.tablist button');
        tabButtons.forEach(button => {
            button.addEventListener('click', handleTabClick);
        });

        console.log('Dashboard initialized');
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Cleanup on page unload
    window.addEventListener('beforeunload', function() {
        if (ws) {
            ws.close(1000, 'Page unload');
        }
        if (reconnectTimeout) {
            clearTimeout(reconnectTimeout);
        }
        if (uptimeInterval) {
            clearInterval(uptimeInterval);
        }
    });
})();
