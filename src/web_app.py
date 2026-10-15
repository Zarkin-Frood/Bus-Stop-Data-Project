from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse

class WebApp(BaseHTTPRequestHandler):
    app_features = None
    message_board = None

    def _send_json(self, obj, status=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        params = urllib.parse.parse_qs(query)

        if path == "/api/stops":
            radius = float(params.get("radius", ["250"])[0])
            data = self.app_features.compute_stop_scores(radius_m=radius)
            self._send_json(data)
        elif path == "/api/heatmap":
            data = self.app_features.heatmap_points()
            self._send_json(data)
        elif path == "/api/messages":
            stop_id = params.get("stop_id", [None])[0]
            msgs = self.message_board.list_messages(stop_id)
            self._send_json([m.__dict__ for m in msgs])
        elif path in ("/", "/index.html"):
            self._serve_index()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/messages":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            data = urllib.parse.parse_qs(body)
            user = data.get("user", ["anonymous"])[0]
            text = data.get("text", [""])[0]
            stop_id = data.get("stop_id", [None])[0]
            msg = self.message_board.add_message(user, text, stop_id=stop_id)
            self._send_json(msg.__dict__)
        else:
            self.send_error(404)

    def _serve_index(self):
        doctype = "<!DOCTYPE html>"
        html_body = """<html>
<head>
<title>Route 82 Crime App</title>
<meta charset="utf-8">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 0; padding: 20px; background: #f4f6f8; display: flex; flex-direction: column; height: 95vh; }
header { margin-bottom: 15px; }
h1 { color: #1e293b; margin: 0 0 5px 0; }
#dashboard { display: flex; flex: 1; gap: 20px; min-height: 0; }
#map { flex: 2; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); background: #ddd; min-height: 400px; height: 100%; }
#sidebar { flex: 1; display: flex; flex-direction: column; gap: 15px; overflow-y: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
.control-group { display: flex; flex-direction: column; gap: 5px; }
select, input, textarea, button { padding: 8px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 14px; }
button { background: #2563eb; color: white; font-weight: 600; cursor: pointer; border: none; }
button:hover { background: #1d4ed8; }
#message-list { flex: 1; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; overflow-y: auto; background: #f8fafc; font-size: 14px; list-style: none; margin: 0; min-height: 100px; }
.msg-item { margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px dashed #e2e8f0; }
.msg-user { font-weight: bold; color: #1e3a8a; }
</style>
</head>
<body>
<header>
<h1>Route 82 Crime & Bus Stops Dashboard</h1>
<p style="color: #64748b; margin: 0;">Interactive spatial safety auditing engine</p>
</header>
<div id="dashboard">
<div id="map"></div>
<div id="sidebar">
<div class="control-group">
<label for="stop-selector" style="font-weight: 600;">Select a Bus Stop:</label>
<select id="stop-selector" onchange="focusOnStop(this.value)">
<option value="">-- Select or Click a Marker --</option>
</select>
</div>
<div id="stop-details" style="background: #eff6ff; padding: 12px; border-radius: 6px; border: 1px solid #bfdbfe; display: none;">
<h3 id="detail-name" style="margin: 0 0 5px 0; color: #1e40af;">Stop Details</h3>
<p id="detail-score" style="margin: 0; font-weight: bold;">Safety Index Score: --</p>
</div>
<div class="control-group" style="flex: 1; display: flex; flex-direction: column;">
<label style="font-weight: 600; margin-bottom: 5px;">Stop Message Board Logs:</label>
<div id="message-list">Select a bus stop to view neighborhood comments.</div>
</div>
<form id="msg-form" onsubmit="submitComment(event)" style="display: flex; flex-direction: column; gap: 8px;">
<input type="hidden" id="form-stop-id" value="">
<input type="text" id="form-user" placeholder="Your Name" required>
<textarea id="form-text" placeholder="Write a safety or service log comment..." rows="3" required></textarea>
<button type="submit">Submit Log Entry</button>
</form>
</div>
</div>
<script>
// If the Leaflet CDN files did not load, say so instead of leaving a silent grey box.
if (typeof L === 'undefined') {
    document.getElementById('map').textContent =
        'Map library failed to load. Check internet access to cdnjs.cloudflare.com.';
    throw new Error('Leaflet (L) is not defined');
}

const RADIUS_M = 250;

const map = L.map('map').setView([29.7604, -95.3698], 12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

let stopDataGlobal = {};   // stop_id -> stop object from /api/stops
let stopMarkers = {};      // stop_id -> Leaflet marker

function popupNode(name, stop) {
    const box = document.createElement('div');
    const title = document.createElement('b');
    title.textContent = name;
    box.appendChild(title);
    box.appendChild(document.createElement('br'));
    box.appendChild(document.createTextNode(
        'Incidents within ' + RADIUS_M + ' m: ' + stop.crime_count +
        ' | Score: ' + stop.score.toFixed(1)));
    return box;
}

async function initDashboard() {
    try {
        // The API returns a LIST: [{stop_id, name, lat, lon, score, crime_count, rank}, ...]
        const response = await fetch('/api/stops?radius=' + RADIUS_M);
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const stops = await response.json();
        const selector = document.getElementById('stop-selector');
        const coordinates = [];
        stops.forEach(stop => {
            if (stop.lat == null || stop.lon == null || stop.stop_id == null) return;
            const id = String(stop.stop_id);
            const name = stop.name || ('Stop #' + id);
            stopDataGlobal[id] = stop;
            coordinates.push([stop.lat, stop.lon]);

            const opt = document.createElement('option');
            opt.value = id;
            opt.textContent = name + ' (Incidents: ' + stop.crime_count + ')';
            selector.appendChild(opt);

            const color = stop.score > 50 ? 'red' : stop.score > 15 ? 'orange' : 'green';
            const marker = L.circleMarker([stop.lat, stop.lon], {
                radius: 8,
                fillColor: color,
                color: '#fff',
                weight: 1.5,
                opacity: 1,
                fillOpacity: 0.8
            }).addTo(map);
            marker.bindPopup(popupNode(name, stop));
            marker.on('click', () => {
                selector.value = id;
                focusOnStop(id);
            });
            stopMarkers[id] = marker;
        });
        if (coordinates.length > 0) {
            map.fitBounds(L.latLngBounds(coordinates));
        } else {
            document.getElementById('message-list').textContent =
                'No bus stops were returned by the server.';
        }
    } catch (err) {
        console.error('Dashboard Ingestion error:', err);
        document.getElementById('message-list').textContent =
            'Could not load bus stops: ' + err.message;
    }
}

async function focusOnStop(id) {
    const stop = stopDataGlobal[id];
    if (!id || !stop) return;
    map.setView([stop.lat, stop.lon], 16);
    stopMarkers[id].openPopup();
    document.getElementById('form-stop-id').value = id;
    document.getElementById('detail-name').textContent = stop.name || ('Stop #' + id);
    document.getElementById('detail-score').textContent =
        'Safety Score Index: ' + stop.score.toFixed(1) + ' (' + stop.crime_count +
        ' incidents within ' + RADIUS_M + ' m, rank #' + stop.rank + ')';
    document.getElementById('stop-details').style.display = 'block';
    loadComments(id);
}

async function loadComments(stopId) {
    const list = document.getElementById('message-list');
    list.textContent = 'Fetching board logs...';
    try {
        const res = await fetch('/api/messages?stop_id=' + encodeURIComponent(stopId));
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const msgs = await res.json();
        list.textContent = '';
        if (msgs.length === 0) {
            const empty = document.createElement('div');
            empty.style.color = '#64748b';
            empty.textContent = 'No safety reviews submitted for this transit platform yet.';
            list.appendChild(empty);
            return;
        }
        msgs.forEach(m => {
            const item = document.createElement('div');
            item.className = 'msg-item';
            const who = document.createElement('span');
            who.className = 'msg-user';
            who.textContent = (m.user || 'Anonymous') + ': ';
            item.appendChild(who);
            // textContent (not innerHTML) so a comment can never inject markup or script
            item.appendChild(document.createTextNode(m.text || ''));
            list.appendChild(item);
        });
    } catch (err) {
        list.textContent = 'Failed to synchronize comment logs.';
    }
}

async function submitComment(e) {
    e.preventDefault();
    const stopId = document.getElementById('form-stop-id').value;
    const user = document.getElementById('form-user').value;
    const text = document.getElementById('form-text').value;
    if (!stopId) {
        alert('Please select a specific transit bus stop first before logging feedback entries!');
        return;
    }
    try {
        const bodyData = new URLSearchParams();
        bodyData.append('stop_id', stopId);
        bodyData.append('user', user);
        bodyData.append('text', text);
        const res = await fetch('/api/messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: bodyData.toString()
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        document.getElementById('form-text').value = '';
        loadComments(stopId);
    } catch (err) {
        alert('Failed to securely post message updates.');
    }
}
window.onload = initDashboard;
</script>
</body>
</html>"""
        final_html = doctype.strip() + "\n" + html_body.lstrip()
        html_bytes = final_html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()
        self.wfile.write(html_bytes)

def run_server(app_features, message_board, host="0.0.0.0", port=8000, logger=None):
    WebApp.app_features = app_features
    WebApp.message_board = message_board
    server = HTTPServer((host, port), WebApp)
    logger.info(f"Listening on http://{host}:{port}")
    server.serve_forever()
