/* ================================================================
   booking.js — Multi-step booking wizard logic
   ================================================================ */
'use strict';

var state = {
  currentStep: 1, totalSteps: 6,
  serviceType: null, urgency: 'routine',
  selectedDates: [], timeSlot: 'anytime',
  photoFiles: [],
  maxPhotos: (window.BOOKING_CONFIG || {}).maxPhotos || 5,
  availableDays: (window.BOOKING_CONFIG || {}).availableDays || 14,
};

var STEP_LABELS = [
  '', 'Step 1 of 6 — Choose a Service', 'Step 2 of 6 — Describe the Issue',
  'Step 3 of 6 — Service Location', 'Step 4 of 6 — Scheduling Preference',
  'Step 5 of 6 — Your Information', 'Step 6 of 6 — Review & Submit'
];

var QUICK_ISSUES = {
  plumbing: ['Leaking pipe','Clogged drain','No hot water','Water heater issue','Toilet problem','Faucet repair','Other'],
  hvac: ['No heating','No cooling','Strange noise','Thermostat issue','Filter change','Annual tune-up','Other'],
  electrical: ['Power outage','Breaker tripping','Outlet not working','Light fixture','Panel upgrade','Other'],
  general: ['Drywall repair','Door / Window','Flooring','Painting','Other'],
};

// ── Navigation ──
function goToStep(n) {
  document.querySelectorAll('.booking-step').forEach(function(el) { el.classList.add('d-none'); });
  var target = document.getElementById('step-' + n);
  if (target) target.classList.remove('d-none');
  state.currentStep = n;
  var pct = (n / state.totalSteps) * 100;
  document.getElementById('progress-bar').style.width = pct + '%';
  document.getElementById('step-label').textContent = STEP_LABELS[n];
  window.scrollTo({ top: 0, behavior: 'smooth' });
  if (n === 4) initCalendar();
  if (n === 6) populateReview();
}

// ── Step 1 ──
function selectService(btn) {
  document.querySelectorAll('.service-type-btn').forEach(function(b) { b.classList.remove('selected'); });
  btn.classList.add('selected');
  state.serviceType = btn.dataset.service;
  document.getElementById('service_type_input').value = state.serviceType;
  document.getElementById('step1-next').disabled = false;
  populateQuickTags(state.serviceType);
}

// ── Step 2 ──
function populateQuickTags(service) {
  var container = document.getElementById('quick-tags-container');
  container.innerHTML = '';
  (QUICK_ISSUES[service] || []).forEach(function(issue) {
    var btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'quick-tag'; btn.textContent = issue;
    btn.onclick = function() { selectQuickTag(btn, issue); };
    container.appendChild(btn);
  });
}

function selectQuickTag(btn, issue) {
  document.querySelectorAll('.quick-tag').forEach(function(t) { t.classList.remove('selected'); });
  btn.classList.add('selected');
  var ta = document.getElementById('description');
  if (issue === 'Other') { ta.value = ''; ta.focus(); } else { ta.value = issue; }
}

function selectUrgency(btn) {
  document.querySelectorAll('.urgency-btn').forEach(function(b) { b.classList.remove('selected'); });
  btn.classList.add('selected');
  state.urgency = btn.dataset.value;
  document.getElementById('urgency_input').value = state.urgency;
}

function validateStep2() {
  var desc = document.getElementById('description').value.trim();
  if (!desc) { showFieldError('description', 'Please describe your issue.'); return; }
  goToStep(3);
}

// ── Step 3 ──
function validateStep3() {
  var required = ['street_address', 'city', 'state_province', 'postal_code'];
  var valid = true;
  required.forEach(function(id) {
    var el = document.getElementById(id);
    if (el && !el.value.trim()) { showFieldError(id, 'This field is required.'); valid = false; }
  });
  if (valid) goToStep(4);
}

// ── Step 4 ──
var calInitialized = false;
function initCalendar() {
  var container = document.getElementById('booking-calendar');
  if (!container || calInitialized) return;
  calInitialized = true;
  var today = new Date();
  var viewYear = today.getFullYear(), viewMonth = today.getMonth();

  function render() {
    var maxDate = new Date(today); maxDate.setDate(today.getDate() + state.availableDays);
    var firstDay = new Date(viewYear, viewMonth, 1).getDay();
    var daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
    var monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    var dayAbbr = ['Su','Mo','Tu','We','Th','Fr','Sa'];
    var html = '<div class="cal-header"><button type="button" onclick="calNav(-1)" style="background:none;border:none;color:#fff;font-size:1.2rem">&lsaquo;</button><strong>' + monthNames[viewMonth] + ' ' + viewYear + '</strong><button type="button" onclick="calNav(1)" style="background:none;border:none;color:#fff;font-size:1.2rem">&rsaquo;</button></div><div class="cal-grid">';
    dayAbbr.forEach(function(d) { html += '<div class="cal-day-header">' + d + '</div>'; });
    for (var i = 0; i < firstDay; i++) html += '<div class="cal-day disabled"></div>';
    for (var d = 1; d <= daysInMonth; d++) {
      var cellDate = new Date(viewYear, viewMonth, d);
      var dateStr = cellDate.toISOString().split('T')[0];
      var isPast = cellDate < today && cellDate.toDateString() !== today.toDateString();
      var isToday = cellDate.toDateString() === today.toDateString();
      var isFuture = cellDate > maxDate;
      var isSelected = state.selectedDates.indexOf(dateStr) !== -1;
      var cls = 'cal-day';
      if (isPast || isFuture) cls += ' disabled';
      if (isToday) cls += ' today';
      if (isSelected) cls += ' selected';
      html += '<div class="' + cls + '" data-date="' + dateStr + '" onclick="toggleDate(\'' + dateStr + '\',this)">' + d + '</div>';
    }
    html += '</div>';
    container.innerHTML = html;
  }
  window.calNav = function(dir) {
    viewMonth += dir;
    if (viewMonth < 0) { viewMonth = 11; viewYear--; }
    if (viewMonth > 11) { viewMonth = 0; viewYear++; }
    render();
  };
  render();
}

function toggleDate(dateStr, el) {
  var idx = state.selectedDates.indexOf(dateStr);
  if (idx === -1) { state.selectedDates.push(dateStr); el.classList.add('selected'); }
  else { state.selectedDates.splice(idx, 1); el.classList.remove('selected'); }
  document.getElementById('preferred_dates_input').value = JSON.stringify(state.selectedDates);
}

function selectTimeSlot(btn) {
  document.querySelectorAll('.time-slot-btn').forEach(function(b) { b.classList.remove('selected'); });
  btn.classList.add('selected');
  state.timeSlot = btn.dataset.value;
  document.getElementById('time_slot_input').value = state.timeSlot;
}

// ── Step 5 ──
function toggleExistingCustomer(cb) {
  document.getElementById('existing-customer-field').classList.toggle('d-none', !cb.checked);
}

function validateStep5() {
  var fields = [
    { id: 'first_name', label: 'First name' }, { id: 'last_name', label: 'Last name' },
    { id: 'phone', label: 'Phone' }, { id: 'email', label: 'Email' },
  ];
  var valid = true;
  fields.forEach(function(f) {
    var el = document.getElementById(f.id);
    if (el && !el.value.trim()) { showFieldError(f.id, f.label + ' is required.'); valid = false; }
  });
  var email = document.getElementById('email');
  if (email && email.value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) {
    showFieldError('email', 'Please enter a valid email.'); valid = false;
  }
  if (valid) goToStep(6);
}

// ── Step 6 ──
function populateReview() {
  var v = function(id) { return (document.getElementById(id) || {}).value || '\u2014'; };
  var svcLabels = { plumbing: '\ud83d\udd27 Plumbing', hvac: '\u2744\ufe0f HVAC', electrical: '\u26a1 Electrical', general: '\ud83c\udfe0 General' };
  var urgLabels = { emergency: '\ud83d\udea8 Emergency', urgent: '\u26a1 Urgent', routine: '\ud83d\udcc5 Routine', flexible: '\ud83c\udf3f Flexible' };
  var slotLabels = { morning: 'Morning (8am\u201312pm)', afternoon: 'Afternoon (12pm\u20135pm)', anytime: 'Anytime' };
  setText('review-service', svcLabels[state.serviceType] || '\u2014');
  setText('review-description', v('description'));
  setText('review-urgency', urgLabels[state.urgency] || '\u2014');
  var addr = [v('street_address'), v('unit_apt'), v('city'), v('state_province'), v('postal_code')].filter(function(s) { return s && s !== '\u2014'; }).join(', ');
  setText('review-location', addr || '\u2014');
  setText('review-dates', state.selectedDates.length ? state.selectedDates.join(', ') : 'No preference');
  setText('review-timeslot', slotLabels[state.timeSlot] || '\u2014');
  var name = [v('first_name'), v('last_name')].join(' ').trim();
  setText('review-contact', name + ' \u00b7 ' + v('phone') + ' \u00b7 ' + v('email'));
}

// ── Photo Upload ──
function handlePhotoUpload(input) {
  var zone = document.getElementById('photo-upload-zone');
  var preview = document.getElementById('photo-previews');
  var newFiles = Array.from(input.files);
  if (state.photoFiles.length + newFiles.length > state.maxPhotos) {
    alert('Maximum ' + state.maxPhotos + ' photos allowed.'); input.value = ''; return;
  }
  newFiles.forEach(function(file) {
    if (!file.type.startsWith('image/')) return;
    if (file.size > 10 * 1024 * 1024) { alert(file.name + ' is too large (max 10MB).'); return; }
    state.photoFiles.push(file);
    var thumb = document.createElement('div'); thumb.className = 'photo-thumb';
    var img = document.createElement('img'); img.src = URL.createObjectURL(file);
    var rm = document.createElement('button'); rm.className = 'remove-photo'; rm.type = 'button'; rm.innerHTML = '\u00d7';
    rm.onclick = function() { var idx = state.photoFiles.indexOf(file); if (idx > -1) state.photoFiles.splice(idx, 1); thumb.remove(); if (!state.photoFiles.length) zone.classList.remove('has-files'); };
    thumb.appendChild(img); thumb.appendChild(rm); preview.appendChild(thumb);
  });
  if (state.photoFiles.length > 0) zone.classList.add('has-files');
  input.value = '';
}

// ── Form Submit ──
document.addEventListener('DOMContentLoaded', function() {
  var form = document.getElementById('booking-form');
  if (!form) return;
  form.addEventListener('submit', function(e) {
    var terms = document.getElementById('terms_check');
    if (!terms || !terms.checked) { e.preventDefault(); alert('Please agree to the Terms of Service.'); return; }
    var btn = document.getElementById('submit-btn');
    if (btn) btn.disabled = true;
    var spinner = document.getElementById('submit-spinner');
    if (spinner) spinner.classList.remove('d-none');
  });
});

// ── Utilities ──
function setText(id, val) { var el = document.getElementById(id); if (el) el.textContent = val; }
function showFieldError(fieldId, message) {
  var el = document.getElementById(fieldId);
  if (!el) return;
  el.classList.add('is-invalid');
  var fb = el.nextElementSibling;
  if (!fb || !fb.classList.contains('invalid-feedback')) {
    fb = document.createElement('div'); fb.className = 'invalid-feedback';
    el.parentNode.insertBefore(fb, el.nextSibling);
  }
  fb.textContent = message; fb.style.display = 'block'; el.focus();
  el.addEventListener('input', function() { el.classList.remove('is-invalid'); }, { once: true });
}
