/**
 * Network Command Logger for MetaTFT (Overwolf DevTools)
 *
 * Paste into MetaTFT's DevTools console to log network-like commands.
 *
 * Logs:
 * - fetch() requests
 * - XMLHttpRequest open/send
 * - WebSocket sends
 *
 * Output is printed to console and stored in window.__tftCoachNetworkLog.
 */

(function() {
  'use strict';

  const LOG_KEY = '__tftCoachNetworkLog';
  const MAX_ENTRIES = 5000;
  const DEBUG = true;
  const WS_URL = 'ws://127.0.0.1:8765/network-log';
  const RECONNECT_INTERVAL = 3000;
  let ws = null;
  let wsReconnectTimer = null;

  if (!window[LOG_KEY]) {
    window[LOG_KEY] = [];
  }

  function pushLog(entry) {
    window[LOG_KEY].push(entry);
    if (window[LOG_KEY].length > MAX_ENTRIES) {
      window[LOG_KEY].shift();
    }
    if (DEBUG) {
      console.log('[NetLog]', entry);
    }
    sendToServer(entry);
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function normalizeUrl(url) {
    try {
      return typeof url === 'string' ? url : url.url || String(url);
    } catch (e) {
      return String(url);
    }
  }

  function connectWebSocket() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        if (DEBUG) {
          console.log('[NetLog] WebSocket connected');
        }
      };
      ws.onclose = () => {
        if (DEBUG) {
          console.log('[NetLog] WebSocket disconnected, retrying...');
        }
        scheduleReconnect();
      };
      ws.onerror = () => {
        scheduleReconnect();
      };
    } catch (e) {
      scheduleReconnect();
    }
  }

  function scheduleReconnect() {
    if (wsReconnectTimer) {
      clearTimeout(wsReconnectTimer);
    }
    wsReconnectTimer = setTimeout(connectWebSocket, RECONNECT_INTERVAL);
  }

  function sendToServer(entry) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      return;
    }
    try {
      ws.send(JSON.stringify(entry));
    } catch (e) {
      if (DEBUG) {
        console.warn('[NetLog] Failed to send log entry', e);
      }
    }
  }

  // Hook fetch
  if (window.fetch) {
    const originalFetch = window.fetch.bind(window);
    window.fetch = function(input, init = {}) {
      const method = (init.method || 'GET').toUpperCase();
      const url = normalizeUrl(input);
      pushLog({
        ts: nowIso(),
        type: 'fetch',
        method,
        url,
        body: init.body || null,
      });
      return originalFetch(input, init);
    };
  }

  // Hook XMLHttpRequest
  if (window.XMLHttpRequest) {
    const OriginalXHR = window.XMLHttpRequest;
    function WrappedXHR() {
      const xhr = new OriginalXHR();
      let method = 'GET';
      let url = '';

      const originalOpen = xhr.open;
      xhr.open = function(m, u, ...rest) {
        method = (m || 'GET').toUpperCase();
        url = u;
        return originalOpen.call(xhr, m, u, ...rest);
      };

      const originalSend = xhr.send;
      xhr.send = function(body) {
        pushLog({
          ts: nowIso(),
          type: 'xhr',
          method,
          url,
          body: body || null,
        });
        return originalSend.call(xhr, body);
      };

      return xhr;
    }

    window.XMLHttpRequest = WrappedXHR;
  }

  // Hook WebSocket
  if (window.WebSocket) {
    const OriginalWebSocket = window.WebSocket;
    window.WebSocket = function(url, protocols) {
      const ws = new OriginalWebSocket(url, protocols);
      const originalSend = ws.send;

      ws.send = function(data) {
        pushLog({
          ts: nowIso(),
          type: 'ws',
          method: 'SEND',
          url: url,
          body: data || null,
        });
        return originalSend.call(ws, data);
      };

      return ws;
    };
  }

  connectWebSocket();
  console.log('[NetLog] Network logging installed. Entries at window.__tftCoachNetworkLog');
  console.log(`[NetLog] Streaming to ${WS_URL}`);
})();
