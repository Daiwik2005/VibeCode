"""
SEFS – Semantic File System Server
====================================
Set ROOT_DIR below, then run:  python server.py
Open: http://localhost:5000
"""

import os
import sys
import json
import time
import queue
import threading
from pathlib import Path
from flask import Flask, Response, send_from_directory
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ── CONFIG ────────────────────────────────────────────────────────────────────
ROOT_DIR = "C:\\Users\\Daiwi\\OneDrive\\Documents\\bands\\SEFS_-BANDS-\\rootEFS_Root"          # ← CHANGE THIS to your directory
PORT     = 5000
# ─────────────────────────────────────────────────────────────────────────────

# Create demo dir if it doesn't exist
Path(ROOT_DIR).mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder="static")
_clients: list[queue.Queue] = []
_clients_lock = threading.Lock()


# ── Tree builder ──────────────────────────────────────────────────────────────
def _node_type(path: Path, depth: int) -> str:
    if depth == 0:  return "root"
    if path.is_dir():
        return "domain" if depth == 1 else "cluster"
    return "file"


def build_tree(root: Path, depth=0, max_depth=4) -> dict:
    """Recursively build a JSON-serialisable tree from the filesystem."""
    node = {
        "id":       str(root.relative_to(Path(ROOT_DIR).parent)),
        "name":     root.name or str(root),
        "type":     _node_type(root, depth),
        "path":     str(root),
        "children": [],
        "modified": root.stat().st_mtime if root.exists() else 0,
    }
    if root.is_dir() and depth < max_depth:
        try:
            entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            node["children"] = [
                build_tree(child, depth + 1, max_depth)
                for child in entries
                if not child.name.startswith(".")
            ]
        except PermissionError:
            pass
    return node


def broadcast(event_type: str):
    """Push updated tree to all SSE clients."""
    tree = build_tree(Path(ROOT_DIR))
    data = json.dumps({"event": event_type, "tree": tree, "ts": time.time()})
    with _clients_lock:
        dead = []
        for q in _clients:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _clients.remove(q)


# ── Watchdog handler ──────────────────────────────────────────────────────────
class FSHandler(FileSystemEventHandler):
    def __init__(self):
        self._debounce_timer = None
        self._lock = threading.Lock()

    def _debounced_broadcast(self, event_type):
        """Coalesce rapid bursts (e.g. copying many files) into one update."""
        with self._lock:
            if self._debounce_timer:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(
                0.25, lambda: broadcast(event_type)
            )
            self._debounce_timer.start()

    def on_created(self, event):  self._debounced_broadcast("created")
    def on_deleted(self, event):  self._debounced_broadcast("deleted")
    def on_modified(self, event): self._debounced_broadcast("modified")
    def on_moved(self, event):    self._debounced_broadcast("moved")


# ── Flask routes ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/tree")
def get_tree():
    """Initial tree snapshot on connect."""
    tree = build_tree(Path(ROOT_DIR))
    return {"tree": tree, "root": str(ROOT_DIR)}


@app.route("/api/stream")
def stream():
    """SSE endpoint – stays open and pushes updates."""
    q: queue.Queue = queue.Queue(maxsize=50)
    with _clients_lock:
        _clients.append(q)

    def generate():
        # Send current snapshot immediately on connect
        tree = build_tree(Path(ROOT_DIR))
        snapshot = json.dumps({"event": "snapshot", "tree": tree, "ts": time.time()})
        yield f"data: {snapshot}\n\n"

        while True:
            try:
                data = q.get(timeout=25)
                yield f"data: {data}\n\n"
            except queue.Empty:
                yield ": heartbeat\n\n"   # keep connection alive

    def cleanup(resp):
        with _clients_lock:
            if q in _clients:
                _clients.remove(q)
        return resp

    resp = Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})
    resp.call_on_close(lambda: cleanup(resp))
    return resp


# ── Start watcher & server ────────────────────────────────────────────────────
if __name__ == "__main__":
    handler  = FSHandler()
    observer = Observer()
    observer.schedule(handler, ROOT_DIR, recursive=True)
    observer.start()
    print(f"👁  Watching: {ROOT_DIR}")
    print(f"🌐  Open:     http://localhost:{PORT}")

    try:
        app.run(host="0.0.0.0", port=PORT, threaded=True, debug=False)
    finally:
        observer.stop()
        observer.join()