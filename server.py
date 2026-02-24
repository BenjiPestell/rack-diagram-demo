#!/usr/bin/env python3
"""
RackForge Server
================
Serves rack-designer.html and exposes a /run endpoint so the browser
can trigger run.py directly — no watcher script needed.

Usage
-----
    python3 server.py

Then open:  http://localhost:8765

Options
-------
    python3 server.py --port 8765          # change port (default 8765)
    python3 server.py --run run.py         # script to execute (default run.py)
    python3 server.py --yaml rack-design.yaml  # output filename (default rack-design.yaml)
    python3 server.py --no-open            # don't auto-open browser

The ▶ Run button in the UI will:
  1. POST the current YAML to this server
  2. Server writes it to disk as the output file
  3. Server executes run.py and streams stdout/stderr back
  4. Output appears in a panel at the bottom of the UI
"""

import argparse
import json
import os
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# ── Config (overridden by CLI args) ──────────────────────────────────────────
DEFAULT_PORT     = 8765
DEFAULT_SCRIPT   = "run.py"
DEFAULT_FILENAME = "rack-design.yaml"
HTML_FILE        = "claude_rackarch.html"  # "rack-designer.html"

BASE_DIR = Path(__file__).parent.resolve()


class RackForgeHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Cleaner logging
        method = args[0] if args else ''
        code   = args[1] if len(args) > 1 else ''
        if '/run' in str(method):
            colour = '\033[92m' if str(code) == '200' else '\033[91m'
            print(f"  {colour}[{code}]\033[0m  {method}")
        elif str(code) not in ('200', '304'):
            print(f"  [{code}]  {fmt % args}")

    def send_json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def send_cors_preflight(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    # ── OPTIONS (CORS preflight) ──────────────────────────────────────────────
    def do_OPTIONS(self):
        self.send_cors_preflight()

    # ── GET ───────────────────────────────────────────────────────────────────
    def do_GET(self):
        path = self.path.split('?')[0]

        if path in ('/', '/index.html', f'/{HTML_FILE}'):
            self._serve_file(BASE_DIR / HTML_FILE, 'text/html; charset=utf-8')
        elif path == '/health':
            self.send_json(200, {'ok': True, 'server': 'RackForge'})
        else:
            # Try to serve as a static file (css, js, etc.)
            file_path = BASE_DIR / path.lstrip('/')
            if file_path.exists() and file_path.is_file():
                mime = self._mime(file_path.suffix)
                self._serve_file(file_path, mime)
            else:
                self.send_json(404, {'error': f'Not found: {path}'})

    def _serve_file(self, path, mime):
        try:
            data = Path(path).read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', len(data))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_json(404, {'error': f'File not found: {path}'})

    def _mime(self, ext):
        return {
            '.html': 'text/html; charset=utf-8',
            '.js':   'application/javascript',
            '.css':  'text/css',
            '.yaml': 'text/yaml',
            '.yml':  'text/yaml',
            '.json': 'application/json',
            '.png':  'image/png',
            '.ico':  'image/x-icon',
        }.get(ext.lower(), 'application/octet-stream')

    # ── POST /run ─────────────────────────────────────────────────────────────
    def do_POST(self):
        if self.path != '/run':
            self.send_json(404, {'error': 'Unknown endpoint'})
            return

        # Read body
        length = int(self.headers.get('Content-Length', 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception as e:
            self.send_json(400, {'ok': False, 'error': f'Bad JSON: {e}'})
            return

        yaml_text = body.get('yaml', '')
        filename  = body.get('filename', self.server.yaml_filename)

        # Sanitise filename — no path traversal
        filename = Path(filename).name or self.server.yaml_filename
        yaml_path = BASE_DIR / filename

        # Write YAML to disk
        try:
            yaml_path.write_text(yaml_text, encoding='utf-8')
            print(f"  [WRITE] {yaml_path}")
        except Exception as e:
            self.send_json(500, {'ok': False, 'error': f'Could not write YAML: {e}'})
            return

        # Execute run.py
        script = self.server.run_script
        script_path = BASE_DIR / script

        if not script_path.exists():
            self.send_json(500, {
                'ok': False,
                'error': f'{script} not found in {BASE_DIR}',
                'output': f"Expected: {script_path}\n\nMake sure run.py is in the same directory as server.py."
            })
            return

        print(f"  [EXEC]  python3 {script_path}")
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                cwd=str(BASE_DIR),
                env={
                    **os.environ,
                    'RACKFORGE_YAML': str(yaml_path),
                    'RACKFORGE_FILENAME': filename,
                },
                timeout=120,
            )
            stdout = result.stdout
            stderr = result.stderr
            combined = stdout
            if stderr:
                combined += ('\n' if combined else '') + '--- stderr ---\n' + stderr
            ok = result.returncode == 0
            print(f"  [EXIT]  code={result.returncode}")
            if stderr and not ok:
                print(f"  [ERR]   {stderr[:200]}")
            self.send_json(200, {
                'ok': ok,
                'returncode': result.returncode,
                'output': combined or '(no output)',
            })
        except subprocess.TimeoutExpired:
            self.send_json(200, {
                'ok': False,
                'output': 'Error: run.py timed out after 120 seconds.',
            })
        except Exception as e:
            self.send_json(500, {'ok': False, 'error': str(e), 'output': str(e)})


def main():
    parser = argparse.ArgumentParser(description='RackForge local server')
    parser.add_argument('--port',    type=int, default=DEFAULT_PORT,     help=f'Port (default {DEFAULT_PORT})')
    parser.add_argument('--run',     default=DEFAULT_SCRIPT,             help=f'Script to run (default {DEFAULT_SCRIPT})')
    parser.add_argument('--yaml',    default=DEFAULT_FILENAME,           help=f'YAML output filename (default {DEFAULT_FILENAME})')
    parser.add_argument('--no-open', action='store_true',                help="Don't open browser automatically")
    args = parser.parse_args()

    # Check HTML file exists
    html_path = BASE_DIR / HTML_FILE
    if not html_path.exists():
        print(f"\033[91m[ERROR]\033[0m {HTML_FILE} not found in {BASE_DIR}")
        sys.exit(1)

    server = HTTPServer(('localhost', args.port), RackForgeHandler)
    server.run_script    = args.run
    server.yaml_filename = args.yaml

    url = f'http://localhost:{args.port}'

    print(f"""
\033[96m\033[1m  RackForge Server\033[0m
  \033[2mServing  : {html_path}
  Script   : {BASE_DIR / args.run}
  YAML out : {BASE_DIR / args.yaml}
  URL      : \033[0m\033[96m{url}\033[0m
""")

    if not args.no_open:
        webbrowser.open(url)
        print(f"  \033[2mOpening browser...\033[0m")

    print(f"  \033[2mPress Ctrl+C to stop.\033[0m\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n\033[2m  Server stopped.\033[0m')


if __name__ == '__main__':
    main()