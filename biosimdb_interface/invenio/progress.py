"""Upload files to an InvenioRDM instance draft record.

By default the file is sent as a multipart (chunked) upload: each part is PUT
straight to object storage via a pre-signed URL, so no single request stays
open for the whole transfer.
If multipart fails for a smaller file, use one PUT through the repository.

Adapted from a script provided by Andrew Harper, STFC.
"""

import threading
import time

from biosimdb_interface.core.cancellation import UploadCancelled


class Progress:
    """Thread-safe byte counter that logs progress at most every `every` seconds."""

    def __init__(self, size, every=30):
        self.size = size
        self.sent = 0
        self.start = time.monotonic()
        self.every = every
        self.last_log = self.start
        self.done_at = None
        self.lock = threading.Lock()

    def add(self, n):
        with self.lock:
            self.sent += n
            now = time.monotonic()
            if self.sent >= self.size and self.done_at is None:
                self.done_at = now
            if now - self.last_log >= self.every or self.sent >= self.size:
                self.last_log = now

    def status(self):
        elapsed = time.monotonic() - self.start
        rate = self.sent / elapsed / 1e6 if elapsed else 0
        pct = 100 * self.sent / self.size if self.size else 100
        return (
            f"{self.sent / 1e9:.2f}/{self.size / 1e9:.2f} GB ({pct:.1f}%) "
            f"in {elapsed / 60:.1f} min, {rate:.1f} MB/s"
        )

    def wait_time(self):
        return f"{time.monotonic() - (self.done_at or time.monotonic()):.0f}s"


class ProgressReader:
    """File wrapper for a single streamed PUT that feeds a Progress counter."""

    def __init__(self, path, progress, cancelled=lambda: False):
        self.fp = open(path, "rb")
        self.progress = progress
        self.cancelled = cancelled

    def __len__(self):
        return self.progress.size

    def read(self, n=-1):
        if self.cancelled():
            raise UploadCancelled
        chunk = self.fp.read(n)
        if chunk:
            self.progress.add(len(chunk))
        return chunk


class PartReader:
    """Streams one part from disk, aborting promptly if cancelled."""

    def __init__(self, path, offset, length, cancelled, chunk=1024 * 1024):
        self.fp = open(path, "rb")
        self.fp.seek(offset)
        self.left, self.length = length, length
        self.cancelled, self.chunk = cancelled, chunk

    def __len__(self):
        return self.length

    def read(self, n=-1):
        if self.cancelled():
            raise UploadCancelled
        n = self.chunk if n is None or n < 0 else min(n, self.chunk)
        data = self.fp.read(min(n, self.left))
        self.left -= len(data)
        return data

    def close(self):
        self.fp.close()
