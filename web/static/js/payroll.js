/* Payroll: expandable rows, inline status updates, confirm actions */
document.addEventListener('DOMContentLoaded', function() {

    // Expandable detail rows
    document.querySelectorAll('.payroll-row-toggle').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var techId = this.dataset.techId;
            var row = document.getElementById('detail-row-' + techId);
            if (!row) return;
            var visible = row.style.display !== 'none';
            row.style.display = visible ? 'none' : 'table-row';
            var icon = this.querySelector('.toggle-icon');
            if (icon) icon.textContent = visible ? '>' : 'v';
        });
    });

    // Inline status update
    document.querySelectorAll('.line-item-status-select').forEach(function(sel) {
        sel.dataset.originalStatus = sel.value;
        sel.addEventListener('change', function() {
            var itemId = this.dataset.itemId;
            var newStatus = this.value;
            var self = this;
            var formData = new FormData();
            formData.append('status', newStatus);
            fetch('/payroll/line-item/' + itemId + '/status', {
                method: 'POST', body: formData,
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            }).then(function(r) { return r.json(); }).then(function(data) {
                if (!data.success) {
                    alert('Failed to update status.');
                    self.value = self.dataset.originalStatus;
                }
            }).catch(function() {
                self.value = self.dataset.originalStatus;
            });
        });
    });

    // Confirm destructive actions
    document.querySelectorAll('[data-confirm]').forEach(function(el) {
        el.addEventListener('click', function(e) {
            if (!confirm(this.dataset.confirm)) e.preventDefault();
        });
    });
});
