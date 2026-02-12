"""
SEFS – main.py
==============
Orchestrator: runs file watcher, content processor, semantic clustering,
and the live UI server all together.

Usage:  python main.py
UI:     http://localhost:5000
"""

import os
import sys
import time
import threading
from queue import Queue
from pathlib import Path

# ── your existing modules ─────────────────────────────────────────────────────
from file_watcher        import start_watcher
from content_processor   import process_file, remove_file
from semantic_intelligence import reorganize_files

# ── UI server (Flask + SSE) ───────────────────────────────────────────────────
import ui_server   # imported so it registers Flask routes and exposes broadcast()

# ─────────────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(r"C:\Bhanu\vibecoding\SEFS_Root")   # ← your directory
# ─────────────────────────────────────────────────────────────────────────────

event_queue    = Queue()
recluster_timer = None
lock           = threading.Lock()


def schedule_recluster():
    """Debounce semantic reclustering so rapid file changes → one recluster."""
    global recluster_timer
    with lock:
        if recluster_timer:
            recluster_timer.cancel()
        def _do():
            reorganize_files(ROOT_DIR)
            ui_server.broadcast("reorganized", ROOT_DIR)   # push fresh tree to browser
        recluster_timer = threading.Timer(3.0, _do)
        recluster_timer.start()


def event_processor():
    """Consume fs events, run per-file processing, then schedule recluster."""
    while True:
        event, src, dst = event_queue.get()
        try:
            if event == "deleted":
                remove_file(src, ROOT_DIR)
                ui_server.broadcast("deleted", ROOT_DIR)
            elif event == "moved":
                remove_file(src, ROOT_DIR)
                process_file(dst, ROOT_DIR)
                ui_server.broadcast("moved", ROOT_DIR)
            else:  # created / modified
                process_file(src, ROOT_DIR)
                ui_server.broadcast(event, ROOT_DIR)
        except Exception as e:
            print(f"[SEFS] Error processing {event} on {src}: {e}")
        finally:
            schedule_recluster()


def main():
    print(f"[SEFS] Starting – watching {ROOT_DIR}")

    # 1. Initial scan
    for root, _, files in os.walk(ROOT_DIR):
        for f in files:
            try:
                process_file(Path(root) / f, ROOT_DIR)
            except Exception as e:
                print(f"[SEFS] Skipping {f}: {e}")

    schedule_recluster()

    # 2. Background threads
    threading.Thread(target=event_processor,                         daemon=True).start()
    threading.Thread(target=start_watcher, args=(ROOT_DIR, event_queue), daemon=True).start()

    print("[SEFS] Watcher active – open http://localhost:5000")

    # 3. Flask UI server (blocking – must be last)
    ui_server.run(ROOT_DIR, port=5000)


if __name__ == "__main__":
    main()