#!/usr/bin/env python3
"""Local dev server: serves flasher static files + proxies /nvs/ to nvs_api."""
import http.server
import urllib.request
import urllib.error
import json
import os

PORT = 8080
NVS_API = "http://127.0.0.1:8765"
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_POST(self):
        if self.path.startswith("/nvs/"):
            upstream_path = self.path[len("/nvs"):]  # strip /nvs prefix
            self._proxy(upstream_path)
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        if self.path.startswith("/nvs/"):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()
        else:
            self.send_error(404)

    def _proxy(self, path):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        url = NVS_API + path
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": self.headers.get("Content-Type", "application/json")},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.headers.get("Content-Type", "application/octet-stream"))
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")


if __name__ == "__main__":
    os.chdir(STATIC_DIR)
    with http.server.HTTPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"Flasher dev server: http://localhost:{PORT}/")
        print(f"Proxying /nvs/ → {NVS_API}")
        print("Ctrl+C to stop\n")
        httpd.serve_forever()
