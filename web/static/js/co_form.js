/**
 * co_form.js — Change order form: line item management, live cost calculations.
 */
'use strict';

(function () {
  function fmt(n) { return '$' + parseFloat(n || 0).toFixed(2); }

  function recalculate() {
    var additions = 0, deductions = 0;

    document.querySelectorAll('#lineItemsBody .line-item-row').forEach(function (row, idx) {
      var qty = parseFloat(row.querySelector('.qty-input') ? row.querySelector('.qty-input').value : 1) || 0;
      var price = parseFloat(row.querySelector('.price-input') ? row.querySelector('.price-input').value : 0) || 0;
      var toggle = row.querySelector('.addition-toggle');
      var isAddition = toggle ? toggle.checked : true;
      var total = qty * price;

      var totalCell = row.querySelector('.line-total');
      if (totalCell) {
        totalCell.textContent = (isAddition ? '+' : '-') + fmt(total);
        totalCell.style.color = isAddition ? 'var(--color-success)' : 'var(--color-danger)';
      }
      if (toggle) toggle.value = String(idx);

      if (isAddition) additions += total;
      else deductions += total;
    });

    var net = additions - deductions;
    setText('additionsTotal', fmt(additions));
    setText('deductionsTotal', '-' + fmt(deductions));
    var netEl = document.getElementById('netChange');
    if (netEl) {
      netEl.textContent = (net >= 0 ? '+' : '') + fmt(net);
      netEl.style.color = net >= 0 ? 'var(--color-success)' : 'var(--color-danger)';
    }

    setText('sideAdditions', fmt(additions));
    setText('sideDeductions', '-' + fmt(deductions));
    var sideNet = document.getElementById('sideNetChange');
    if (sideNet) {
      sideNet.textContent = (net >= 0 ? '+' : '') + fmt(net);
      sideNet.style.color = net >= 0 ? 'var(--color-success)' : 'var(--color-danger)';
    }

    var sideNew = document.getElementById('sideNewTotal');
    if (sideNew && typeof JOB_CURRENT_TOTAL !== 'undefined') {
      sideNew.textContent = fmt(JOB_CURRENT_TOTAL + net);
    }

    // Auto-fill revised amount
    var revisedInput = document.getElementById('revisedAmount');
    if (revisedInput && !revisedInput.dataset.manuallySet) {
      var origInput = document.querySelector('[name="original_amount"]');
      var original = parseFloat(origInput ? origInput.value : 0) || 0;
      revisedInput.value = (original + net).toFixed(2);
    }
  }

  function addRow() {
    var tbody = document.getElementById('lineItemsBody');
    var idx = tbody.querySelectorAll('.line-item-row').length;
    var tr = document.createElement('tr');
    tr.className = 'line-item-row';
    tr.innerHTML = '<td><input type="text" name="li_description[]" class="form-control" placeholder="Describe work or material..." required></td>'
      + '<td><input type="number" name="li_qty[]" class="form-control qty-input" value="1" step="0.01" min="0.01" style="text-align:right;"></td>'
      + '<td><input type="number" name="li_unit_price[]" class="form-control price-input" value="0" step="0.01" min="0" style="text-align:right;"></td>'
      + '<td style="text-align:right;font-weight:var(--font-weight-semibold);color:var(--color-success);" class="line-total">+$0.00</td>'
      + '<td style="text-align:center;"><input type="checkbox" class="addition-toggle" name="li_is_addition[]" value="' + idx + '" checked style="accent-color:var(--color-accent);"></td>'
      + '<td><button type="button" class="btn btn-sm btn-ghost remove-line-item" style="color:var(--color-danger);"><i class="bi bi-x-lg"></i></button></td>';
    tbody.appendChild(tr);
    bindRow(tr);
    tr.querySelector('input').focus();
  }

  function bindRow(row) {
    var qtyIn = row.querySelector('.qty-input');
    var priceIn = row.querySelector('.price-input');
    var toggle = row.querySelector('.addition-toggle');
    var rmBtn = row.querySelector('.remove-line-item');
    if (qtyIn) qtyIn.addEventListener('input', recalculate);
    if (priceIn) priceIn.addEventListener('input', recalculate);
    if (toggle) toggle.addEventListener('change', recalculate);
    if (rmBtn) rmBtn.addEventListener('click', function () { row.remove(); recalculate(); });
  }

  function setText(id, text) { var el = document.getElementById(id); if (el) el.textContent = text; }

  function init() {
    document.querySelectorAll('#lineItemsBody .line-item-row').forEach(bindRow);
    var addBtn = document.getElementById('addLineItemBtn');
    if (addBtn) addBtn.addEventListener('click', addRow);

    var revisedInput = document.getElementById('revisedAmount');
    if (revisedInput) revisedInput.addEventListener('input', function () { this.dataset.manuallySet = 'true'; });

    recalculate();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
