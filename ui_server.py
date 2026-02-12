"""
ui_server.py
============
Flask + SSE UI server.
Imported by main.py — does NOT run its own file watcher.
main.py calls broadcast() after every fs event, and run() to start Flask.
"""

import json
import time
import queue
import threading
from pathlib import Path
from flask import Flask, Response, send_from_directory

BASE_DIR  = Path(__file__).parent
app       = Flask(__name__, static_folder=str(BASE_DIR / "static"))

_clients: list[queue.Queue] = []
_lock    = threading.Lock()
_root    = None   # set by run()


# ── Tree builder (reads real filesystem) ─────────────────────────────────────
def _node_type(path: Path, depth: int) -> str:
    if depth == 0:       return "root"
    if path.is_dir():    return "domain" if depth == 1 else "folder"
    return "file"


def _file_ext(name: str) -> str:
    return Path(name).suffix.lstrip(".").lower() or "file"


def build_tree(root: Path, depth=0, max_depth=6) -> dict:
    node = {
        "id":       str(root).replace("\\", "/"),
        "name":     root.name or str(root),
        "type":     _node_type(root, depth),
        "ext":      _file_ext(root.name) if root.is_file() else None,
        "path":     str(root),
        "children": [],
        "modified": root.stat().st_mtime if root.exists() else 0,
    }
    if root.is_dir() and depth < max_depth:
        try:
            # folders first, then files, both alphabetical
            entries = sorted(root.iterdir(),
                             key=lambda p: (p.is_file(), p.name.lower()))
            node["children"] = [
                build_tree(child, depth + 1, max_depth)
                for child in entries
                if not child.name.startswith(".")
                and child.name not in {"__pycache__", ".git", "node_modules", ".venv", "venv"}
            ]
        except PermissionError:
            pass
    return node


# ── Push to all SSE clients ───────────────────────────────────────────────────
def broadcast(event_type: str, root_dir=None):
    root = Path(root_dir) if root_dir else _root
    if not root:
        return
    tree = build_tree(root)
    data = json.dumps({"event": event_type, "tree": tree, "ts": time.time()})
    with _lock:
        dead = []
        for q in _clients:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _clients.remove(q)


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(str(BASE_DIR / "static"), "index.html")


@app.route("/api/tree")
def get_tree():
    tree = build_tree(_root) if _root else {}
    return {"tree": tree, "root": str(_root)}


@app.route("/api/stream")
def stream():
    q: queue.Queue = queue.Queue(maxsize=100)
    with _lock:
        _clients.append(q)

    def generate():
        # Immediate snapshot on connect
        if _root:
            tree     = build_tree(_root)
            snapshot = json.dumps({"event": "snapshot", "tree": tree, "ts": time.time()})
            yield f"data: {snapshot}\n\n"
        while True:
            try:
                data = q.get(timeout=25)
                yield f"data: {data}\n\n"
            except queue.Empty:
                yield ": heartbeat\n\n"

    def cleanup(r):
        with _lock:
            if q in _clients:
                _clients.remove(q)
        return r

    resp = Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
    resp.call_on_close(lambda: cleanup(resp))
    return resp


# ── Entry point called by main.py ────────────────────────────────────────────
def run(root_dir, port=5000):
    global _root
    _root = Path(root_dir)
    print(f"[SEFS UI] http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False, use_reloader=False)