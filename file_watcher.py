from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time

class SEFSHandler(FileSystemEventHandler):
    def __init__(self, queue):
        self.queue = queue

    def on_any_event(self, event):
        if event.is_directory:
            return

        if event.event_type == "deleted":
            self.queue.put(("deleted", event.src_path, None))
        elif event.event_type == "moved":
            self.queue.put(("moved", event.src_path, event.dest_path))
        else:
            self.queue.put(("modified", event.src_path, None))

def start_watcher(root, queue):
    observer = Observer()
    observer.schedule(SEFSHandler(queue), str(root), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
