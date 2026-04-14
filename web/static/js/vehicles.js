/* Vehicle management: navigation, fuel/mileage form helpers */

function openNavigation(address) {
    if (!address || !address.trim()) {
        alert('No address available for navigation.');
        return;
    }
    var encoded = encodeURIComponent(address.trim());
    var isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
    if (isMobile) {
        window.open('https://maps.google.com/maps?daddr=' + encoded, '_blank');
    } else {
        window.open('https://www.google.com/maps/dir/?api=1&destination=' + encoded, '_blank');
    }
}

function openNavigationFromCurrentLocation(destination) {
    if (!navigator.geolocation) { openNavigation(destination); return; }
    navigator.geolocation.getCurrentPosition(
        function(pos) {
            var origin = encodeURIComponent(pos.coords.latitude + ',' + pos.coords.longitude);
            var dest = encodeURIComponent(destination.trim());
            window.open('https://www.google.com/maps/dir/?api=1&origin=' + origin + '&destination=' + dest, '_blank');
        },
        function() { openNavigation(destination); }
    );
}

function openFullRoute(stops) {
    if (!stops || stops.length === 0) return;
    if (stops.length === 1) { openNavigation(stops[0]); return; }
    var origin = encodeURIComponent(stops[0]);
    var destination = encodeURIComponent(stops[stops.length - 1]);
    var url = 'https://www.google.com/maps/dir/?api=1&origin=' + origin + '&destination=' + destination;
    if (stops.length > 2) {
        var waypoints = stops.slice(1, -1).map(function(s) { return encodeURIComponent(s); }).join('|');
        url += '&waypoints=' + waypoints;
    }
    window.open(url, '_blank');
}

document.addEventListener('DOMContentLoaded', function() {
    // Fuel total cost calculator
    var gallonsInput = document.getElementById('gallons');
    var ppgInput = document.getElementById('price_per_gallon');
    var totalDisplay = document.getElementById('fuel_total_display');

    function updateFuelTotal() {
        if (!gallonsInput || !ppgInput || !totalDisplay) return;
        var g = parseFloat(gallonsInput.value) || 0;
        var p = parseFloat(ppgInput.value) || 0;
        totalDisplay.textContent = '$' + (g * p).toFixed(2);
    }
    if (gallonsInput) gallonsInput.addEventListener('input', updateFuelTotal);
    if (ppgInput) ppgInput.addEventListener('input', updateFuelTotal);

    // Mileage calculator
    var startOdo = document.getElementById('start_odometer');
    var endOdo = document.getElementById('end_odometer');
    var milesDisplay = document.getElementById('miles_driven_display');

    function updateMiles() {
        if (!startOdo || !endOdo || !milesDisplay) return;
        var s = parseInt(startOdo.value) || 0;
        var e = parseInt(endOdo.value) || 0;
        milesDisplay.textContent = Math.max(0, e - s).toLocaleString() + ' miles';
    }
    if (startOdo) startOdo.addEventListener('input', updateMiles);
    if (endOdo) endOdo.addEventListener('input', updateMiles);

    // Job selector auto-fills end location
    var jobSelect = document.getElementById('job_id');
    var endLocInput = document.getElementById('end_location');
    if (jobSelect) {
        jobSelect.addEventListener('change', function() {
            var jobId = this.value;
            if (!jobId || !endLocInput) return;
            fetch('/vehicles/api/job-address/' + jobId)
                .then(function(r) { return r.json(); })
                .then(function(data) { if (data.address) endLocInput.value = data.address; })
                .catch(function() {});
        });
    }
});
