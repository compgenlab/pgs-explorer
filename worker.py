"""
Background task worker for pgs-explorer.

Polls the task database for pending tasks and executes them in a
separate process from the web server, keeping the web server responsive.

Usage:
    python worker.py

Configuration (env vars):
    WORKER_POLL_INTERVAL  Seconds between polls when idle (default: 5)
"""

import os
import signal
import time
import traceback

from database import db
from apps.distribution.service import process_distribution
from apps.subcohorts.service import process_subcohort_plot
from apps.multivariate.heatmap import process_heatmap
from apps.multivariate.umap import process_umap
from apps.multivariate.svd import process_svd
from apps.multivariate.pca import process_pca
from apps.multivariate.tsne import process_tsne

TASK_HANDLERS = {
    "distribution":   process_distribution,
    "subcohort_plot": process_subcohort_plot,
    "heatmap":        process_heatmap,
    "umap":           process_umap,
    "svd":            process_svd,
    "pca":            process_pca,
    "tsne":           process_tsne,
}

POLL_INTERVAL = int(os.environ.get("WORKER_POLL_INTERVAL", "5"))

running = True


def handle_signal(sig, frame):
    global running
    print(f"Received signal {sig}, shutting down after current task...", flush=True)
    running = False


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def process_next_task() -> bool:
    """Claim and execute the oldest pending task. Returns True if a task was processed."""
    tasks = db.active_db.tasks.get_tasks_by_status("pending")
    if not tasks:
        return False

    # Oldest first
    task = sorted(tasks, key=lambda t: t["created_at"])[0]
    task_id = task["task_id"]
    task_type = task["task_type"]
    request_data = task["request_data"]

    handler = TASK_HANDLERS.get(task_type)
    if handler is None:
        print(f"Unknown task type '{task_type}' for task {task_id}, marking failed", flush=True)
        db.active_db.tasks.update_task_status(task_id, "failed", error=f"Unknown task type: {task_type}")
        return True

    print(f"Starting task {task_id} (type={task_type})", flush=True)
    db.active_db.tasks.update_task_status(task_id, "processing")

    try:
        result_path = handler(request_data)
        db.active_db.tasks.update_task_status(task_id, "completed", result_path=result_path)
        print(f"Completed task {task_id}: {result_path}", flush=True)
    except Exception:
        error_msg = traceback.format_exc()
        db.active_db.tasks.update_task_status(task_id, "failed", error=error_msg)
        print(f"Failed task {task_id}:\n{error_msg}", flush=True)

    return True


def main():
    print(f"Worker started. Poll interval: {POLL_INTERVAL}s", flush=True)
    print(f"Registered handlers: {sorted(TASK_HANDLERS.keys())}", flush=True)

    while running:
        try:
            processed = process_next_task()
            if not processed:
                time.sleep(POLL_INTERVAL)
        except Exception:
            print(f"Worker loop error:\n{traceback.format_exc()}", flush=True)
            time.sleep(POLL_INTERVAL)

    print("Worker stopped.", flush=True)


if __name__ == "__main__":
    main()
