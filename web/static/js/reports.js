/* FieldServicePro Reports — shared JS */
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.preset-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var preset = this.dataset.preset;
            document.getElementById('presetInput').value = preset;
            document.querySelectorAll('.preset-btn').forEach(function(b) { b.classList.remove('btn-primary'); b.classList.add('btn-outline-secondary'); });
            this.classList.remove('btn-outline-secondary'); this.classList.add('btn-primary');
            var cr = document.getElementById('customDateRange');
            if (cr) cr.style.display = preset === 'custom' ? 'flex' : 'none';
            if (preset !== 'custom') document.getElementById('reportFilterForm').submit();
        });
    });
    initSortableTables();
});

function initSortableTables() {
    document.querySelectorAll('.report-table').forEach(function(table) {
        table.querySelectorAll('th[data-sort]').forEach(function(th) {
            th.addEventListener('click', function() { sortTable(table, th); });
        });
    });
}

function sortTable(table, th) {
    var col = th.cellIndex, rows = Array.from(table.querySelectorAll('tbody tr'));
    var isAsc = th.classList.contains('sorted-asc');
    table.querySelectorAll('th').forEach(function(h) { h.classList.remove('sorted-asc','sorted-desc'); });
    th.classList.add(isAsc ? 'sorted-desc' : 'sorted-asc');
    rows.sort(function(a, b) {
        var av = getCellValue(a, col), bv = getCellValue(b, col);
        if (!isNaN(av) && !isNaN(bv)) return isAsc ? bv - av : av - bv;
        return isAsc ? bv.toString().localeCompare(av.toString()) : av.toString().localeCompare(bv.toString());
    });
    var tbody = table.querySelector('tbody');
    rows.forEach(function(r) { tbody.appendChild(r); });
}

function getCellValue(row, col) {
    var cell = row.cells[col]; if (!cell) return '';
    return (cell.dataset.sortValue || cell.textContent.trim()).replace(/[$,%]/g, '').replace(/,/g, '');
}

function exportCSV() {
    var table = document.querySelector('.report-table');
    if (!table) { alert('No table found.'); return; }
    var rows = [];
    rows.push(Array.from(table.querySelectorAll('thead th')).map(function(th) { return '"' + th.textContent.trim().replace(/"/g,'""') + '"'; }).join(','));
    table.querySelectorAll('tbody tr').forEach(function(tr) {
        rows.push(Array.from(tr.querySelectorAll('td')).map(function(td) { return '"' + (td.dataset.exportValue || td.textContent).trim().replace(/"/g,'""') + '"'; }).join(','));
    });
    var blob = new Blob([rows.join('\n')], {type:'text/csv'});
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = (document.querySelector('h2')?.textContent.trim() || 'report').toLowerCase().replace(/\s+/g,'_') + '_' + new Date().toISOString().slice(0,10) + '.csv';
    a.click();
}

function requestAiInsights() {
    var panel = document.getElementById('aiInsightsPanel'), content = document.getElementById('aiInsightsContent');
    panel.style.display = 'block';
    content.innerHTML = '<div style="text-align:center;padding:var(--space-3);"><p>Analyzing data...</p></div>';
    var summaryData = {}; try { summaryData = JSON.parse(document.getElementById('reportSummaryData')?.textContent || '{}'); } catch(e) {}
    fetch('/reports/ai-insights', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({report_title: document.querySelector('h2')?.textContent.trim(), summary_data: summaryData}) })
        .then(function(r) { return r.json(); })
        .then(function(d) { content.innerHTML = d.insights ? '<div style="white-space:pre-line;">' + d.insights + '</div>' : '<p style="color:var(--color-danger);">Failed.</p>'; })
        .catch(function(e) { content.innerHTML = '<p style="color:var(--color-danger);">Error: ' + e.message + '</p>'; });
}

function closeAiPanel() { document.getElementById('aiInsightsPanel').style.display = 'none'; }

var REPORT_COLORS = { primary:'#0d6efd', success:'#198754', warning:'#ffc107', danger:'#dc3545', info:'#0dcaf0', secondary:'#6c757d' };
var COLOR_PALETTE = Object.values(REPORT_COLORS);
if (typeof Chart !== 'undefined') { Chart.defaults.font.family = "'Inter', system-ui, sans-serif"; Chart.defaults.font.size = 12; Chart.defaults.plugins.legend.position = 'bottom'; }
