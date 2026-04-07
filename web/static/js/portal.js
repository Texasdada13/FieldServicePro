/**
 * FieldServicePro Client Portal — Frontend JS
 */

document.addEventListener('DOMContentLoaded', function() {

    // ── Clickable Table Rows ──────────────────────────────────────
    document.querySelectorAll('.clickable-row').forEach(function(row) {
        row.addEventListener('click', function(e) {
            if (e.target.closest('a, button, .btn, .dropdown')) return;
            var href = this.dataset.href;
            if (href) window.location.href = href;
        });
    });

    // ── Auto-dismiss alerts ───────────────────────────────────────
    document.querySelectorAll('.alert-dismissible').forEach(function(alert) {
        setTimeout(function() {
            var bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 5000);
    });

    // ── Confirm dialogs ──────────────────────────────────────────
    document.querySelectorAll('[data-confirm]').forEach(function(el) {
        el.addEventListener('click', function(e) {
            if (!confirm(this.dataset.confirm)) {
                e.preventDefault();
            }
        });
    });

    // ── File upload preview ──────────────────────────────────────
    document.querySelectorAll('.portal-file-input').forEach(function(input) {
        input.addEventListener('change', function() {
            var fileList = this.closest('.portal-file-upload').querySelector('.portal-file-list');
            if (!fileList) return;
            fileList.innerHTML = '';
            Array.from(this.files).forEach(function(file) {
                var item = document.createElement('div');
                item.className = 'portal-file-item small text-muted';
                item.innerHTML = '<i class="bi bi-paperclip"></i> ' +
                    file.name + ' (' + formatFileSize(file.size) + ')';
                fileList.appendChild(item);
            });
        });
    });

    // ── Format currency helper ────────────────────────────────────
    document.querySelectorAll('[data-currency]').forEach(function(el) {
        var val = parseFloat(el.textContent);
        if (!isNaN(val)) {
            el.textContent = '$' + val.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        }
    });

    // ── Session timeout warning ──────────────────────────────────
    var sessionTimeout = parseInt(document.body.dataset.sessionTimeout || '30');
    var warningMinutes = 2;
    if (sessionTimeout > warningMinutes) {
        setTimeout(function() {
            if (confirm('Your session will expire in ' + warningMinutes +
                ' minutes. Would you like to stay logged in?')) {
                fetch('/portal/ping', { method: 'POST', credentials: 'same-origin' })
                    .catch(function() {});
            }
        }, (sessionTimeout - warningMinutes) * 60 * 1000);
    }
});

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    var k = 1024;
    var sizes = ['B', 'KB', 'MB', 'GB'];
    var i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
