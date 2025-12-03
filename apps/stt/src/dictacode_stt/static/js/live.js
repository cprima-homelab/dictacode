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

    // v0.3.16: Update HID typing pause and mic mute status
    updateTypingStatus(components.hid_typing?.paused || false);
    updateMuteStatus(components.audio?.muted || false);

    // v0.3.17: Update trace panel
    if (components.traces) {
      updateTracePanel(components.traces.stats || {}, components.traces.recent || []);
    }
  }

  /**
   * Update trace panel with stats and recent traces (v0.3.17)
   */
  function updateTracePanel(stats, traces) {
    // Update summary counts
    setText('trace-completed', stats.completed || 0);
    setText('trace-dropped', stats.dropped || 0);
    setText('trace-in-progress', stats.in_progress || 0);

    // Update drop histogram
    updateDropHistogram(stats.drop_points || {});

    // Update trace list
    updateTraceList(traces || []);
  }

  /**
   * Update drop point histogram (v0.3.17)
   */
  function updateDropHistogram(dropPoints) {
    const container = document.getElementById('histogram-bars');
    if (!container) return;

    const entries = Object.entries(dropPoints);
    if (entries.length === 0) {
      container.innerHTML = '<span class="empty-state">No drops recorded</span>';
      return;
    }

    const maxCount = Math.max(...entries.map(([_, count]) => count));

    container.innerHTML = entries.map(([point, count]) => {
      const height = Math.max(10, (count / maxCount) * 50); // Min 10px height
      const label = point.replace(/_/g, ' ');
      return `
        <div class="histogram-bar" style="height: ${height}px">
          <span class="count">${count}</span>
          <span class="label">${escapeHtml(label)}</span>
        </div>
      `;
    }).join('');
  }

  /**
   * Update trace list table (v0.3.17)
   */
  function updateTraceList(traces) {
    const tbody = document.getElementById('trace-list');
    if (!tbody) return;

    if (!traces || traces.length === 0) {
      tbody.innerHTML = '<tr class="empty-state"><td colspan="5">No traces yet</td></tr>';
      return;
    }

    tbody.innerHTML = traces.map(t => {
      const latency = t.latency_ms ? `${Math.round(t.latency_ms)}ms` : '-';
      const age = formatRelativeTime(t.created_at);
      const dropPoint = t.drop_point ? escapeHtml(t.drop_point.replace(/_/g, ' ')) : '-';
      const traceIdShort = t.trace_id ? t.trace_id.slice(-12) : '-';
      return `
        <tr class="${t.status}">
          <td class="trace-id" title="${escapeHtml(t.trace_id || '')}">${escapeHtml(traceIdShort)}</td>
          <td>${escapeHtml(t.status || '-')}</td>
          <td>${dropPoint}</td>
          <td>${latency}</td>
          <td>${age}</td>
        </tr>
      `;
    }).join('');
  }

  /**
   * Update HID typing pause button and indicator (v0.3.16)
   */
  function updateTypingStatus(paused) {
    const btn = document.getElementById('pause-typing-btn');
    const indicator = document.getElementById('typing-status');

    if (btn) {
      btn.dataset.paused = paused;
      btn.textContent = paused ? '\u25B6 Resume Typing' : '\u23F8 Pause Typing';
      btn.classList.toggle('active', paused);
    }

    if (indicator) {
      indicator.classList.toggle('visible', paused);
    }
  }

  /**
   * Update microphone mute button and indicator (v0.3.16)
   */
  function updateMuteStatus(muted) {
    const btn = document.getElementById('mute-mic-btn');
    const indicator = document.getElementById('mute-status');

    if (btn) {
      btn.dataset.muted = muted;
      btn.textContent = muted ? '\uD83D\uDD0A Unmute Mic' : '\uD83C\uDF99 Mute Mic';
      btn.classList.toggle('active', muted);
    }

    if (indicator) {
      indicator.classList.toggle('visible', muted);
    }
  }

  /**
   * Toggle HID typing pause (v0.3.16)
   */
  async function toggleTypingPause() {
    const btn = document.getElementById('pause-typing-btn');
    if (!btn) return;

    const isPaused = btn.dataset.paused === 'true';
    const endpoint = isPaused ? '/v1/api/hid/resume' : '/v1/api/hid/pause';

    btn.disabled = true;
    try {
      const resp = await fetch(endpoint, { method: 'POST' });
      const data = await resp.json();
      if (data.status === 'ok') {
        updateTypingStatus(data.hid_paused);
      } else {
        console.error('Failed to toggle typing pause:', data.message);
      }
    } catch (err) {
      console.error('Failed to toggle typing pause:', err);
    } finally {
      btn.disabled = false;
    }
  }

  /**
   * Toggle microphone mute (v0.3.16)
   */
  async function toggleMicMute() {
    const btn = document.getElementById('mute-mic-btn');
    if (!btn) return;

    const isMuted = btn.dataset.muted === 'true';
    const endpoint = isMuted ? '/v1/api/audio/unmute' : '/v1/api/audio/mute';

    btn.disabled = true;
    try {
      const resp = await fetch(endpoint, { method: 'POST' });
      const data = await resp.json();
      if (data.status === 'ok') {
        updateMuteStatus(data.mic_muted);
      } else {
        console.error('Failed to toggle mic mute:', data.message);
      }
    } catch (err) {
      console.error('Failed to toggle mic mute:', err);
    } finally {
      btn.disabled = false;
    }
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

    // v0.3.16: Bind pause typing button
    const pauseTypingBtn = document.getElementById('pause-typing-btn');
    if (pauseTypingBtn) {
      pauseTypingBtn.addEventListener('click', toggleTypingPause);
    }

    // v0.3.16: Bind mute mic button
    const muteMicBtn = document.getElementById('mute-mic-btn');
    if (muteMicBtn) {
      muteMicBtn.addEventListener('click', toggleMicMute);
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
