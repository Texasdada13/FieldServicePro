/* ══════════════════════════════════════════════════════════════
   FieldServicePro — Mobile Core JS
   ══════════════════════════════════════════════════════════════ */

'use strict';

/* ── API Helper ─────────────────────────────────────────────── */
const mAPI = {
  async post(url, data) {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.cookie.match(/csrf_token=([^;]+)/)?.[1] || ''
      },
      body: JSON.stringify(data)
    });
    return res.json();
  },
  async get(url) {
    const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
    return res.json();
  },
  async upload(url, formData) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '' },
      body: formData
    });
    return res.json();
  }
};

/* ── Toast Notifications ────────────────────────────────────── */
function mToast(message, type, duration) {
  type = type || 'info';
  duration = duration || 3500;
  var existing = document.getElementById('js-toast');
  if (existing) existing.remove();
  var toast = document.createElement('div');
  toast.id = 'js-toast';
  toast.className = 'm-toast m-toast-' + type;
  toast.innerHTML = message + '<button class="m-toast-close" onclick="this.parentElement.remove()">\u2715</button>';
  document.body.appendChild(toast);
  setTimeout(function() { toast.remove(); }, duration);
}

/* ── Loading Overlay ────────────────────────────────────────── */
function mLoading(show, message) {
  message = message || 'Loading\u2026';
  var overlay = document.getElementById('m-loading');
  if (show) {
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'm-loading';
      overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:9000;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:16px;color:white;font-weight:600;';
      overlay.innerHTML = '<div style="width:40px;height:40px;border:3px solid rgba(255,255,255,0.2);border-top-color:var(--color-accent,#0d9488);border-radius:50%;animation:spin 0.8s linear infinite;"></div><div>' + message + '</div>';
      if (!document.getElementById('m-spin-style')) {
        var style = document.createElement('style');
        style.id = 'm-spin-style';
        style.textContent = '@keyframes spin{to{transform:rotate(360deg)}}';
        document.head.appendChild(style);
      }
      document.body.appendChild(overlay);
    }
  } else {
    if (overlay) overlay.remove();
  }
}

/* ── Swipe Detection ────────────────────────────────────────── */
function mSwipe(element, opts) {
  var threshold = opts.threshold || 50;
  var startX = 0, startY = 0;
  element.addEventListener('touchstart', function(e) {
    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
  }, { passive: true });
  element.addEventListener('touchend', function(e) {
    var dx = e.changedTouches[0].clientX - startX;
    var dy = Math.abs(e.changedTouches[0].clientY - startY);
    if (dy > 30) return;
    if (dx > threshold && opts.onRight) opts.onRight();
    if (dx < -threshold && opts.onLeft) opts.onLeft();
  }, { passive: true });
}

/* ── Swipeable dismiss ──────────────────────────────────────── */
function initSwipeableDismiss(selector, onDismiss) {
  document.querySelectorAll(selector).forEach(function(item) {
    var content = item.querySelector('.m-notif-content') || item;
    var startX = 0;
    content.addEventListener('touchstart', function(e) { startX = e.touches[0].clientX; }, { passive: true });
    content.addEventListener('touchmove', function(e) {
      var dx = Math.max(0, e.touches[0].clientX - startX);
      content.style.transform = 'translateX(' + dx + 'px)';
    }, { passive: true });
    content.addEventListener('touchend', function(e) {
      var dx = e.changedTouches[0].clientX - startX;
      if (dx > 80) {
        item.style.transition = 'all 0.3s';
        item.style.opacity = '0';
        item.style.maxHeight = '0';
        item.style.marginBottom = '0';
        setTimeout(function() { item.remove(); if (onDismiss) onDismiss(item.dataset.id); }, 300);
      } else {
        content.style.transform = '';
      }
    }, { passive: true });
  });
}

/* ── Confirm Dialog ─────────────────────────────────────────── */
function mConfirm(message) {
  return new Promise(function(resolve) {
    var modal = document.createElement('div');
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:9100;display:flex;align-items:flex-end;padding:16px;';
    modal.innerHTML =
      '<div style="background:var(--color-bg-surface,#1e293b);border-radius:16px;padding:24px;width:100%;text-align:center;">' +
        '<p style="font-size:16px;margin:0 0 20px;font-weight:500;">' + message + '</p>' +
        '<div style="display:flex;gap:10px;">' +
          '<button id="m-confirm-cancel" class="m-btn m-btn--secondary" style="flex:1;">Cancel</button>' +
          '<button id="m-confirm-ok" class="m-btn m-btn--primary" style="flex:1;">Confirm</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(modal);
    modal.querySelector('#m-confirm-ok').onclick = function() { modal.remove(); resolve(true); };
    modal.querySelector('#m-confirm-cancel').onclick = function() { modal.remove(); resolve(false); };
  });
}

/* ── Confetti Animation ─────────────────────────────────────── */
function mConfetti() {
  var colors = ['#0d9488','#22c55e','#f59e0b','#6366f1','#ec4899','#f97316'];
  var wrap = document.createElement('div');
  wrap.className = 'm-confetti-wrap';
  for (var i = 0; i < 60; i++) {
    var piece = document.createElement('div');
    piece.className = 'm-confetti-piece';
    piece.style.cssText =
      'left:' + (Math.random() * 100) + '%;top:-20px;' +
      'background:' + colors[Math.floor(Math.random() * colors.length)] + ';' +
      'width:' + (Math.random() * 10 + 6) + 'px;height:' + (Math.random() * 10 + 6) + 'px;' +
      'animation-delay:' + (Math.random() * 1.5) + 's;' +
      'animation-duration:' + (Math.random() * 2 + 2) + 's;' +
      'border-radius:' + (Math.random() > 0.5 ? '50%' : '2px') + ';';
    wrap.appendChild(piece);
  }
  document.body.appendChild(wrap);
  setTimeout(function() { wrap.remove(); }, 4000);
}

/* ── Local Storage cache ────────────────────────────────────── */
var mCache = {
  set: function(key, data) {
    try { localStorage.setItem('fsp_' + key, JSON.stringify({ ts: Date.now(), data: data })); } catch(e) {}
  },
  get: function(key, maxAgeMs) {
    maxAgeMs = maxAgeMs || 3600000;
    try {
      var item = JSON.parse(localStorage.getItem('fsp_' + key));
      if (!item || Date.now() - item.ts > maxAgeMs) return null;
      return item.data;
    } catch(e) { return null; }
  },
  clear: function(key) { localStorage.removeItem('fsp_' + key); }
};

/* ── Time formatting ────────────────────────────────────────── */
function formatDuration(seconds) {
  var h = Math.floor(seconds / 3600);
  var m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? h + 'h ' + m + 'm' : m + 'm';
}

/* ── Live clock ─────────────────────────────────────────────── */
function startLiveClock(elementId) {
  var el = document.getElementById(elementId);
  if (!el) return;
  function tick() {
    var now = new Date();
    el.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
  tick();
  return setInterval(tick, 1000);
}

/* ── Elapsed timer ──────────────────────────────────────────── */
function startElapsedTimer(elementId, startTimestamp) {
  var el = document.getElementById(elementId);
  if (!el) return;
  function tick() {
    var elapsed = Math.floor((Date.now() - startTimestamp) / 1000);
    var h = Math.floor(elapsed / 3600);
    var m = Math.floor((elapsed % 3600) / 60);
    var s = elapsed % 60;
    el.textContent =
      String(h).padStart(2, '0') + ':' +
      String(m).padStart(2, '0') + ':' +
      String(s).padStart(2, '0');
  }
  tick();
  return setInterval(tick, 1000);
}

/* ── Category selector ──────────────────────────────────────── */
function initCategorySelector(inputId) {
  document.querySelectorAll('.m-category-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      document.querySelectorAll('.m-category-btn').forEach(function(b) { b.classList.remove('selected'); });
      btn.classList.add('selected');
      var input = document.getElementById(inputId);
      if (input) input.value = btn.dataset.value;
    });
  });
}

/* ── Auto-dismiss flash toasts on page load ─────────────────── */
document.addEventListener('DOMContentLoaded', function() {
  setTimeout(function() {
    document.querySelectorAll('.m-toast').forEach(function(t) { t.remove(); });
  }, 4000);
});
