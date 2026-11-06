#!/usr/bin/env python
"""File-backed submission progress, shared between requests and upload threads.

Progress is stored in the workflow's temporary directory (like the
cancellation flag) so a polling request can read what a blocking
``do_submit`` request is doing, even across worker processes.
"""

import json
import os
import threading
import time

PROGRESS_FILENAME = "progress.json"


class ProgressReporter:
    """Write the ordered step list and the current step's progress."""

    def __init__(self, tmpdir, min_interval=0.5):
        """Create a reporter writing to ``tmpdir``.

        Args:
            tmpdir (str): Workflow temporary directory.
            min_interval (float): Minimum seconds between writes for updates
                within the same step.
        """
        self.path = os.path.join(tmpdir, PROGRESS_FILENAME)
        self.min_interval = min_interval
        self.state = {"steps": [], "current": None, "pct": None, "detail": ""}
        self.lock = threading.Lock()
        self.last_write = 0.0

    def set_steps(self, steps):
        """Set the ordered steps as ``[{"id": ..., "label": ...}, ...]``."""
        with self.lock:
            self.state["steps"] = steps
            self._write()

    def update(self, step, pct=None, detail=""):
        """Record progress for ``step``; ``pct`` is 0-1 or None if unknown."""
        with self.lock:
            changed = step != self.state["current"]
            self.state.update(current=step, pct=pct, detail=detail)
            if (
                changed
                or pct == 1
                or time.monotonic() - self.last_write >= self.min_interval
            ):
                self._write()

    def _write(self):
        tmp = f"{self.path}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump(self.state, f)
        os.replace(tmp, self.path)  # atomic: readers never see partial JSON
        self.last_write = time.monotonic()


def read_progress(tmpdir):
    """Return the saved progress state, or an empty state if none exists."""
    try:
        with open(os.path.join(tmpdir, PROGRESS_FILENAME)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"steps": [], "current": None, "pct": None, "detail": ""}
