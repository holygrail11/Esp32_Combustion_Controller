"""
web_server.py
HTTP web server for the combustion controller dashboard.

Features:
  - Serves an embedded HTML dashboard
  - JSON API endpoints for sensor data
  - Real-time graphs using Chart.js
  - Auto-refresh every 1 second

WiFi setup:
  Create a file called secrets.py in the ESP32 root:
    SSID = "your-wifi-name"
    PASSWORD = "your-wifi-password"

  Or hardcode them in main.py before starting the web server.

Usage:
    from web_server import WebServer
    from data_logger import DataLogger
    
    logger = DataLogger()
    server = WebServer(logger, ssid="MyWiFi", password="pass123")
    server.start()  # Blocking — runs forever
"""

import socket
import json
import time
from data_logger import DataLogger

# Try to import secrets.py if it exists (optional)
try:
    from secrets import SSID, PASSWORD
except ImportError:
    SSID = None
    PASSWORD = None


class WebServer:
    """
    Lightweight HTTP server for the dashboard.
    Serves HTML + handles JSON API requests.
    """

    # Embedded HTML dashboard
    DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Combustion Controller</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            text-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
        }
        .card-title {
            font-size: 14px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
            font-weight: 600;
        }
        .card-value {
            font-size: 32px;
            font-weight: bold;
            color: #333;
        }
        .card-unit {
            font-size: 14px;
            color: #999;
            margin-top: 4px;
        }
        .status-badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 8px;
            width: fit-content;
        }
        .badge-on { background: #4ade80; color: white; }
        .badge-off { background: #ef4444; color: white; }
        .badge-normal { background: #3b82f6; color: white; }
        .badge-high { background: #f59e0b; color: white; }
        .badge-critical { background: #ef4444; color: white; }
        .charts {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .chart-container {
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        }
        .chart-title {
            font-size: 18px;
            font-weight: 600;
            color: #333;
            margin-bottom: 16px;
        }
        canvas { max-height: 300px; }
        .footer {
            text-align: center;
            color: rgba(255,255,255,0.8);
            font-size: 12px;
            margin-top: 40px;
        }
        .status-zone {
            font-size: 18px;
            font-weight: bold;
            color: #333;
            margin-top: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔥 Combustion Controller</h1>

        <!-- Current Status Cards -->
        <div class="grid">
            <div class="card">
                <div class="card-title">Temperature</div>
                <div class="card-value" id="temp">--</div>
                <div class="card-unit">Celsius</div>
            </div>
            <div class="card">
                <div class="card-title">Smoke Level</div>
                <div class="card-value" id="smoke">--</div>
                <div class="card-unit">Raw ADC (0-4095)</div>
                <span class="status-badge" id="smoke-badge">--</span>
            </div>
            <div class="card">
                <div class="card-title">Zone</div>
                <div class="status-zone" id="zone">--</div>
                <div class="card-unit" id="purpose">--</div>
            </div>
            <div class="card">
                <div class="card-title">Servo Position</div>
                <div class="card-value" id="servo">--</div>
                <div class="card-unit">Degrees</div>
            </div>
            <div class="card">
                <div class="card-title">Fan</div>
                <span class="status-badge" id="fan-badge">--</span>
            </div>
            <div class="card">
                <div class="card-title">Buzzer</div>
                <span class="status-badge" id="buzzer-badge">--</span>
            </div>
        </div>

        <!-- Charts -->
        <div class="charts">
            <div class="chart-container">
                <div class="chart-title">Temperature (last 5 min)</div>
                <canvas id="tempChart"></canvas>
            </div>
            <div class="chart-container">
                <div class="chart-title">Smoke Level (last 5 min)</div>
                <canvas id="smokeChart"></canvas>
            </div>
        </div>

        <div class="footer">
            Last updated: <span id="updated">never</span> · Polling every 1 second
        </div>
    </div>

    <script>
        // Create charts
        const tempCtx = document.getElementById('tempChart').getContext('2d');
        const smokeCtx = document.getElementById('smokeChart').getContext('2d');

        const tempChart = new Chart(tempCtx, {
            type: 'line',
            data: { labels: [], datasets: [{ label: 'Temperature (C)', data: [], borderColor: '#ef4444', backgroundColor: 'rgba(239, 68, 68, 0.1)', tension: 0.1 }] },
            options: { responsive: true, maintainAspectRatio: true, scales: { y: { beginAtZero: true, max: 250 } } }
        });

        const smokeChart = new Chart(smokeCtx, {
            type: 'line',
            data: { labels: [], datasets: [{ label: 'Smoke (raw)', data: [], borderColor: '#f59e0b', backgroundColor: 'rgba(245, 158, 11, 0.1)', tension: 0.1 }] },
            options: { responsive: true, maintainAspectRatio: true, scales: { y: { beginAtZero: true, max: 1024 } } }
        });

        // Fetch and update data
        async function updateData() {
            try {
                const res = await fetch('/api/data?n=60');
                const data = await res.json();

                if (data.length === 0) return;

                const latest = data[data.length - 1];

                // Update cards
                document.getElementById('temp').textContent = latest.temp.toFixed(1);
                document.getElementById('smoke').textContent = latest.smoke_raw;
                document.getElementById('servo').textContent = latest.servo;
                document.getElementById('zone').textContent = 'Zone ' + latest.zone;
                document.getElementById('purpose').textContent = '(Zone ' + latest.zone + ')';

                // Update badges
                document.getElementById('fan-badge').textContent = latest.fan ? 'ON' : 'OFF';
                document.getElementById('fan-badge').className = 'status-badge ' + (latest.fan ? 'badge-on' : 'badge-off');

                document.getElementById('buzzer-badge').textContent = latest.buzzer ? 'ON' : 'OFF';
                document.getElementById('buzzer-badge').className = 'status-badge ' + (latest.buzzer ? 'badge-on' : 'badge-off');

                document.getElementById('smoke-badge').textContent = latest.smoke_level.toUpperCase();
                const smokeBadgeClass = 'status-badge badge-' + latest.smoke_level;
                document.getElementById('smoke-badge').className = smokeBadgeClass;

                // Update timestamp
                const now = new Date();
                document.getElementById('updated').textContent = now.toLocaleTimeString();

                // Update charts
                const labels = data.map((_, i) => i);
                const temps = data.map(d => d.temp);
                const smokes = data.map(d => d.smoke_raw);

                tempChart.data.labels = labels;
                tempChart.data.datasets[0].data = temps;
                tempChart.update('none');

                smokeChart.data.labels = labels;
                smokeChart.data.datasets[0].data = smokes;
                smokeChart.update('none');

            } catch (error) {
                console.error('Error fetching data:', error);
            }
        }

        // Poll every 1 second
        updateData();
        setInterval(updateData, 1000);
    </script>
</body>
</html>"""

    def __init__(self, data_logger, ssid=None, password=None, port=80):
        """
        Initialise the web server.

        Args:
            data_logger: DataLogger instance to read from
            ssid:        WiFi SSID (or use secrets.py)
            password:    WiFi password (or use secrets.py)
            port:        HTTP port (default 80)
        """
        self.logger = data_logger
        self.ssid = ssid or SSID
        self.password = password or PASSWORD
        self.port = port
        self.server_socket = None
        self.wlan = None

    def start(self):
        """Connect to WiFi and start the HTTP server (blocks forever)."""
        if not self.ssid or not self.password:
            raise ValueError("WiFi SSID and password not provided")

        print("[WebServer] Connecting to WiFi: {}".format(self.ssid))
        self._connect_wifi()
        print("[WebServer] Connected! IP: {}".format(self.wlan.ifconfig()[0]))
        print("[WebServer] Dashboard: http://{}".format(self.wlan.ifconfig()[0]))

        self._start_http_server()

    def _connect_wifi(self):
        """Connect to WiFi."""
        import network
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.wlan.connect(self.ssid, self.password)

        timeout = 30  # Increased from 20 to 30 seconds
        while timeout > 0 and not self.wlan.isconnected():
            print("[WebServer] Attempting to connect... ({} seconds left)".format(timeout))
            time.sleep(0.5)
            timeout -= 1

        if not self.wlan.isconnected():
            print("[WebServer] Failed to connect to WiFi: {}".format(self.ssid))
            print("[WebServer] Check your SSID and password in secrets.py or main.py")
            raise RuntimeError("Failed to connect to WiFi")
        
        print("[WebServer] WiFi connected!")

    def _start_http_server(self):
        """Start the HTTP server."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", self.port))
        self.server_socket.listen(5)
        print("[WebServer] Listening on port {}".format(self.port))

        while True:
            try:
                client_socket, client_addr = self.server_socket.accept()
                self._handle_request(client_socket, client_addr)
            except Exception as e:
                print("[WebServer] Error: {}".format(e))

    def _handle_request(self, client_socket, client_addr):
        """Handle a single HTTP request."""
        try:
            # Read request line
            request = b""
            while True:
                chunk = client_socket.recv(1024)
                if not chunk:
                    break
                request += chunk
                if b"\r\n\r\n" in request:
                    break

            request_str = request.decode("utf-8", errors="ignore")
            lines = request_str.split("\r\n")
            request_line = lines[0]

            method, path, protocol = request_line.split(" ")

            if path == "/":
                self._send_response(client_socket, 200, "text/html", self.DASHBOARD_HTML)
            elif path.startswith("/api/data"):
                self._handle_api_data(client_socket, path)
            elif path.startswith("/api/latest"):
                self._handle_api_latest(client_socket)
            else:
                self._send_response(client_socket, 404, "text/plain", "Not Found")

        except Exception as e:
            print("[WebServer] Request error: {}".format(e))
        finally:
            try:
                client_socket.close()
            except:
                pass

    def _handle_api_data(self, client_socket, path):
        """Handle GET /api/data?n=60 — return last n readings as JSON."""
        n = 60  # default
        if "?" in path:
            query = path.split("?")[1]
            if "n=" in query:
                try:
                    n = int(query.split("n=")[1])
                except:
                    pass

        data = self.logger.get_last_n(n)
        json_str = json.dumps(data)
        self._send_response(client_socket, 200, "application/json", json_str)

    def _handle_api_latest(self, client_socket):
        """Handle GET /api/latest — return most recent reading as JSON."""
        latest = self.logger.get_latest()
        if latest:
            json_str = json.dumps(latest)
        else:
            json_str = "{}"
        self._send_response(client_socket, 200, "application/json", json_str)

    def _send_response(self, client_socket, status_code, content_type, body):
        """Send an HTTP response."""
        status_text = {
            200: "OK",
            404: "Not Found",
            500: "Internal Server Error",
        }.get(status_code, "Unknown")

        if isinstance(body, str):
            body = body.encode("utf-8")

        response = (
            "HTTP/1.1 {} {}\r\n"
            "Content-Type: {}; charset=utf-8\r\n"
            "Content-Length: {}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).format(status_code, status_text, content_type, len(body))

        client_socket.send(response.encode("utf-8"))
        client_socket.send(body)
