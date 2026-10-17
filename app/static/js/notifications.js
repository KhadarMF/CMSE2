(() => {
  'use strict';
  const badge = document.getElementById('notificationUnreadBadge');
  if (!badge) return;
  badge.setAttribute('aria-live', 'polite');
  const total = document.getElementById('notificationUnreadTotal');
  const hint = document.getElementById('notificationRefreshHint');
  let latest = hint ? Number(hint.dataset.latestId || 0) : null;
  let busy = false, stopped = false, lastPoll = 0;
  async function refresh() {
    if (document.hidden || busy || stopped || Date.now() - lastPoll < 2000) return;
    busy = true; lastPoll = Date.now();
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(badge.dataset.countUrl, {credentials:'same-origin', cache:'no-store', signal:controller.signal});
      if (response.redirected || response.status === 401 || response.status === 403) { stopped = true; return; }
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) return;
      const data = await response.json();
      badge.textContent = String(data.unread);
      badge.parentElement.setAttribute('aria-label', 'Notifications: ' + data.unread + ' unread');
      if (total) total.textContent = String(data.unread);
      if (hint && latest !== null && data.latest_id > latest) hint.hidden = false;
      if (latest === null) latest = data.latest_id;
    } catch (_) { /* Retry on the next interval after a temporary network failure. */ }
    finally { clearTimeout(timeout); busy = false; }
  }
  refresh();
  setInterval(refresh, 20000);
  document.addEventListener('visibilitychange', refresh);
  window.addEventListener('focus', refresh);
})();
