"""
Rack Designer — launcher / GUI

Starts a Flask server in a background thread and shows a tkinter control panel.
The pipeline runs in-process (no src/ folder or subprocess needed) — all modules
are bundled inside the executable by PyInstaller.

PyInstaller build (single exe, no console):
    pyinstaller RackDesigner.spec --clean --noconfirm

Folder layout expected next to the exe (created automatically on first run):
    RackDesigner.exe   <- the executable
    system.yaml        <- user's rack definition (created blank if missing)
    output/            <- generated dot/csv/html files  (auto-created)
    pngs/              <- rendered PNG diagrams          (auto-created)
"""

import os
import sys
import socket
import threading
import webbrowser
import io
import tkinter as tk
from tkinter import scrolledtext

from flask import Flask, request, jsonify, send_from_directory

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _base_dir() -> str:
    """
    The project root — where system.yaml lives and output/ will be written.
    When frozen by PyInstaller this is the folder containing the .exe.
    When run from source this is the folder containing server.py.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR   = _base_dir()
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
PNG_DIR    = os.path.join(BASE_DIR, "pngs")
YAML_PATH  = os.path.join(BASE_DIR, "system.yaml")
PORT       = 5000

# Static files (HTML) are bundled inside the exe and unpacked to _MEIPASS.
# When running from source they live alongside server.py (same as BASE_DIR).
STATIC_DIR = getattr(sys, "_MEIPASS", BASE_DIR)

# Ensure output directories exist immediately
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(PNG_DIR,    exist_ok=True)

# When frozen with console=False, Windows sets sys.stdout/stderr to None.
# Werkzeug and other libs write to stdout at startup and crash silently.
# Redirect to a log file so nothing gets a None write.
if getattr(sys, "frozen", False) and sys.stdout is None:
    _log_file = open(os.path.join(BASE_DIR, "startup.log"), "w", buffering=1, encoding="utf-8")
    sys.stdout = _log_file
    sys.stderr = _log_file

# Create a blank system.yaml if none exists
if not os.path.exists(YAML_PATH):
    with open(YAML_PATH, "w") as _f:
        _f.write("# Rack Designer configuration\n# Open the Rack Designer in your browser to get started.\n")

# Add STATIC_DIR (==_MEIPASS when frozen) to sys.path so bundled
# pipeline modules are importable.
if STATIC_DIR not in sys.path:
    sys.path.insert(0, STATIC_DIR)

# When running from source (not frozen), pipeline modules live in src/.
if not getattr(sys, "frozen", False):
    _src_dir = os.path.join(BASE_DIR, "src")
    if _src_dir not in sys.path:
        sys.path.insert(0, _src_dir)

# ---------------------------------------------------------------------------
# Pipeline runner — in-process, no subprocess needed
# ---------------------------------------------------------------------------

run_state     = {"running": False, "log": [], "files": []}
run_lock      = threading.Lock()
_log_callback = None


class _LogWriter(io.TextIOBase):
    """Redirect sys.stdout so pipeline print() calls appear in our log."""
    def __init__(self, log_fn):
        self._log = log_fn
        self._buf = ""
        self._in_write = False   # re-entrancy guard

    def write(self, s: str) -> int:
        if self._in_write:
            # Re-entrant call (e.g. from inside _log_callback) — buffer only,
            # never recurse.
            self._buf += s
            return len(s)
        self._in_write = True
        try:
            self._buf += s
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                if line:
                    self._log(line)
        finally:
            self._in_write = False
        return len(s)

    def flush(self):
        if self._buf and not self._in_write:
            self._in_write = True
            try:
                self._log(self._buf)
                self._buf = ""
            finally:
                self._in_write = False


def _run_pipeline():
    with run_lock:
        run_state["running"] = True
        run_state["log"]     = []
        run_state["files"]   = []

    # Capture real stdout before any redirection so log() can always write to it
    real_stdout = sys.stdout

    def log(msg: str):
        try:
            real_stdout.write(msg + "\n")
            real_stdout.flush()
        except (UnicodeEncodeError, AttributeError):
            real_stdout.write(msg.encode("ascii", errors="replace").decode("ascii") + "\n")
            real_stdout.flush()
        run_state["log"].append(msg)
        if _log_callback:
            _log_callback(msg)

    try:
        # All pipeline modules use relative paths — cwd must be BASE_DIR
        os.chdir(BASE_DIR)

        # ── Step 1: run pipeline in-process ─────────────────────────────
        log("Running pipeline...")

        # Import pipeline modules BEFORE redirecting stdout so any module-level
        # print() calls don't hit _LogWriter during import.
        import main as pipeline_main

        # Redirect stdout so print() calls inside main.main() reach our log.
        # log() itself uses real_stdout directly so it never recurses.
        old_stdout = sys.stdout
        sys.stdout = _LogWriter(log)
        try:
            pipeline_main.main()
        except SystemExit as e:
            if e.code not in (None, 0):
                log(f"Pipeline exited with code {e.code}")
        except Exception as e:
            import traceback
            log(f"Pipeline error: {e}")
            for line in traceback.format_exc().splitlines():
                log(f"  {line}")
            return
        finally:
            sys.stdout = old_stdout

        log("Pipeline complete.")

        # ── Step 2: convert .dot -> PNG ──────────────────────────────────
        dot_files = [f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith(".dot")]
        if dot_files:
            log(f"Converting {len(dot_files)} diagram(s) to PNG...")
            import subprocess
            for filename in dot_files:
                dot_path = os.path.join(OUTPUT_DIR, filename)
                png_path = os.path.join(PNG_DIR, os.path.splitext(filename)[0] + ".png")
                # CREATE_NO_WINDOW prevents a console flash on Windows
                _no_window = 0x08000000 if sys.platform == "win32" else 0
                result = subprocess.run(
                    ["dot", "-Tpng:cairo", "-Gdpi=300", dot_path, "-o", png_path],
                    capture_output=True, text=True,
                    creationflags=_no_window
                )
                if result.returncode == 0:
                    log(f"  [ok] {filename}")
                else:
                    log(f"  [stderr] {filename}: {result.stderr.strip()}")
        else:
            log("No .dot files to convert.")

        log("Done.")
        run_state["files"] = {
            "output": os.listdir(OUTPUT_DIR) if os.path.isdir(OUTPUT_DIR) else [],
            "pngs":   os.listdir(PNG_DIR)    if os.path.isdir(PNG_DIR)    else [],
        }

    except Exception as e:
        import traceback
        log(f"Unexpected error: {e}")
        for line in traceback.format_exc().splitlines():
            log(f"  {line}")
    finally:
        run_state["running"] = False
        if _log_callback:
            _log_callback("__DONE__")


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------

def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


LOCAL_IP  = _local_ip()
LOCAL_URL  = f"http://localhost:{PORT}"
NET_URL    = f"http://{LOCAL_IP}:{PORT}"
MOBILE_URL = f"http://{LOCAL_IP}:{PORT}/rack_inspector.html"


def _wifi_ssid() -> str:
    """Return the current Wi-Fi SSID on Windows, or empty string."""
    try:
        import subprocess as _sp
        _no_win = 0x08000000 if sys.platform == "win32" else 0
        r = _sp.run(["netsh", "wlan", "show", "interfaces"],
                    capture_output=True, text=True, creationflags=_no_win)
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("SSID") and "BSSID" not in line:
                return line.split(":", 1)[-1].strip()
    except Exception:
        pass
    return ""


WIFI_SSID = _wifi_ssid()

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

flask_app = Flask(__name__)

import logging
logging.getLogger("werkzeug").setLevel(logging.ERROR)


@flask_app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "rack_designer.html")

@flask_app.route("/rack_inspector.html")
def inspector():
    return send_from_directory(STATIC_DIR, "rack_inspector.html")

@flask_app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)

@flask_app.route("/yaml", methods=["GET"])
def get_yaml():
    try:
        with open(YAML_PATH, "r") as f:
            return f.read(), 200, {"Content-Type": "text/plain"}
    except FileNotFoundError:
        return "", 200, {"Content-Type": "text/plain"}

@flask_app.route("/yaml", methods=["POST"])
def save_yaml():
    with open(YAML_PATH, "w") as f:
        f.write(request.get_data(as_text=True))
    return jsonify({"status": "saved"})

@flask_app.route("/run", methods=["POST"])
def run_endpoint():
    if run_state["running"]:
        return jsonify({"status": "already_running"}), 409
    threading.Thread(target=_run_pipeline, daemon=True).start()
    return jsonify({"status": "started"})

@flask_app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "running": run_state["running"],
        "log":     run_state["log"],
        "files":   run_state["files"],
    })

@flask_app.route("/output/<path:filename>")
def get_output(filename):
    mime_map = {".html": "text/html", ".csv": "text/plain",
                ".txt": "text/plain", ".json": "application/json"}
    ext = os.path.splitext(filename)[1].lower()
    return send_from_directory(OUTPUT_DIR, filename, mimetype=mime_map.get(ext))

@flask_app.route("/pngs/<path:filename>")
def get_png(filename):
    return send_from_directory(PNG_DIR, filename)


def _start_flask():
    flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)


# ---------------------------------------------------------------------------
# QR code helper
# ---------------------------------------------------------------------------

def _make_qr_image(url: str, size: int = 130):
    try:
        import qrcode
        from PIL import ImageTk
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").resize((size, size))
        return ImageTk.PhotoImage(img)
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# tkinter GUI
# ---------------------------------------------------------------------------

# Matches rack_designer.html :root palette
BG      = "#0b0d10"
CARD    = "#181b20"
ACCENT  = "#3fdc6f"
ACCENT2 = "#c91622"
BORDER  = "#2a2e34"
TEXT1   = "#f1f3f5"
TEXT2   = "#6c7077"
RED     = "#e10613"
MONO    = ("Consolas", 8)


def _lighten(h: str) -> str:
    r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
    return f"#{min(255,r+30):02x}{min(255,g+30):02x}{min(255,b+30):02x}"


def _btn(parent, text, cmd, color=ACCENT2, fg="#fff", **kw):
    b = tk.Button(parent, text=text, command=cmd, bg=color, fg=fg,
                  activebackground=color, font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=12, pady=6, cursor="hand2", **kw)
    b.bind("<Enter>", lambda e: b.config(bg=_lighten(color)))
    b.bind("<Leave>", lambda e: b.config(bg=color))
    return b


def build_gui():
    global _log_callback

    root = tk.Tk()
    root.title("Rack Designer")
    root.configure(bg=BG)
    root.resizable(False, False)

    # Set window + taskbar icon.
    # Use wm_iconbitmap with the 'default' parameter so it applies to all
    # windows and persists. Defer via root.after so the window handle exists.
    try:
        icon_path = os.path.join(STATIC_DIR, "icon.ico")
        if os.path.exists(icon_path):
            def _set_icon():
                try:
                    root.wm_iconbitmap(default=icon_path)
                    if sys.platform == "win32":
                        # Also set via Windows API for taskbar / Alt+Tab
                        import ctypes
                        hwnd = ctypes.windll.user32.GetParent(
                            int(root.frame(), 16))
                        _load = ctypes.windll.user32.LoadImageW
                        _send = ctypes.windll.user32.SendMessageW
                        for sz, slot in [(16, 0), (32, 1)]:
                            hicon = _load(None, icon_path, 1, sz, sz, 0x10)
                            if hicon:
                                _send(hwnd, 0x80, slot, hicon)
                except Exception:
                    pass
            root.after(0, _set_icon)
    except Exception:
        pass

    # Header
    hdr = tk.Frame(root, bg=ACCENT2, pady=10)
    hdr.pack(fill="x")
    tk.Label(hdr, text="Rack Designer", font=("Segoe UI", 16, "bold"),
             bg=ACCENT2, fg="#fff").pack()
    tk.Label(hdr, text="Server control panel", font=("Segoe UI", 8),
             bg=ACCENT2, fg="#ffecec").pack()

    body = tk.Frame(root, bg=BG, padx=16, pady=12)
    body.pack(fill="both", expand=True)

    # Status
    sf = tk.Frame(body, bg=BG)
    sf.pack(fill="x", pady=(0, 10))
    tk.Label(sf, text="●", font=("Segoe UI", 14), bg=BG, fg=ACCENT).pack(side="left")
    tk.Label(sf, text=f"Server running on port {PORT}",
             font=("Segoe UI", 10), bg=BG, fg=TEXT1).pack(side="left", padx=6)

    # ── Two-column layout: QR left, URLs + buttons right ───────────────
    content = tk.Frame(body, bg=BG)
    content.pack(fill="x", pady=(0, 10))

    # Left column: QR code pointing at mobile inspector
    qr_img = _make_qr_image(MOBILE_URL)
    if qr_img:
        qf = tk.Frame(content, bg=CARD, padx=10, pady=10)
        qf.pack(side="left", anchor="n")
        tk.Label(qf, text="PHONE / TABLET", font=("Segoe UI", 7, "bold"),
                 bg=CARD, fg=TEXT2).pack()
        tk.Label(qf, text="Rack Inspector", font=("Segoe UI", 9),
                 bg=CARD, fg=TEXT1).pack(pady=(0, 4))
        ql = tk.Label(qf, image=qr_img, bg=CARD)
        ql.image = qr_img
        ql.pack()
        if WIFI_SSID:
            tk.Label(qf, text=f"Wi-Fi:  {WIFI_SSID}", font=("Segoe UI", 8, "bold"),
                     bg=CARD, fg=ACCENT2).pack(pady=(6, 0))
        tk.Label(qf, text=MOBILE_URL, font=("Segoe UI", 7),
                 bg=CARD, fg=TEXT2, wraplength=155).pack(pady=(2, 0))

    # Right column: URL cards + open buttons
    rf = tk.Frame(content, bg=BG)
    rf.pack(side="left", fill="both", expand=True, padx=(10, 0), anchor="n")

    for label, url in [("This computer", LOCAL_URL), ("Network", NET_URL)]:
        card = tk.Frame(rf, bg=CARD, padx=10, pady=8)
        card.pack(fill="x", pady=(0, 6))
        tk.Label(card, text=label, font=("Segoe UI", 8), bg=CARD, fg=TEXT2).pack(anchor="w")
        tk.Label(card, text=url, font=("Consolas", 10, "bold"),
                 bg=CARD, fg=ACCENT2).pack(anchor="w")

    if not qr_img:
        tk.Label(rf, text="Tip: pip install qrcode pillow for phone QR",
                 font=("Segoe UI", 7), bg=BG, fg=TEXT2).pack(anchor="w", pady=(0, 4))

    # Buttons in right column, below URL cards
    _btn(rf, "Open Rack Designer",
         lambda: webbrowser.open(LOCAL_URL)
         ).pack(fill="x", pady=(0, 4))
    _btn(rf, "Open Inspector",
         lambda: webbrowser.open(f"{LOCAL_URL}/rack_inspector.html"),
         color="#6b0a0f", fg="#fff").pack(fill="x")

    # Separator
    tk.Frame(body, bg=CARD, height=1).pack(fill="x", pady=(4, 10))

    # Pipeline row
    pr = tk.Frame(body, bg=BG)
    pr.pack(fill="x", pady=(0, 6))
    tk.Label(pr, text="Pipeline", font=("Segoe UI", 10, "bold"),
             bg=BG, fg=TEXT1).pack(side="left")
    pipe_lbl = tk.Label(pr, text="idle", font=("Segoe UI", 8), bg=BG, fg=TEXT2)
    pipe_lbl.pack(side="left", padx=8)
    run_btn = _btn(pr, "Run Pipeline", lambda: _trigger_run(),
                   color=ACCENT2, fg="#fff")
    run_btn.pack(side="right")

    # Log box
    log_box = scrolledtext.ScrolledText(
        body, height=10, font=MONO,
        bg="#08090a", fg=TEXT1, insertbackground=TEXT1,
        relief="flat", bd=0, state="disabled"
    )
    log_box.pack(fill="both", expand=True)
    log_box.tag_config("ok",  foreground=TEXT1)
    log_box.tag_config("err", foreground=RED)
    log_box.tag_config("dim", foreground=TEXT2)

    # Working directory footer
    tk.Label(body, text=f"Working directory: {BASE_DIR}",
             font=("Segoe UI", 8), bg=BG, fg=TEXT2).pack(pady=(8, 0))

    def _write_log(line: str):
        log_box.config(state="normal")
        is_err = "[stderr]" in line or "error" in line.lower() or "failed" in line.lower()
        is_ok  = ("[ok]" in line or "done" in line.lower() or
                  "complete" in line.lower() or "cleaned" in line.lower())
        tag = "err" if is_err else "ok" if is_ok else "dim"
        log_box.insert("end", line + "\n", tag)
        log_box.see("end")
        log_box.config(state="disabled")

    def _append_log(line: str):
        if line == "__DONE__":
            root.after(0, _pipeline_finished)
        else:
            root.after(0, lambda l=line: _write_log(l))

    def _trigger_run():
        if run_state["running"]:
            return
        log_box.config(state="normal")
        log_box.delete("1.0", "end")
        log_box.config(state="disabled")
        pipe_lbl.config(text="running...", fg=ACCENT)
        run_btn.config(state="disabled", bg="#6b0a0f")
        threading.Thread(target=_run_pipeline, daemon=True).start()

    def _pipeline_finished():
        ok = not any(
            ("[stderr]" in l or "error" in l.lower() or "failed" in l.lower())
            for l in run_state["log"]
        )
        pipe_lbl.config(text="completed" if ok else "finished with errors",
                        fg=ACCENT if ok else RED)
        run_btn.config(state="normal", bg=ACCENT2)

    _log_callback = _append_log
    root.protocol("WM_DELETE_WINDOW", lambda: (root.destroy(), os._exit(0)))
    return root


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    threading.Thread(target=_start_flask, daemon=True).start()
    build_gui().mainloop()