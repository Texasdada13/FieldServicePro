/**
 * phase_manager.js
 * Handles phase status changes, drag-drop reorder, inspection recording, and deletion via AJAX.
 */
'use strict';

var PhaseManager = (function () {

  // -- Inline Status Change --
  function initStatusChanges() {
    document.addEventListener('click', function (e) {
      var target = e.target.closest('.phase-status-change');
      if (!target) return;
      e.preventDefault();

      var phaseId = target.dataset.phaseId;
      var jobId = target.dataset.jobId;
      var newStatus = target.dataset.newStatus;
      var note = null;

      if (newStatus === 'on_hold') {
        note = prompt('Reason for placing phase on hold?');
        if (note === null) return;
      }

      fetch('/jobs/' + jobId + '/phases/' + phaseId + '/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ status: newStatus, note: note }),
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          showToast('Phase moved to "' + newStatus.replace(/_/g, ' ') + '"', 'success');
          updatePhaseCard(data.phase);
          updateJobProgressHeader(data.job_summary);
          // Reload for full UI refresh
          setTimeout(function () { location.reload(); }, 600);
        } else {
          showToast(data.error || 'Could not update status', 'danger');
        }
      })
      .catch(function (err) {
        showToast('Network error', 'danger');
        console.error(err);
      });
    });
  }

  // -- Drag-and-Drop Reordering --
  function initDragReorder() {
    var timeline = document.getElementById('phaseTimeline');
    if (!timeline) return;

    var jobId = timeline.dataset.jobId;
    var dragging = null;

    timeline.addEventListener('dragstart', function (e) {
      var item = e.target.closest('.phase-item');
      if (!item) return;
      dragging = item;
      item.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
    });

    timeline.addEventListener('dragover', function (e) {
      e.preventDefault();
      var item = e.target.closest('.phase-item');
      if (!item || item === dragging) return;
      timeline.querySelectorAll('.drag-over').forEach(function (el) { el.classList.remove('drag-over'); });
      item.classList.add('drag-over');
    });

    timeline.addEventListener('drop', function (e) {
      e.preventDefault();
      var target = e.target.closest('.phase-item');
      if (!target || target === dragging) return;
      timeline.insertBefore(dragging, target);
      saveNewOrder(jobId);
    });

    timeline.addEventListener('dragend', function () {
      if (dragging) dragging.classList.remove('dragging');
      timeline.querySelectorAll('.drag-over').forEach(function (el) { el.classList.remove('drag-over'); });
      dragging = null;
    });

    timeline.querySelectorAll('.phase-item').forEach(function (item) {
      item.setAttribute('draggable', 'true');
    });
  }

  function saveNewOrder(jobId) {
    var timeline = document.getElementById('phaseTimeline');
    var phaseIds = [];
    timeline.querySelectorAll('.phase-item').forEach(function (el) {
      phaseIds.push(el.dataset.phaseId);
    });

    fetch('/jobs/' + jobId + '/phases/reorder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify({ phase_ids: phaseIds }),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (!data.success) showToast('Could not save new order', 'warning');
    })
    .catch(function (err) { console.error('Reorder error:', err); });
  }

  // -- Inspection Recording --
  function initInspections() {
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('.record-inspection');
      if (!btn) return;

      var phaseId = btn.dataset.phaseId;
      var jobId = btn.dataset.jobId;
      var passed = btn.dataset.passed === 'true';
      var notes = passed
        ? prompt('Inspection notes (optional):')
        : prompt('Describe what failed:');
      if (!passed && notes === null) return;

      fetch('/jobs/' + jobId + '/phases/' + phaseId + '/inspection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ passed: passed, notes: notes || '' }),
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          showToast(passed ? 'Inspection passed!' : 'Inspection failure recorded', passed ? 'success' : 'warning');
          location.reload();
        } else {
          showToast(data.error || 'Error recording inspection', 'danger');
        }
      })
      .catch(function () { showToast('Network error', 'danger'); });
    });
  }

  // -- Phase Delete --
  function initDeletePhase() {
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('.phase-delete-btn');
      if (!btn) return;

      var phaseId = btn.dataset.phaseId;
      var jobId = btn.dataset.jobId;
      var title = btn.dataset.phaseTitle;

      if (!confirm('Remove phase "' + title + '"?\n\nIf the phase has logged activity, it will be marked as Skipped instead.')) return;

      fetch('/jobs/' + jobId + '/phases/' + phaseId + '/delete', {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          var item = document.getElementById('phase-item-' + phaseId);
          if (item) item.remove();
          showToast('Phase "' + title + '" removed', 'success');
        } else {
          showToast(data.error || 'Could not delete phase', 'danger');
        }
      })
      .catch(function () { showToast('Network error', 'danger'); });
    });
  }

  // -- DOM Update Helpers --
  function updatePhaseCard(phaseData) {
    var item = document.getElementById('phase-item-' + phaseData.id);
    if (!item) return;
    var badge = item.querySelector('.phase-number-badge');
    if (badge) badge.className = 'phase-number-badge status-' + phaseData.status;
    var card = item.querySelector('.phase-card');
    if (card) {
      card.className = 'phase-card status-' + phaseData.status;
      card.style.width = '100%';
    }
  }

  function updateJobProgressHeader(summary) {
    if (!summary) return;
    var pctEl = document.querySelector('.phases-progress-header .fill');
    if (pctEl) pctEl.style.width = summary.percent + '%';
  }

  // -- Toast --
  function showToast(message, type) {
    type = type || 'info';
    var toast = document.createElement('div');
    toast.style.cssText = 'position:fixed;bottom:1rem;right:1rem;z-index:9999;padding:0.75rem 1.25rem;border-radius:var(--radius-md);color:#fff;font-size:var(--font-size-sm);box-shadow:var(--shadow-lg);';
    toast.style.background = type === 'success' ? 'var(--color-success)' : type === 'danger' ? 'var(--color-danger)' : type === 'warning' ? 'var(--color-warning)' : 'var(--color-accent)';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(function () { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.3s'; }, 3500);
    setTimeout(function () { toast.remove(); }, 4000);
  }

  // -- Init --
  function init() {
    initStatusChanges();
    initDragReorder();
    initInspections();
    initDeletePhase();
  }

  return { init: init };
})();

document.addEventListener('DOMContentLoaded', PhaseManager.init);
