/**
 * quick_log.js — Quick Communication Log modal controller
 */
(function() {
    'use strict';

    function openQuickLog(prefill) {
        prefill = prefill || {};
        var overlay = document.getElementById('quickLogOverlay');
        if (!overlay) return;

        // Reset form
        var form = document.getElementById('quickLogForm');
        if (form) form.reset();
        document.querySelectorAll('.ql-type-tile').forEach(function(t) {
            t.style.borderColor = 'var(--color-border)';
            t.style.background = '';
        });
        document.getElementById('qlTypeInput').value = '';
        document.getElementById('qlJobSelect').innerHTML = '<option value="">—</option>';

        // Set current datetime
        var now = new Date();
        var pad = function(n) { return String(n).padStart(2, '0'); };
        document.getElementById('qlCommDate').value =
            now.getFullYear() + '-' + pad(now.getMonth()+1) + '-' + pad(now.getDate()) +
            'T' + pad(now.getHours()) + ':' + pad(now.getMinutes());

        // Auto-detect context from body data attributes
        var body = document.body;
        var clientId = prefill.client_id || body.dataset.clientId || '';
        var jobId = prefill.job_id || body.dataset.jobId || '';

        if (clientId) {
            document.getElementById('qlClientSelect').value = clientId;
            qlLoadEntities(clientId, jobId);
        }

        overlay.style.display = 'flex';
    }

    function closeQuickLog() {
        var overlay = document.getElementById('quickLogOverlay');
        if (overlay) overlay.style.display = 'none';
    }

    // Type tile selection
    document.addEventListener('click', function(e) {
        var tile = e.target.closest('.ql-type-tile');
        if (!tile) return;
        document.querySelectorAll('.ql-type-tile').forEach(function(t) {
            t.style.borderColor = 'var(--color-border)';
            t.style.background = '';
        });
        tile.style.borderColor = 'var(--color-accent)';
        tile.style.background = 'rgba(13,148,136,0.08)';
        document.getElementById('qlTypeInput').value = tile.dataset.type;
    });

    // Backdrop click to close
    var overlay = document.getElementById('quickLogOverlay');
    if (overlay) overlay.addEventListener('click', function(e) { if (e.target === this) closeQuickLog(); });

    // Keyboard shortcut: Ctrl+L
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'l') {
            e.preventDefault();
            openQuickLog();
        }
    });

    // FAB click
    var fab = document.getElementById('commLogFAB');
    if (fab) fab.addEventListener('click', function() { openQuickLog(); });

    // Client -> entities loader
    window.qlLoadEntities = function(clientId, preselectJobId) {
        if (!clientId) return;
        fetch('/communications/api/client/' + clientId + '/entities')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var sel = document.getElementById('qlJobSelect');
                sel.innerHTML = '<option value="">—</option>';
                (data.jobs || []).forEach(function(j) {
                    var opt = document.createElement('option');
                    opt.value = j.id;
                    opt.textContent = j.number + ' — ' + j.title;
                    if (String(j.id) === String(preselectJobId)) opt.selected = true;
                    sel.appendChild(opt);
                });
            });
    };

    // Template loader
    window.qlLoadTemplate = function(templateId) {
        if (!templateId) return;
        fetch('/communications/api/template/' + templateId)
            .then(function(r) { return r.json(); })
            .then(function(t) {
                if (t.communication_type) {
                    document.getElementById('qlTypeInput').value = t.communication_type;
                    document.querySelectorAll('.ql-type-tile').forEach(function(tile) {
                        if (tile.dataset.type === t.communication_type) {
                            tile.style.borderColor = 'var(--color-accent)';
                            tile.style.background = 'rgba(13,148,136,0.08)';
                        }
                    });
                }
                if (t.subject) document.getElementById('qlSubject').value = t.subject;
                if (t.follow_up_required) {
                    document.getElementById('qlFuCheck').checked = true;
                    document.getElementById('qlFuDate').style.display = 'inline-block';
                    if (t.follow_up_date) document.getElementById('qlFuDate').value = t.follow_up_date;
                }
            });
    };

    // AJAX submit
    var form = document.getElementById('quickLogForm');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            if (!document.getElementById('qlTypeInput').value) { alert('Select a type.'); return; }
            var formData = new FormData(this);
            fetch('/communications/quick-log', {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                body: formData,
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    closeQuickLog();
                    // Show brief notification
                    var notif = document.createElement('div');
                    notif.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--color-success);color:#fff;padding:8px 20px;border-radius:var(--radius-md);z-index:1200;font-size:var(--font-size-sm);box-shadow:0 4px 12px rgba(0,0,0,0.2);';
                    notif.textContent = 'Communication ' + data.log_number + ' logged.';
                    document.body.appendChild(notif);
                    setTimeout(function() { notif.remove(); }, 3000);
                } else {
                    alert('Error: ' + (data.error || 'Unknown'));
                }
            });
        });
    }

    // Expose globally
    window.openQuickLog = openQuickLog;
    window.closeQuickLog = closeQuickLog;
})();
