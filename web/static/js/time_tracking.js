/**
 * Time Tracking JS — Clock in/out, elapsed timers, bulk actions
 */
document.addEventListener('DOMContentLoaded', function() {

    // ── Elapsed timers (update every second) ──
    function updateTimers() {
        document.querySelectorAll('.elapsed-timer').forEach(function(el) {
            var clockIn = el.dataset.clockIn;
            if (!clockIn) return;
            var start = new Date(clockIn);
            var now = new Date();
            var secs = Math.floor((now - start) / 1000);
            var h = Math.floor(secs / 3600);
            var m = Math.floor((secs % 3600) / 60);
            el.textContent = h + 'h ' + (m < 10 ? '0' : '') + m + 'm';
        });
    }
    setInterval(updateTimers, 1000);

    // ── Clock In button ──
    var btnClockIn = document.getElementById('btnClockIn');
    if (btnClockIn) {
        btnClockIn.addEventListener('click', function() {
            var techId = this.dataset.techId;
            var jobSelect = document.getElementById('clockInJobSelect');
            var jobId = jobSelect ? jobSelect.value : null;
            if (!jobId) { alert('Please select a job.'); return; }

            fetch('/time-tracking/api/clock-in', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({technician_id: parseInt(techId), job_id: parseInt(jobId)}),
            })
            .then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.success) window.location.reload();
                else alert(d.error || 'Clock in failed.');
            });
        });
    }

    // ── Clock Out buttons ──
    document.querySelectorAll('.btn-clock-out, #btnClockOut').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var techId = this.dataset.techId;
            document.getElementById('clockOutTechId').value = techId;
            var modal = new bootstrap.Modal(document.getElementById('clockOutModal'));
            modal.show();
        });
    });

    var confirmClockOut = document.getElementById('confirmClockOut');
    if (confirmClockOut) {
        confirmClockOut.addEventListener('click', function() {
            var techId = document.getElementById('clockOutTechId').value;
            var desc = document.getElementById('clockOutDescription').value;

            fetch('/time-tracking/api/clock-out', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({technician_id: parseInt(techId), description: desc}),
            })
            .then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.success) window.location.reload();
                else alert(d.error || 'Clock out failed.');
            });
        });
    }

    // ── Switch Job ──
    var confirmSwitch = document.getElementById('confirmSwitchJob');
    if (confirmSwitch) {
        confirmSwitch.addEventListener('click', function() {
            var techId = this.dataset.techId;
            var jobId = document.getElementById('switchJobSelect').value;
            var desc = document.getElementById('switchDescription').value;
            if (!jobId) { alert('Select a job.'); return; }

            fetch('/time-tracking/api/clock-out', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({technician_id: parseInt(techId), description: desc}),
            })
            .then(function(r) { return r.json(); })
            .then(function(d) {
                if (!d.success) { alert(d.error); return; }
                return fetch('/time-tracking/api/clock-in', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({technician_id: parseInt(techId), job_id: parseInt(jobId)}),
                });
            })
            .then(function(r) { return r ? r.json() : null; })
            .then(function(d) {
                if (d && d.success) window.location.reload();
                else if (d) alert(d.error || 'Switch failed.');
            });
        });
    }

    // ── Submit Week button ──
    var btnSubmitWeek = document.getElementById('btnSubmitWeek');
    if (btnSubmitWeek) {
        btnSubmitWeek.addEventListener('click', function() {
            var ids = this.dataset.ids.split(',').map(Number);
            fetch('/time-tracking/api/submit', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({entry_ids: ids}),
            })
            .then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.success) window.location.reload();
                else alert(d.error || 'Submit failed.');
            });
        });
    }

    // ── Bulk select/approve/reject (entries page) ──
    var selectAll = document.getElementById('selectAll');
    if (selectAll) {
        selectAll.addEventListener('change', function() {
            document.querySelectorAll('.entry-checkbox').forEach(function(cb) {
                cb.checked = selectAll.checked;
            });
            updateBulkActions();
        });
    }

    document.querySelectorAll('.entry-checkbox').forEach(function(cb) {
        cb.addEventListener('change', updateBulkActions);
    });

    function updateBulkActions() {
        var checked = document.querySelectorAll('.entry-checkbox:checked');
        var actions = document.getElementById('bulkActions');
        var countEl = document.getElementById('selectedCount');
        if (actions) {
            actions.classList.toggle('d-none', checked.length === 0);
            if (countEl) countEl.textContent = checked.length + ' selected';
        }
    }

    var bulkApprove = document.getElementById('bulkApprove');
    if (bulkApprove) {
        bulkApprove.addEventListener('click', function() {
            var ids = Array.from(document.querySelectorAll('.entry-checkbox:checked')).map(function(cb) { return parseInt(cb.value); });
            if (!ids.length) return;
            fetch('/time-tracking/api/approve', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({entry_ids: ids}),
            })
            .then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.success) window.location.reload();
                else alert(d.error);
            });
        });
    }

    var bulkReject = document.getElementById('bulkReject');
    if (bulkReject) {
        bulkReject.addEventListener('click', function() {
            var modal = new bootstrap.Modal(document.getElementById('rejectModal'));
            modal.show();
        });
    }

    var confirmReject = document.getElementById('confirmReject');
    if (confirmReject) {
        confirmReject.addEventListener('click', function() {
            var ids = Array.from(document.querySelectorAll('.entry-checkbox:checked')).map(function(cb) { return parseInt(cb.value); });
            var reason = document.getElementById('rejectReason').value;
            if (!reason) { alert('Reason required.'); return; }
            fetch('/time-tracking/api/reject', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({entry_ids: ids, reason: reason}),
            })
            .then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.success) window.location.reload();
                else alert(d.error);
            });
        });
    }
});
