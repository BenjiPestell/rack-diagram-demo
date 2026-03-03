import subprocess
import os
import sys
import threading
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

OUTPUT_DIR = "output"
PNG_DIR = "pngs"

# --- Serve the frontend ---

@app.route("/")
def index():
    return send_from_directory(".", "rack_designer.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(".", filename)


# --- YAML management ---

@app.route("/yaml", methods=["GET"])
def get_yaml():
    """Return the current YAML file contents."""
    try:
        with open("system.yaml", "r") as f:
            return f.read(), 200, {"Content-Type": "text/plain"}
    except FileNotFoundError:
        return "", 200, {"Content-Type": "text/plain"}

@app.route("/yaml", methods=["POST"])
def save_yaml():
    """Save YAML sent as plain text from the editor."""
    yaml_text = request.get_data(as_text=True)
    with open("system.yaml", "w") as f:
        f.write(yaml_text)
    return jsonify({"status": "saved"})


# --- Run pipeline ---

# Track run state so the UI can poll for progress
run_state = {"running": False, "log": [], "files": []}
run_lock = threading.Lock()

def _run_pipeline():
    """Executes the full pipeline in a background thread."""
    with run_lock:
        run_state["running"] = True
        run_state["log"] = []
        run_state["files"] = []

    def log(msg):
        print(msg)
        run_state["log"].append(msg)

    try:
        os.makedirs(PNG_DIR, exist_ok=True)

        # Step 1: run src/main.py
        log("Running src/main.py...")
        result = subprocess.run(
            [sys.executable, "src/main.py"],
            capture_output=True, text=True
        )
        if result.stdout:
            for line in result.stdout.splitlines():
                log(line)
        if result.stderr:
            for line in result.stderr.splitlines():
                log(f"[stderr] {line}")

        if result.returncode != 0:
            log("src/main.py failed. Aborting.")
            return

        log("src/main.py completed.")

        # Step 2: convert .dot files to PNGs
        for filename in os.listdir(OUTPUT_DIR):
            if filename.lower().endswith(".dot"):
                dot_path = os.path.join(OUTPUT_DIR, filename)
                name_without_ext = os.path.splitext(filename)[0]
                png_path = os.path.join(PNG_DIR, f"{name_without_ext}.png")

                cmd = ["dot", "-Tpng:cairo", "-Gdpi=300", dot_path, "-o", png_path]
                log(f"Converting {filename} → {png_path}")

                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    log(f"Failed to convert {filename}")
                    if result.stderr:
                        log(result.stderr)

        log("All files processed.")

        # Collect output files
        files = {"output": [], "pngs": []}
        if os.path.isdir(OUTPUT_DIR):
            files["output"] = os.listdir(OUTPUT_DIR)
        if os.path.isdir(PNG_DIR):
            files["pngs"] = os.listdir(PNG_DIR)
        run_state["files"] = files

    except Exception as e:
        log(f"Unexpected error: {e}")
    finally:
        run_state["running"] = False


@app.route("/run", methods=["POST"])
def run():
    """Kick off the pipeline. Returns immediately; poll /status for progress."""
    if run_state["running"]:
        return jsonify({"status": "already_running"}), 409
    t = threading.Thread(target=_run_pipeline, daemon=True)
    t.start()
    return jsonify({"status": "started"})

@app.route("/status", methods=["GET"])
def status():
    """Return current run state: running flag, log lines, and output file lists."""
    return jsonify({
        "running": run_state["running"],
        "log": run_state["log"],
        "files": run_state["files"],
    })


# --- Serve output files ---

@app.route("/output/<path:filename>")
def get_output(filename):
    mime_map = {
        ".html": "text/html",
        ".htm":  "text/html",
        ".csv":  "text/plain",
        ".txt":  "text/plain",
        ".json": "application/json",
        ".pdf":  "application/pdf",
    }
    ext = os.path.splitext(filename)[1].lower()
    mimetype = mime_map.get(ext)
    return send_from_directory(OUTPUT_DIR, filename, mimetype=mimetype)

@app.route("/pngs/<path:filename>")
def get_png(filename):
    return send_from_directory(PNG_DIR, filename)


# --- Entry point ---

if __name__ == "__main__":
    print("Starting server at http://localhost:5000")
    app.run(debug=True, port=5000, use_reloader=False)