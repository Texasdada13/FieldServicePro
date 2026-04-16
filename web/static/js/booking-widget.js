/* ================================================================
   booking-widget.js — Embed booking form on external websites
   Usage:
     <script src="https://your-domain.com/static/js/booking-widget.js"
             data-base-url="https://your-domain.com"></script>
     <button onclick="FSP.openBooking()">Request Service</button>
   ================================================================ */
(function() {
  'use strict';
  var scriptEl = document.currentScript;
  var BASE_URL = (scriptEl && scriptEl.getAttribute('data-base-url')) || window.FSP_BASE_URL || '';

  var style = document.createElement('style');
  style.textContent = [
    '#fsp-modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:99999;align-items:center;justify-content:center;padding:16px;}',
    '#fsp-modal-overlay.active{display:flex;}',
    '#fsp-modal-box{background:#fff;border-radius:12px;width:100%;max-width:700px;max-height:90vh;overflow:hidden;display:flex;flex-direction:column;box-shadow:0 24px 60px rgba(0,0,0,.3);}',
    '#fsp-modal-header{padding:12px 16px;display:flex;justify-content:flex-end;border-bottom:1px solid #e2e8f0;}',
    '#fsp-modal-close{background:none;border:none;font-size:1.5rem;cursor:pointer;color:#64748b;line-height:1;}',
    '#fsp-modal-iframe{flex:1;border:none;min-height:640px;}'
  ].join('');
  document.head.appendChild(style);

  var overlay = document.createElement('div');
  overlay.id = 'fsp-modal-overlay';
  overlay.innerHTML =
    '<div id="fsp-modal-box">' +
      '<div id="fsp-modal-header">' +
        '<button id="fsp-modal-close" onclick="FSP.closeBooking()" aria-label="Close">&times;</button>' +
      '</div>' +
      '<iframe id="fsp-modal-iframe" src="' + BASE_URL + '/book/embed" title="Request Service" allow="camera"></iframe>' +
    '</div>';
  overlay.addEventListener('click', function(e) { if (e.target === overlay) window.FSP.closeBooking(); });
  document.body.appendChild(overlay);

  window.FSP = {
    openBooking: function() {
      document.getElementById('fsp-modal-overlay').classList.add('active');
      document.body.style.overflow = 'hidden';
    },
    closeBooking: function() {
      document.getElementById('fsp-modal-overlay').classList.remove('active');
      document.body.style.overflow = '';
    }
  };
})();
