/**
 * Scratch page: dump API-visible state/diagnostics/license (IPC-backed).
 */
(function() {
  'use strict';

  const targets = [
    { id: 'state-dump', url: '/v1/api/service/state' },
    { id: 'history-dump', url: '/v1/api/service/state/history' },
    { id: 'diag-dump', url: '/v1/api/diagnostics/status' },
    { id: 'license-dump', url: '/v1/api/license' },
    { id: 'live-dump', url: '/v1/api/status/live' },  // v0.3.13
  ];

  async function fetchAndRender(target) {
    const el = document.getElementById(target.id);
    if (!el) return;
    el.textContent = 'Loading...';
    try {
      const resp = await fetch(target.url);
      const data = await resp.json();
      el.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      el.textContent = `Error: ${err.message}`;
      console.error(`Failed to fetch ${target.url}:`, err);
    }
  }

  function refreshAll() {
    targets.forEach(fetchAndRender);
  }

  function init() {
    const btn = document.getElementById('refresh-btn');
    if (btn) {
      btn.addEventListener('click', refreshAll);
    }
    refreshAll();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
