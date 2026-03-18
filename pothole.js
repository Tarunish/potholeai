// ============================
// POTHOLE NAVIGATION SYSTEM
// ============================

var potholes = [];
fetch("pothole.json")
    .then(function (r) { return r.json(); })
    .then(function (d) { potholes = d; console.log("Loaded", d.length, "potholes"); })
    .catch(function (e) { console.error("pothole.json error:", e); });

// --- Map ---
var map = L.map('map').setView([20.5937, 78.9629], 5);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '© OpenStreetMap contributors'
}).addTo(map);

// --- State ---
var startLatLng = null, endLatLng = null;
var routeCoordinates = [], routeAlternatives = [];
var origRouteCoords = [];   // original (red) route coords — car uses these on "Continue"
var routingControl = null;
var driver = null, currentStep = 0;
var isPaused = false;
var moveTimeout = null;
var ignoredPotholes = new Set();
var revealedPotholes = new Set();
var warnedPotholes = new Set();
var shownPotholeLayers = {};
var origRouteLine = null, safeRouteLine = null;

// --- UI ---
var navPanel = document.getElementById("navPanel");
var toggleNav = document.getElementById("toggleNav");
var startInput = document.getElementById("startInput");
var endInput = document.getElementById("endInput");
var startSugg = document.getElementById("startSugg");
var endSugg = document.getElementById("endSugg");
var journeyBtn = document.getElementById("startJourneyBtn");
var statusBar = document.getElementById("statusBar");

// Popup elements
var potholeCard = document.getElementById("potholeCard");
var modalBadge = document.getElementById("modalBadge");
var modalTitle = document.getElementById("modalTitle");
var modalMsg = document.getElementById("modalMsg");
var modalBtns = document.getElementById("modalBtns");

function showStatus(m) { statusBar.textContent = m; statusBar.style.display = "block"; }
function hideStatus() { statusBar.style.display = "none"; }

// =======================
// CUSTOM POPUP MODAL
// =======================
function showModal(risk, distanceM, hasAlt, onReroute, onContinue) {
    var colors = {
        CRITICAL: { bg: "#b71c1c", text: "#ff6b6b" },
        MEDIUM: { bg: "#e65100", text: "#ffb74d" },
        LOW: { bg: "#1b5e20", text: "#66bb6a" }
    };
    var c = colors[risk] || colors.LOW;
    var emoji = risk === "CRITICAL" ? "🔴" : risk === "MEDIUM" ? "🟡" : "🟢";

    // Format distance nicely
    var distLabel = distanceM >= 1000
        ? (distanceM / 1000).toFixed(1) + " km ahead"
        : Math.round(distanceM) + " m ahead";

    modalBadge.textContent = emoji + " " + risk + " RISK  ·  " + distLabel;
    modalBadge.style.background = c.bg;
    modalBadge.style.color = c.text;
    modalTitle.textContent = "⚠ Pothole Detected Ahead!";
    modalBtns.innerHTML = "";

    if (risk === "CRITICAL") {
        modalMsg.textContent = hasAlt
            ? "🔴 A CRITICAL pothole is " + distLabel + " on your route. Choose to reroute to a safer path or continue with extreme caution."
            : "🔴 A CRITICAL pothole is " + distLabel + ". No alternative route is available. Proceed with extreme caution.";
        if (hasAlt) {
            var r = document.createElement("button");
            r.className = "modal-btn btn-reroute";
            r.textContent = "🔄 Reroute (Recommended)";
            r.onclick = function () { closeModal(); onReroute(); };
            modalBtns.appendChild(r);
        }
        var cont = document.createElement("button");
        cont.className = "modal-btn btn-continue";
        cont.textContent = hasAlt ? "➡ Continue Anyway" : "⚠ Proceed with Caution";
        cont.onclick = function () { closeModal(); onContinue(); };
        modalBtns.appendChild(cont);

    } else if (risk === "MEDIUM") {
        modalMsg.textContent = hasAlt
            ? "🟡 A MEDIUM risk pothole is " + distLabel + ". An alternative route is available."
            : "🟡 A MEDIUM risk pothole is " + distLabel + ". No alternative route found.";
        if (hasAlt) {
            var r2 = document.createElement("button"); r2.className = "modal-btn btn-reroute"; r2.textContent = "🔄 Reroute"; r2.onclick = function () { closeModal(); onReroute(); }; modalBtns.appendChild(r2);
        }
        var c2 = document.createElement("button"); c2.className = "modal-btn btn-continue"; c2.textContent = "➡ Continue"; c2.onclick = function () { closeModal(); onContinue(); }; modalBtns.appendChild(c2);

    } else { // LOW
        modalMsg.textContent = "🟢 A LOW risk pothole is " + distLabel + ". Continuing automatically in 3s.";
        var ok = document.createElement("button"); ok.className = "modal-btn btn-continue"; ok.textContent = "👍 OK, Continue"; ok.onclick = function () { closeModal(); onContinue(); }; modalBtns.appendChild(ok);
        setTimeout(function () { if (potholeCard.style.display !== "none") { closeModal(); onContinue(); } }, 3000);
    }

    potholeCard.style.display = "block";
}

function closeModal() {
    potholeCard.style.display = "none";
}

// =======================
// GEOCODING
// =======================
var debounce = null;
function geocode(q, cb) {
    fetch("https://nominatim.openstreetmap.org/search?format=json&limit=5&q=" + encodeURIComponent(q))
        .then(function (r) { return r.json(); }).then(cb).catch(function () { cb([]); });
}

function setupAutocomplete(input, box, onPick) {
    input.addEventListener("input", function () {
        clearTimeout(debounce);
        var q = input.value.trim();
        if (q.length < 3) { box.style.display = "none"; return; }
        debounce = setTimeout(function () {
            geocode(q, function (results) {
                box.innerHTML = "";
                if (!results.length) { box.style.display = "none"; return; }
                results.slice(0, 5).forEach(function (r) {
                    var d = document.createElement("div");
                    d.textContent = r.display_name;
                    d.addEventListener("mousedown", function (e) {
                        e.preventDefault();
                        input.value = r.display_name;
                        box.style.display = "none";
                        onPick({ lat: parseFloat(r.lat), lng: parseFloat(r.lon) });
                    });
                    box.appendChild(d);
                });
                box.style.display = "block";
            });
        }, 400);
    });
    input.addEventListener("blur", function () { setTimeout(function () { box.style.display = "none"; }, 200); });
}

setupAutocomplete(startInput, startSugg, function (ll) { startLatLng = ll; });
setupAutocomplete(endInput, endSugg, function (ll) { endLatLng = ll; });

// =======================
// START JOURNEY
// =======================
journeyBtn.addEventListener("click", function () {
    var st = startInput.value.trim(), en = endInput.value.trim();
    if (!st || !en) { alert("Enter both start and destination!"); return; }

    journeyBtn.disabled = true;
    showStatus("🔍 Looking up locations...");

    var gs = startLatLng ? Promise.resolve([{ lat: startLatLng.lat, lon: startLatLng.lng }])
        : fetch("https://nominatim.openstreetmap.org/search?format=json&limit=1&q=" + encodeURIComponent(st)).then(function (r) { return r.json(); });
    var ge = endLatLng ? Promise.resolve([{ lat: endLatLng.lat, lon: endLatLng.lng }])
        : fetch("https://nominatim.openstreetmap.org/search?format=json&limit=1&q=" + encodeURIComponent(en)).then(function (r) { return r.json(); });

    Promise.all([gs, ge]).then(function (res) {
        if (!res[0] || !res[0].length) { alert('Cannot find: "' + st + '"'); journeyBtn.disabled = false; hideStatus(); return; }
        if (!res[1] || !res[1].length) { alert('Cannot find: "' + en + '"'); journeyBtn.disabled = false; hideStatus(); return; }
        startLatLng = L.latLng(parseFloat(res[0][0].lat), parseFloat(res[0][0].lon));
        endLatLng = L.latLng(parseFloat(res[1][0].lat), parseFloat(res[1][0].lon));
        beginJourney();
    }).catch(function () { alert("Network error. Check your internet."); journeyBtn.disabled = false; hideStatus(); });
});

// =======================
// BEGIN JOURNEY
// =======================
function beginJourney() {
    navPanel.style.display = "none";
    toggleNav.style.display = "flex";

    if (driver) { map.removeLayer(driver); driver = null; }
    if (moveTimeout) clearTimeout(moveTimeout);
    isPaused = false;
    ignoredPotholes.clear(); revealedPotholes.clear(); warnedPotholes.clear();
    routeCoordinates = []; routeAlternatives = []; currentStep = 0;
    Object.keys(shownPotholeLayers).forEach(function (k) {
        try { map.removeLayer(shownPotholeLayers[k].marker); } catch (e) { }
        try { map.removeLayer(shownPotholeLayers[k].circle); } catch (e) { }
    });
    shownPotholeLayers = {};
    if (origRouteLine) { map.removeLayer(origRouteLine); origRouteLine = null; }
    if (safeRouteLine) { map.removeLayer(safeRouteLine); safeRouteLine = null; }
    if (routingControl) { try { map.removeControl(routingControl); } catch (e) { } routingControl = null; }

    showStatus("🛣️ Calculating route...");

    routingControl = L.Routing.control({
        waypoints: [startLatLng, endLatLng],
        router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1', profile: 'driving' }),
        routeWhileDragging: false, addWaypoints: false, show: false, fitSelectedRoutes: false,
        lineOptions: { styles: [{ opacity: 0, weight: 0 }] },
        createMarker: function (i, wp) { return L.marker(wp.latLng).bindPopup(i === 0 ? '🟢 Start' : '🔴 End'); }
    }).addTo(map);

    routingControl.on('routesfound', function (e) {
        console.log("Routes found:", e.routes.length);
        routeAlternatives = e.routes;
        var route0 = e.routes[0];

        // Find safest alternative
        var score0 = scorePotholes(route0.coordinates);
        var safeRoute = route0;
        for (var i = 1; i < e.routes.length; i++) {
            var s = scorePotholes(e.routes[i].coordinates);
            if (s < score0) { safeRoute = e.routes[i]; score0 = s; }
        }

        routeCoordinates = safeRoute.coordinates;
        currentStep = 0;

        var bounds = L.latLngBounds(routeCoordinates.map(function (c) { return [c.lat, c.lng]; }));
        map.fitBounds(bounds, { padding: [60, 60] });

        // Save original route coords (this is the path the car is on initially)
        origRouteCoords = route0.coordinates;

        // Draw initial route in GREEN
        safeRouteLine = L.polyline(routeCoordinates.map(function (c) { return [c.lat, c.lng]; }),
            { color: '#00c853', weight: 7, opacity: 0.95 }).addTo(map);
        safeRouteLine.bindTooltip('🟢 Initial Route', { sticky: true });

        // (legend removed)

        showStatus("✅ Route ready — Starting journey...");
        setTimeout(function () { hideStatus(); startDriver(); }, 1200);
    });

    routingControl.on('routingerror', function (e) {
        console.error("Routing error:", e);
        showStatus("❌ No route found. Try different cities.");
        setTimeout(hideStatus, 4000); journeyBtn.disabled = false;
    });
}

// =======================
// POTHOLE SCORING
// =======================
function scorePotholes(coords) {
    var score = 0;
    potholes.forEach(function (p) {
        for (var i = 0; i < coords.length; i++) {
            if (map.distance([coords[i].lat, coords[i].lng], [p.lat, p.lng]) < 1500) {
                score += p.risk === 'critical' ? 10 : p.risk === 'medium' ? 5 : 1;
                break;
            }
        }
    });
    return score;
}

// =======================
// POTHOLE MARKER REVEAL
// =======================
function riskColor(r) { return r === 'critical' ? '#e74c3c' : r === 'medium' ? '#f39c12' : '#2ecc71'; }

function revealPotholeMarker(p) {
    var key = p.lat + "," + p.lng;
    if (revealedPotholes.has(key)) return;
    revealedPotholes.add(key);
    var col = riskColor(p.risk);
    var icon = L.divIcon({
        html: '<div style="font-size:26px;text-align:center;filter:drop-shadow(0 0 6px ' + col + ')">🕳️</div>',
        iconSize: [30, 30], className: ""
    });
    var marker = L.marker([p.lat, p.lng], { icon: icon }).addTo(map)
        .bindPopup('<b>⚠ Pothole</b><br>Risk: <b style="color:' + col + '">' + (p.risk || '?').toUpperCase() + '</b>');
    var circle = L.circle([p.lat, p.lng], { color: col, fillColor: col, fillOpacity: 0.2, radius: 80, weight: 2 }).addTo(map);
    shownPotholeLayers[key] = { marker: marker, circle: circle };
}

// =======================
// BEARING HELPER
// =======================
function getBearing(from, to) {
    var r = Math.PI / 180;
    var lat1 = from.lat * r, lat2 = to.lat * r;
    var dLng = (to.lng - from.lng) * r;
    var y = Math.sin(dLng) * Math.cos(lat2);
    var x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng);
    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}

var carImg = null; // reference to the <img> inside the car marker

// =======================
// DRIVER
// =======================
function startDriver() {
    if (!routeCoordinates.length) return;
    
    // Original car icon
    var carIcon = L.icon({ 
        iconUrl: "https://cdn-icons-png.flaticon.com/512/744/744465.png", 
        iconSize: [36, 36],
        iconAnchor: [18, 18],
        tooltipAnchor: [0, -15]
    });
    
    driver = L.marker([routeCoordinates[0].lat, routeCoordinates[0].lng], { icon: carIcon })
        .addTo(map).bindTooltip("🚗 You", { permanent: true, direction: "top", offset: [0, -15] });
    // Smooth position transition on the outer element
    var el = driver.getElement();
    if (el) {
        el.style.transition = "transform 0.18s linear";
        // Cache the img element for rotation
        carImg = el.querySelector('img');
        if (carImg) carImg.style.transition = "transform 0.2s linear";
    }
    moveDriver();
}

function moveDriver() {
    if (currentStep >= routeCoordinates.length) { showStatus("🏁 Arrived at destination!"); return; }
    if (isPaused) return;
    var pt = routeCoordinates[currentStep];
    driver.setLatLng([pt.lat, pt.lng]);

    // Rotate and flip car to face direction of travel
    // We add scaleX(-1) to flip the image horizontally as requested
    if (carImg && currentStep + 1 < routeCoordinates.length) {
        var bearing = getBearing(pt, routeCoordinates[currentStep + 1]);
        carImg.style.transform = 'scale(-1, 1) rotate(' + (bearing - 90) + 'deg)';
    }

    checkPotholeAhead(pt);
    if (!isPaused) { currentStep++; moveTimeout = setTimeout(moveDriver, 180); }
}

// =======================
// POTHOLE DETECTION
// Distances tuned for long-distance highway simulation
// =======================
var LOOK_AHEAD = 150;    // route points to scan ahead
var ON_ROUTE = 1500;     // metres — pothole must be near a future route point
var REVEAL_DIST = 1500;  // metres from car — show marker
var WARN_DIST = 1500;    // metres from car — show popup

function checkPotholeAhead(pos) {
    if (isPaused) return;
    var endIdx = Math.min(currentStep + LOOK_AHEAD, routeCoordinates.length);

    potholes.forEach(function (p) {
        if (isPaused) return;
        var key = p.lat + "," + p.lng;
        if (ignoredPotholes.has(key)) return;

        // Check if pothole is near any upcoming route point
        var onPath = false;
        for (var i = currentStep; i < endIdx; i++) {
            if (map.distance([routeCoordinates[i].lat, routeCoordinates[i].lng], [p.lat, p.lng]) <= ON_ROUTE) {
                onPath = true; break;
            }
        }
        if (!onPath) return;

        var dist = map.distance([pos.lat, pos.lng], [p.lat, p.lng]);

        // Reveal marker
        if (dist <= REVEAL_DIST && !revealedPotholes.has(key)) {
            revealPotholeMarker(p);
        }

        // Trigger warning popup — pass actual distance
        if (dist <= WARN_DIST && !warnedPotholes.has(key)) {
            warnedPotholes.add(key);
            isPaused = true;
            showPotholeWarning(p, dist);
        }
    });
}

// =======================
// WARNING MODAL
// =======================
function showPotholeWarning(p, distanceM) {
    var risk = (p.risk || "low").toUpperCase();
    var key = p.lat + "," + p.lng;

    // Reveal red route exactly through the pothole
    if (!origRouteLine) {
        var potholeRouteIdx = currentStep;
        var minD = Infinity;
        for (var pi = currentStep; pi < Math.min(currentStep + 200, routeCoordinates.length); pi++) {
            var dd = map.distance([routeCoordinates[pi].lat, routeCoordinates[pi].lng], [p.lat, p.lng]);
            if (dd < minD) { minD = dd; potholeRouteIdx = pi; }
        }

        var redPath = [];
        var carPos = driver.getLatLng();
        redPath.push([carPos.lat, carPos.lng]);
        for (var ri = currentStep; ri < potholeRouteIdx; ri++) {
            redPath.push([routeCoordinates[ri].lat, routeCoordinates[ri].lng]);
        }
        redPath.push([p.lat, p.lng]);
        var afterEnd = Math.min(potholeRouteIdx + 25, routeCoordinates.length);
        for (var ri2 = potholeRouteIdx + 1; ri2 < afterEnd; ri2++) {
            redPath.push([routeCoordinates[ri2].lat, routeCoordinates[ri2].lng]);
        }

        origRouteLine = L.polyline(redPath, { color: '#f44336', weight: 8, opacity: 1.0 })
            .addTo(map)
            .bindTooltip('🔴 Pothole Path', { sticky: true });
    }

    // We no longer search static routeAlternatives here.
    // The Reroute button will now trigger a live recalculation from the car's current position.
    var canReroute = true; // Always allow attempting a live reroute

    showModal(risk, distanceM || 0, canReroute,
        // onReroute — LIVE DYNAMIC RECALCULATION
        function () {
            showStatus("🔄 Calculating new route avoiding pothole...");
            if (origRouteLine) { map.removeLayer(origRouteLine); origRouteLine = null; }
            if (safeRouteLine) { map.removeLayer(safeRouteLine); safeRouteLine = null; }

            // Ask OSRM for a new route from CAR POSITION to DESTINATION
            var carPos = driver.getLatLng();

            // To force OSRM to avoid this road, we can pass bearings or use a different service.
            // Since public OSRM /route/v1 doesn't officially support 'avoid' polygons natively without custom profiles,
            // we will simulate an 'avoid' by forcing the router to find an alternative.
            // The Leaflet Routing Machine alternative is to ask for multiple routes from current pos.

            var tempRouting = L.Routing.control({
                waypoints: [carPos, endLatLng],
                router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1', profile: 'driving' }),
                show: false, addWaypoints: false, fitSelectedRoutes: false, createMarker: function () { return null; }
            });

            tempRouting.on('routesfound', function (e) {
                var newRoutes = e.routes;
                var bestAlt = newRoutes[0];

                // Try to find one that doesn't go through our pothole 'p'
                for (var i = 0; i < newRoutes.length; i++) {
                    var r = newRoutes[i];
                    var hit = false;
                    for (var j = 0; j < Math.min(100, r.coordinates.length); j++) {
                        if (map.distance([r.coordinates[j].lat, r.coordinates[j].lng], [p.lat, p.lng]) < 100) {
                            hit = true; break;
                        }
                    }
                    if (!hit) { bestAlt = r; break; }
                }

                // Draw new safe route
                safeRouteLine = L.polyline(bestAlt.coordinates.map(function (c) { return [c.lat, c.lng]; }),
                    { color: '#00c853', weight: 7, opacity: 0.95 }).addTo(map);
                safeRouteLine.bindTooltip('🟢 Rerouted Safe Path', { sticky: true });

                // Switch car to new route smoothly
                rerouteDriverLive(p, bestAlt.coordinates);
                tempRouting = null; // cleanup
            });

            tempRouting.on('routingerror', function (e) {
                showStatus("❌ Reroute failed. Continuing...");
                setTimeout(hideStatus, 2000);
                ignoredPotholes.add(key); isPaused = false; moveDriver();
            });

            tempRouting.route(); // execute the API call
        },
        // onContinue — Keep RED line, remove GREEN line, switch to RED path
        function () {
            ignoredPotholes.add(key);
            if (safeRouteLine) { map.removeLayer(safeRouteLine); safeRouteLine = null; }
            if (origRouteLine) { origRouteLine.bringToFront(); } // ensure red is on top

            if (origRouteCoords.length) {
                var pos = driver.getLatLng();
                var closest = 0, minD = Infinity;
                for (var ci = 0; ci < origRouteCoords.length; ci++) {
                    var d = map.distance([pos.lat, pos.lng], [origRouteCoords[ci].lat, origRouteCoords[ci].lng]);
                    if (d < minD) { minD = d; closest = ci; }
                }
                routeCoordinates = origRouteCoords;
                currentStep = closest;
            }
            isPaused = false;
            moveDriver();
        }
    );
}

// =======================
// LIVE REROUTING
// =======================
function rerouteDriverLive(p, newCoordinates) {
    // 1. Replace our entire remaining journey with these new coordinates
    routeCoordinates = newCoordinates;

    // 2. We start from the very beginning of this new array (index 0) 
    // because the API calculated it from our exact current position!
    currentStep = 0;

    // 3. Mark the pothole as ignored so we don't warn about it again if we accidentally clip its radius
    ignoredPotholes.add(p.lat + "," + p.lng);

    // 4. Unpause and resume driving from our current spot smoothly onto the new road
    isPaused = false;
    showStatus("✅ Reroute successful! Resuming...");
    setTimeout(hideStatus, 2500);
    moveDriver();
}
