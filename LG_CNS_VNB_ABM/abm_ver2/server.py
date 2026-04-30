#!/usr/bin/env python3
"""
LG CNS Developer Productivity ABM — 웹 서버
실행: python server.py
브라우저: http://localhost:8765
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from http.server import HTTPServer, BaseHTTPRequestHandler
from simulate import run_simulation
import warnings
warnings.filterwarnings("ignore")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  {args[0]} {args[1]}")

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self._serve_file('dashboard.html', 'text/html')
        else:
            self._send(404, b'Not found')

    def do_POST(self):
        if self.path == '/simulate':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            params = json.loads(body) if body else {}
            print(f"\n  Running simulation: {params}")
            result = run_simulation(params)
            data = json.dumps(result).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(data))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(data)
        else:
            self._send(404, b'Not found')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _serve_file(self, filename, content_type):
        path = os.path.join(os.path.dirname(__file__), filename)
        try:
            with open(path, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Content-Length', len(data))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self._send(404, b'File not found')

    def _send(self, code, body):
        self.send_response(code)
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    # Render / Fly / Railway 등은 PORT 환경 변수를 넣어줌 (없으면 8765)
    port = int(os.environ.get("PORT", "8765"))
    print(f"\n  LG CNS Developer Productivity ABM")
    print(f"  ─────────────────────────────────")
    print(f"  서버 시작: http://0.0.0.0:{port}  (로컬: http://localhost:{port})")
    print(f"  종료: Ctrl+C\n")
    server = HTTPServer(('0.0.0.0', port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  서버 종료")
