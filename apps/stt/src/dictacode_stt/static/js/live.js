/**
 * Live Status Page - Real-time pipeline monitoring (v0.3.14)
 */
(function() {
  'use strict';

  const API_URL = '/v1/api/status/live';
  const REFRESH_INTERVAL = 5000; // 5 seconds

  let autoRefreshTimer = null;

  /**
   * Format timestamp as relative time (e.g., "2s ago")
   */
  function formatRelativeTime(timestamp) {
    if (!timestamp) return '-';
    const now = Date.now() / 1000;
    const diff = now - timestamp;

    if (diff < 0) return 'just now';
    if (diff < 60) return `${Math.floor(diff)}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  }

  /**
   * Format current time for display
   */
  function formatTime(date) {
    return date.toLocaleTimeString();
  }

  /**
   * Escape HTML to prevent XSS (v0.3.14)
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Update transcription history panel (v0.3.14)
   */
  function updateTranscriptions(transcriptions) {
    const list = document.getElementById('transcription-list');
    const indicator = document.getElementById('transcription-indicator');

    if (!list) return;

    // Update indicator based on recent activity
    if (indicator) {
      indicator.classList.remove('ok', 'warning', 'error');
      if (transcriptions && transcriptions.length > 0) {
        const now = Date.now() / 1000;
        const mostRecent = transcriptions[0]?.timestamp;
        if (mostRecent && (now - mostRecent) < 10) {
          indicator.classList.add('ok');
        } else {
          indicator.classList.add('warning');
        }
      } else {
        indicator.classList.add('warning');
      }
    }

    // Render transcription list
    if (!transcriptions || transcriptions.length === 0) {
      list.innerHTML = '<li class="empty-state">No transcriptions yet</li>';
      return;
    }

    list.innerHTML = transcriptions.map(t => `
      <li class="transcription-entry">
        <span class="text">${escapeHtml(t.text)}</span>
        <span class="time">${formatRelativeTime(t.timestamp)}</span>
      </li>
    `).join('');
  }

  /**
   * Set element text safely
   */
  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text ?? '-';
  }

  /**
   * Set indicator class (ok/warning/error)
   */
  function setIndicator(id, status) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('ok', 'warning', 'error');
    el.classList.add(status);
  }

  /**
   * Set card status class
   */
  function setCardStatus(id, status) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('healthy', 'stale', 'error');
    el.classList.add(status);
  }

  /**
   * Set flow stage status
   */
  function setStageStatus(id, isFresh, hasError) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('fresh', 'stale', 'error');
    if (hasError) {
      el.classList.add('error');
    } else if (isFresh) {
      el.classList.add('fresh');
    } else {
      el.classList.add('stale');
    }
  }

  /**
   * Update health summary based on flow status
   */
  function updateHealthSummary(flow, components) {
    const summary = document.getElementById('health-summary');
    const icon = document.getElementById('health-icon');
    const title = document.getElementById('health-title');
    const desc = document.getElementById('health-desc');

    if (!summary) return;

    // Determine overall health
    const hasErrors = components.audio?.error || components.asr?.error ||
                      components.transport?.error;
    const hasStale = flow.asr_stale || flow.send_stale;
    const allFresh = flow.audio_fresh && flow.asr_fresh && flow.send_fresh;

    summary.classList.remove('healthy', 'degraded', 'error');

    if (hasErrors) {
      summary.classList.add('error');
      icon.textContent = '\u274C'; // X
      title.textContent = 'System Error';
      desc.textContent = 'One or more components have errors';
    } else if (hasStale) {
      summary.classList.add('degraded');
      icon.textContent = '\u26A0'; // Warning
      title.textContent = 'Pipeline Stale';
      if (flow.asr_stale) {
        desc.textContent = 'ASR stage is stale - audio is flowing but not being transcribed';
      } else if (flow.send_stale) {
        desc.textContent = 'Send stage is stale - transcriptions are not being sent';
      }
    } else if (allFresh) {
      summary.classList.add('healthy');
      icon.textContent = '\u2705'; // Checkmark
      title.textContent = 'System Healthy';
      desc.textContent = 'All pipeline stages are operating normally';
    } else {
      summary.classList.add('degraded');
      icon.textContent = '\u23F8'; // Pause
      title.textContent = 'Pipeline Idle';
      desc.textContent = 'Waiting for activity - no recent data flow';
    }
  }

  /**
   * Update the UI with live status data
   */
  function updateUI(data) {
    const { components, flow, timestamp } = data;

    // Update last refresh time
    setText('last-update', formatTime(new Date()));

    // === Flow Pipeline ===
    const audioTime = components.audio?.last_audio_ts;
    const asrTime = components.asr?.last_asr_ts;
    const sendTime = components.transport?.last_send_ts;

    setText('audio-time', formatRelativeTime(audioTime));
    setText('asr-time', formatRelativeTime(asrTime));
    setText('send-time', formatRelativeTime(sendTime));

    setStageStatus('stage-audio', flow.audio_fresh, !!components.audio?.error);
    setStageStatus('stage-asr', flow.asr_fresh, !!components.asr?.error);
    setStageStatus('stage-send', flow.send_fresh, !!components.transport?.error);

    // Flow arrows
    const arrow1 = document.getElementById('arrow-1');
    const arrow2 = document.getElementById('arrow-2');
    if (arrow1) {
      arrow1.classList.toggle('active', flow.audio_fresh && flow.asr_fresh);
    }
    if (arrow2) {
      arrow2.classList.toggle('active', flow.asr_fresh && flow.send_fresh);
    }

    // === Status Cards ===
    // State card
    const state = components.state || {};
    setText('state-value', (state.state || 'unknown').toUpperCase());
    setText('state-sub', state.model ? `Model: ${state.model}` : '-');
    setCardStatus('card-state', state.state === 'listening' ? 'healthy' : 'stale');

    // Mic card
    const audio = components.audio || {};
    const micPresent = audio.mic_present;
    setText('mic-value', micPresent ? 'Connected' : 'Not Found');
    setText('mic-sub', audio.active_port || 'No port');
    setCardStatus('card-mic', micPresent ? 'healthy' : 'error');

    // ASR card
    const asr = components.asr || {};
    setText('asr-value', asr.backend || 'Unknown');
    const asrSuccess = asr.asr_success_total || 0;
    const asrErrors = asr.asr_error_total || 0;
    setText('asr-sub', `${asrSuccess} ok / ${asrErrors} err`);
    setCardStatus('card-asr', asr.available ? (flow.asr_fresh ? 'healthy' : 'stale') : 'error');

    // Transport card
    const transport = components.transport || {};
    setText('transport-value', transport.connected ? 'Connected' : 'Disconnected');
    setText('transport-sub', transport.type || 'Unknown');
    setCardStatus('card-transport', transport.connected ? (flow.send_fresh ? 'healthy' : 'stale') : 'error');

    // === Component Details ===
    // Audio
    setText('audio-port', audio.active_port || '-');
    setText('audio-mic-present', audio.mic_present ? 'Yes' : 'No');
    setText('audio-chunks', audio.audio_chunks_total ?? '-');
    setText('audio-last-ts', formatRelativeTime(audio.last_audio_ts));
    setIndicator('audio-indicator', audio.error ? 'error' : (flow.audio_fresh ? 'ok' : 'warning'));

    // ASR
    setText('asr-backend', asr.backend || '-');
    setText('asr-available', asr.available ? 'Yes' : 'No');
    setText('asr-success', asr.asr_success_total ?? '-');
    setText('asr-errors', asr.asr_error_total ?? '-');
    setIndicator('asr-indicator', asr.error ? 'error' : (asr.available && flow.asr_fresh ? 'ok' : 'warning'));

    // Transport
    setText('transport-type', transport.type || '-');
    setText('transport-connected', transport.connected ? 'Yes' : 'No');
    setText('transport-success', transport.send_success_total ?? '-');
    setText('transport-errors', transport.send_error_total ?? '-');
    setIndicator('transport-indicator', transport.error ? 'error' : (transport.connected && flow.send_fresh ? 'ok' : 'warning'));

    // IPC
    const ipc = components.ipc || {};
    setText('ipc-available', ipc.available ? 'Yes' : 'No');
    setText('ipc-socket', ipc.socket_path ? ipc.socket_path.split('/').pop() : '-');
    setText('ipc-running', ipc.running ? 'Yes' : 'No');
    setIndicator('ipc-indicator', ipc.available ? 'ok' : 'error');

    // Update health summary
    updateHealthSummary(flow, components);

    // v0.3.14: Update transcription history
    updateTranscriptions(components.transcriptions || []);
  }

  /**
   * Show error state in UI
   */
  function showError(message) {
    const summary = document.getElementById('health-summary');
    const icon = document.getElementById('health-icon');
    const title = document.getElementById('health-title');
    const desc = document.getElementById('health-desc');

    if (summary) {
      summary.classList.remove('healthy', 'degraded');
      summary.classList.add('error');
    }
    if (icon) icon.textContent = '\u274C';
    if (title) title.textContent = 'Connection Error';
    if (desc) desc.textContent = message;
  }

  /**
   * Fetch live status from API
   */
  async function fetchStatus() {
    try {
      const resp = await fetch(API_URL);
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      updateUI(data);
    } catch (err) {
      console.error('Failed to fetch live status:', err);
      showError(err.message || 'Failed to connect to service');
    }
  }

  /**
   * Toggle auto-refresh
   */
  function toggleAutoRefresh(enabled) {
    if (autoRefreshTimer) {
      clearInterval(autoRefreshTimer);
      autoRefreshTimer = null;
    }
    if (enabled) {
      autoRefreshTimer = setInterval(fetchStatus, REFRESH_INTERVAL);
    }
  }

  /**
   * Initialize page
   */
  function init() {
    // Bind refresh button
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', fetchStatus);
    }

    // Bind auto-refresh checkbox
    const autoRefresh = document.getElementById('auto-refresh');
    if (autoRefresh) {
      autoRefresh.addEventListener('change', (e) => {
        toggleAutoRefresh(e.target.checked);
      });
      // Start auto-refresh if checked
      if (autoRefresh.checked) {
        toggleAutoRefresh(true);
      }
    }

    // Initial fetch
    fetchStatus();
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
