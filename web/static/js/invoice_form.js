/**
 * invoice_form.js
 *
 * Handles the commercial fields section of the invoice create/edit form:
 *   - Shows/hides commercial fields based on selected client type
 *   - Loads POs for the selected client via AJAX
 *   - Displays PO balance panel and live capacity warnings
 *   - Auto-populates payment terms from client defaults
 *   - Calculates due date from invoice date + terms
 */
'use strict';

var InvoiceForm = (function () {

  var TERMS_DAYS = {
    due_on_receipt: 0,
    net_15: 15,
    net_30: 30,
    net_45: 45,
    net_60: 60,
    net_90: 90,
    custom: null,
  };

  var clientData = null;
  var poData = null;

  function init() {
    var clientSel = document.getElementById('client_id');
    var poSel = document.getElementById('po_id');
    var termsSel = document.getElementById('payment_terms');
    var invoiceDateIn = document.getElementById('invoice_date');
    var customDaysIn = document.getElementById('custom_payment_days');

    if (clientSel) clientSel.addEventListener('change', onClientChange);
    if (poSel) poSel.addEventListener('change', onPOChange);
    if (termsSel) termsSel.addEventListener('change', onTermsChange);
    if (invoiceDateIn) invoiceDateIn.addEventListener('change', recalcDueDate);
    if (customDaysIn) customDaysIn.addEventListener('input', debounce(recalcDueDate, 300));

    document.addEventListener('lineItemsChanged', debounce(onTotalChanged, 600));

    // Trigger client load on page load (editing existing invoice)
    if (clientSel && clientSel.value) {
      clientSel.dispatchEvent(new Event('change'));
    }
  }

  // -- Client Change --

  function onClientChange() {
    var clientId = this.value;
    var wrap = document.getElementById('commercial-fields');

    if (!clientId) {
      if (wrap) wrap.style.display = 'none';
      clientData = null;
      return;
    }

    fetch('/api/client/' + clientId + '/billing-defaults')
      .then(function (res) {
        if (!res.ok) throw new Error('Client billing fetch failed');
        return res.json();
      })
      .then(function (data) {
        clientData = data;
        var isCommercial = data.is_commercial;
        if (wrap) wrap.style.display = isCommercial ? '' : 'none';

        if (isCommercial) {
          loadPOs(clientId);
          applyClientDefaults();
        }
      })
      .catch(function (e) {
        console.error(e);
      });
  }

  // -- PO Selector --

  function loadPOs(clientId) {
    var poSel = document.getElementById('po_id');
    if (!poSel) return;

    var currentPO = poSel.dataset.currentPo || '';
    var qs = currentPO ? 'include_all=true' : '';

    fetch('/purchase-orders/api/purchase-orders/client/' + clientId + '?' + qs)
      .then(function (res) { return res.json(); })
      .then(function (pos) {
        poSel.innerHTML = '<option value="">-- No PO (manual entry) --</option>';

        pos.forEach(function (po) {
          var opt = document.createElement('option');
          opt.value = po.id;
          opt.dataset.po = JSON.stringify(po);

          var expiry = po.expiry_date ? ' · Exp ' + po.expiry_date : '';
          var badge = po.status !== 'active' ? ' [' + po.status.toUpperCase() + ']' : '';
          opt.textContent = po.po_number + ' -- $' + po.amount_remaining.toFixed(2) + ' remaining' + expiry + badge;
          opt.disabled = !po.is_available && String(po.id) !== currentPO;
          if (String(po.id) === currentPO) opt.selected = true;

          poSel.appendChild(opt);
        });

        // require-PO warning
        var warn = document.getElementById('po-require-warning');
        if (warn) {
          warn.style.display = (clientData && clientData.require_po) ? '' : 'none';
        }

        if (poSel.value) poSel.dispatchEvent(new Event('change'));
      })
      .catch(function (e) {
        console.error('PO load error:', e);
      });
  }

  function onPOChange() {
    var opt = this.options[this.selectedIndex];
    var panel = document.getElementById('po-balance-panel');
    clearPOAlerts();

    if (!this.value) {
      poData = null;
      if (panel) panel.style.display = 'none';
      return;
    }

    try { poData = JSON.parse(opt.dataset.po); } catch (e) { return; }

    renderBalancePanel(poData);
    if (panel) panel.style.display = '';

    // Auto-fill cost_code / department if blank
    if (poData.cost_code) {
      var el = document.getElementById('cost_code');
      if (el && !el.value) el.value = poData.cost_code;
    }
    if (poData.department) {
      var el2 = document.getElementById('department');
      if (el2 && !el2.value) el2.value = poData.department;
    }

    checkCapacity();
  }

  function renderBalancePanel(po) {
    var pct = Math.min(100, po.utilization_pct || 0);
    var bar = document.getElementById('po-progress');

    setText('po-authorized', '$' + po.amount_authorized.toFixed(2));
    setText('po-used', '$' + po.amount_used.toFixed(2));
    setText('po-remaining', '$' + po.amount_remaining.toFixed(2));

    if (bar) {
      bar.style.width = pct + '%';
      bar.style.background = pct >= 90 ? 'var(--color-danger)' : pct >= 70 ? 'var(--color-warning)' : 'var(--color-success)';
    }
  }

  function checkCapacity() {
    var poSel = document.getElementById('po_id');
    if (!poSel || !poSel.value) return;

    var total = getInvoiceTotal();
    if (!total) return;

    var excludeId = null;
    var invoiceIdEl = document.getElementById('invoice_id');
    if (invoiceIdEl) excludeId = invoiceIdEl.value || null;

    fetch('/purchase-orders/api/purchase-orders/' + poSel.value + '/capacity', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount: total, exclude_invoice_id: excludeId }),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        showPOAlerts(data.warnings || [], data.errors || []);
      })
      .catch(function (e) {
        console.error('Capacity check error:', e);
      });
  }

  function showPOAlerts(warnings, errors) {
    var warn = document.getElementById('po-balance-warning');
    var err = document.getElementById('po-error-msg');

    if (warn) {
      warn.style.display = warnings.length ? '' : 'none';
      warn.innerHTML = warnings.map(function (w) {
        return '<i class="bi bi-exclamation-triangle-fill" style="margin-right:4px;"></i>' + w;
      }).join('<br>');
    }
    if (err) {
      err.style.display = errors.length ? '' : 'none';
      err.innerHTML = errors.map(function (e) {
        return '<i class="bi bi-x-circle-fill" style="margin-right:4px;"></i>' + e;
      }).join('<br>');
    }
  }

  function clearPOAlerts() {
    ['po-balance-warning', 'po-error-msg'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
  }

  // -- Payment Terms --

  function applyClientDefaults() {
    var termsSel = document.getElementById('payment_terms');
    if (!termsSel || termsSel.dataset.userModified) return;

    if (clientData && clientData.payment_terms) {
      termsSel.value = clientData.payment_terms;
      termsSel.dispatchEvent(new Event('change'));
    }

    var bcEl = document.getElementById('billing_contact');
    if (bcEl && !bcEl.value && clientData && clientData.billing_contact_name) {
      bcEl.value = clientData.billing_contact_name;
    }
  }

  function onTermsChange() {
    this.dataset.userModified = '1';
    var customWrap = document.getElementById('custom-days-wrapper');
    if (customWrap) {
      customWrap.style.display = this.value === 'custom' ? '' : 'none';
    }
    recalcDueDate();
  }

  function recalcDueDate() {
    var termsSel = document.getElementById('payment_terms');
    var invoiceDateIn = document.getElementById('invoice_date');
    var dueDateIn = document.getElementById('due_date');
    var customDaysIn = document.getElementById('custom_payment_days');

    if (!termsSel || !invoiceDateIn || !dueDateIn || !invoiceDateIn.value) return;

    var invoiceDate = new Date(invoiceDateIn.value + 'T00:00:00');
    var days = TERMS_DAYS[termsSel.value];
    if (days === null) days = parseInt(customDaysIn ? customDaysIn.value : '0') || 0;

    var due = new Date(invoiceDate);
    due.setDate(due.getDate() + days);
    dueDateIn.value = due.toISOString().split('T')[0];
  }

  // -- Helpers --

  function getInvoiceTotal() {
    var candidates = ['invoice-grand-total', 'total_amount', 'invoice_total'];
    for (var i = 0; i < candidates.length; i++) {
      var el = document.getElementById(candidates[i]);
      if (!el) continue;
      var raw = el.value || el.textContent;
      var val = parseFloat(String(raw).replace(/[^0-9.]/g, ''));
      if (!isNaN(val)) return val;
    }
    return 0;
  }

  function onTotalChanged() {
    if (poData) {
      renderBalancePanel(poData);
      checkCapacity();
    }
  }

  function setText(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function debounce(fn, ms) {
    var t;
    return function () {
      var args = arguments;
      var ctx = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }

  return { init: init };
})();

document.addEventListener('DOMContentLoaded', InvoiceForm.init);
