/**
 * document_manager.js — Handles inline document upload widgets via AJAX.
 * Usage: Include on any page with a document upload zone.
 */
'use strict';

var DocumentManager = (function () {

  function initUploadZone(zoneId, options) {
    var zone = document.getElementById(zoneId);
    if (!zone) return;

    var fileInput = zone.querySelector('input[type="file"]');
    var listContainer = options.listContainer ? document.getElementById(options.listContainer) : null;
    var entityType = options.entityType || '';
    var entityId = options.entityId || '';
    var category = options.category || 'other';

    // Drag-and-drop
    zone.addEventListener('dragover', function (e) {
      e.preventDefault();
      zone.classList.add('dragover');
    });
    zone.addEventListener('dragleave', function () {
      zone.classList.remove('dragover');
    });
    zone.addEventListener('drop', function (e) {
      e.preventDefault();
      zone.classList.remove('dragover');
      if (e.dataTransfer.files.length) {
        uploadFile(e.dataTransfer.files[0]);
      }
    });

    // Click to select
    zone.addEventListener('click', function () {
      if (fileInput) fileInput.click();
    });
    if (fileInput) {
      fileInput.addEventListener('change', function () {
        if (this.files.length) uploadFile(this.files[0]);
      });
    }

    function uploadFile(file) {
      var formData = new FormData();
      formData.append('file', file);
      formData.append('category', category);
      formData.append('entity_type', entityType);
      formData.append('entity_id', entityId);
      formData.append('display_name', file.name);

      zone.innerHTML = '<div style="padding:var(--space-4);text-align:center;"><i class="bi bi-hourglass-split" style="font-size:1.5rem;color:var(--color-accent);"></i><div style="font-size:var(--font-size-sm);margin-top:var(--space-2);">Uploading...</div></div>';

      fetch('/documents/api/upload', {
        method: 'POST',
        body: formData,
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          zone.innerHTML = '<div style="padding:var(--space-4);text-align:center;"><i class="bi bi-check-circle" style="font-size:1.5rem;color:var(--color-success);"></i><div style="font-size:var(--font-size-sm);margin-top:var(--space-2);">Uploaded!</div></div>';
          if (listContainer) {
            appendDocumentRow(listContainer, data.document);
          }
          setTimeout(function () { resetZone(); }, 2000);
        } else {
          zone.innerHTML = '<div style="padding:var(--space-4);text-align:center;color:var(--color-danger);"><i class="bi bi-x-circle" style="font-size:1.5rem;"></i><div style="font-size:var(--font-size-sm);margin-top:var(--space-2);">' + (data.error || 'Upload failed') + '</div></div>';
          setTimeout(function () { resetZone(); }, 3000);
        }
      })
      .catch(function (err) {
        zone.innerHTML = '<div style="padding:var(--space-4);text-align:center;color:var(--color-danger);">Error: ' + err.message + '</div>';
        setTimeout(function () { resetZone(); }, 3000);
      });
    }

    function resetZone() {
      zone.innerHTML = '<div class="upload-dropzone__icon"><i class="bi bi-cloud-upload"></i></div>'
        + '<div style="font-size:var(--font-size-sm);color:var(--color-text-secondary);">Drop file here or click to upload</div>'
        + '<input type="file" style="display:none;" accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.doc,.docx,.xls,.xlsx,.csv,.txt">';
      var newInput = zone.querySelector('input[type="file"]');
      if (newInput) {
        newInput.addEventListener('change', function () {
          if (this.files.length) uploadFile(this.files[0]);
        });
      }
    }

    function appendDocumentRow(container, doc) {
      var html = '<div style="display:flex;align-items:center;gap:var(--space-2);padding:var(--space-2) var(--space-3);border-bottom:1px solid var(--color-border-light);">'
        + '<i class="bi ' + doc.icon_class + '" style="font-size:1.1rem;"></i>'
        + '<div style="flex:1;"><div style="font-size:var(--font-size-sm);font-weight:var(--font-weight-medium);">' + doc.display_name + '</div>'
        + '<div style="font-size:var(--font-size-xs);color:var(--color-text-muted);">' + doc.file_size_display + '</div></div>'
        + '<a href="/documents/' + doc.id + '/download" class="btn btn-sm btn-ghost"><i class="bi bi-download"></i></a></div>';
      container.insertAdjacentHTML('afterbegin', html);
    }
  }

  return { initUploadZone: initUploadZone };
})();
