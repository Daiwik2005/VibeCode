# """
# SEFS – main.py
# ==============
# Orchestrator: runs file watcher, content processor, semantic clustering,
# and the live UI server all together.

# Usage:  python main.py
# UI:     http://localhost:5000
# """

# import os
# import sys
# import time
# import threading
# from queue import Queue
# from pathlib import Path

# # ── your existing modules ─────────────────────────────────────────────────────
# from file_watcher        import start_watcher
# from content_processor   import process_file, remove_file
# from semantic_intelligence import reorganize_files

# # ── UI server (Flask + SSE) ───────────────────────────────────────────────────
# import ui_server   # imported so it registers Flask routes and exposes broadcast()

# # ─────────────────────────────────────────────────────────────────────────────
# ROOT_DIR = Path(r"C:\Users\Daiwi\OneDrive\Documents\bands\SEFS_-BANDS-\root")   # ← your directory
# # ─────────────────────────────────────────────────────────────────────────────

# event_queue    = Queue()
# recluster_timer = None
# lock           = threading.Lock()


# def schedule_recluster():
#     """Debounce semantic reclustering so rapid file changes → one recluster."""
#     global recluster_timer
#     with lock:
#         if recluster_timer:
#             recluster_timer.cancel()
#         def _do():
#             reorganize_files(ROOT_DIR)
#             ui_server.broadcast("reorganized", ROOT_DIR)   # push fresh tree to browser
#         recluster_timer = threading.Timer(3.0, _do)
#         recluster_timer.start()


# def event_processor():
#     """Consume fs events, run per-file processing, then schedule recluster."""
#     while True:
#         event, src, dst = event_queue.get()
#         try:
#             if event == "deleted":
#                 remove_file(src, ROOT_DIR)
#                 ui_server.broadcast("deleted", ROOT_DIR)
#             elif event == "moved":
#                 remove_file(src, ROOT_DIR)
#                 process_file(dst, ROOT_DIR)
#                 ui_server.broadcast("moved", ROOT_DIR)
#             else:  # created / modified
#                 process_file(src, ROOT_DIR)
#                 ui_server.broadcast(event, ROOT_DIR)
#         except Exception as e:
#             print(f"[SEFS] Error processing {event} on {src}: {e}")
#         finally:
#             schedule_recluster()


# def main():
#     print(f"[SEFS] Starting – watching {ROOT_DIR}")

#     # 1. Initial scan
#     for root, _, files in os.walk(ROOT_DIR):
#         for f in files:
#             try:
#                 process_file(Path(root) / f, ROOT_DIR)
#             except Exception as e:
#                 print(f"[SEFS] Skipping {f}: {e}")

#     schedule_recluster()

#     # 2. Background threads
#     threading.Thread(target=event_processor,                         daemon=True).start()
#     threading.Thread(target=start_watcher, args=(ROOT_DIR, event_queue), daemon=True).start()

#     print("[SEFS] Watcher active – open http://localhost:5000")

#     # 3. Flask UI server (blocking – must be last)
#     ui_server.run(ROOT_DIR, port=5000)


# if __name__ == "__main__":
#     main()



"""
SEFS – main.py
==============
Input folder  → ROOT_IN
Structured out → ROOT_OUT
UI shows ROOT_OUT

Usage:  python main.py
UI:     http://localhost:5000
"""
import os
import threading
import shutil
from queue import Queue
from pathlib import Path

# ── modules ───────────────────────────────────────────────
from file_watcher import start_watcher
from content_processor import process_file, remove_file
from semantic_intelligence import reorganize_files
import ui_server

# ──────────────────────────────────────────────────────────
ROOT_IN  = Path(r"C:\Users\Daiwi\OneDrive\Documents\bands\SEFS_-BANDS-\root1")
ROOT_OUT = Path(r"C:\Users\Daiwi\OneDrive\Documents\bands\SEFS_-BANDS-\root2")
# ──────────────────────────────────────────────────────────

event_queue = Queue()
recluster_timer = None
lock = threading.Lock()


# ==========================================================
# Debounced recluster (longer delay to avoid race)
# ==========================================================
def schedule_recluster():
    global recluster_timer

    with lock:
        if recluster_timer:
            recluster_timer.cancel()

        def _do():
            print("[Semantic] Reclustering now...")
            reorganize_files(ROOT_OUT)
            ui_server.broadcast("reorganized", ROOT_OUT)

        # longer delay → let embeddings + pdf parsing finish
        recluster_timer = threading.Timer(8.0, _do)
        recluster_timer.start()


# ==========================================================
# Move file to ROOT_OUT staging first
# ==========================================================
def move_to_output(src_path):
    src = Path(src_path)
    if not src.exists():
        return None

    dst = ROOT_OUT / src.name

    try:
        shutil.move(str(src), str(dst))
        print(f"[SEFS] Staged → {dst}")
        return dst
    except Exception as e:
        print("[Move Error]", e)
        return None


# ==========================================================
# Event Processor
# ==========================================================
def event_processor():
    while True:
        event, src, dst = event_queue.get()

        try:
            if event == "deleted":
                # ignore — we already moved it
                continue

            elif event == "moved":
                new_path = move_to_output(dst)
                if new_path:
                    process_file(new_path, ROOT_OUT)

            else:  # created / modified
                new_path = move_to_output(src)
                if new_path:
                    process_file(new_path, ROOT_OUT)

        except Exception as e:
            print(f"[SEFS] Error {event} {src}: {e}")

        finally:
            schedule_recluster()


# ==========================================================
# Main
# ==========================================================
def main():

    ROOT_OUT.mkdir(parents=True, exist_ok=True)

    print(f"[SEFS] Watching INPUT  : {ROOT_IN}")
    print(f"[SEFS] Writing OUTPUT : {ROOT_OUT}")

    # -------- Initial scan of ROOT_IN ----------
    moved_any = False

    for root, _, files in os.walk(ROOT_IN):
        for f in files:
            try:
                src = Path(root) / f
                dst = ROOT_OUT / src.name
                shutil.move(str(src), str(dst))
                print(f"[SEFS] Initial stage → {dst}")
                process_file(dst, ROOT_OUT)
                moved_any = True
            except Exception as e:
                print(f"[SEFS] Skip {f}: {e}")

    # -------- Force first clustering if files exist ----------
    if moved_any:
        print("[SEFS] Initial scan complete — clustering")
        reorganize_files(ROOT_OUT)

    # -------- Threads ----------
    threading.Thread(target=event_processor, daemon=True).start()

    threading.Thread(
        target=start_watcher,
        args=(ROOT_IN, event_queue),
        daemon=True
    ).start()

    print("[SEFS] Drop files into ROOT_IN")
    print("[SEFS UI] http://localhost:5000")

    # -------- UI shows ROOT_OUT ----------
    ui_server.run(ROOT_OUT, port=5000)


if __name__ == "__main__":
    main()

