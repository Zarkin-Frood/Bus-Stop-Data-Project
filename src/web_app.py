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
        html = b"""
        <html>
          <head><title>Route 82 Crime App</title></head>
          <body>
            <h1>Route 82 Crime & Bus Stops</h1>
            <!-- TODO: add JS for map, dropdown, and message board -->
          </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

def run_server(app_features, message_board, host="0.0.0.0", port=8000, logger=None):
    WebApp.app_features = app_features
    WebApp.message_board = message_board
    server = HTTPServer((host, port), WebApp)
    logger.info(f"Listening on http://{host}:{port}")
    server.serve_forever()
