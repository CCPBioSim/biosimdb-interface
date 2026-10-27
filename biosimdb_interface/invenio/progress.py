#!/usr/bin/env python
"""Track upload progress and stream file data in cancellable chunks.

Provides a thread-safe progress counter and file readers for single-request
and multipart uploads. Readers check the cancellation callback before reading.
"""

import threading
import time

from biosimdb_interface.core.cancellation import UploadCancelled


class Progress:
    """Thread-safe byte counter that logs progress at most every `every` seconds."""

    def __init__(self, size, every=30):
        """Initialize a progress counter.

        Args:
            size (int): Total upload size in bytes.
            every (int): Minimum seconds between progress log updates.
        """
        self.size = size
        self.sent = 0
        self.start = time.monotonic()
        self.every = every
        self.last_log = self.start
        self.done_at = None
        self.lock = threading.Lock()

    def add(self, n):
        """Record that ``n`` bytes have been sent."""
        with self.lock:
            self.sent += n
            now = time.monotonic()
            if self.sent >= self.size and self.done_at is None:
                self.done_at = now
            if now - self.last_log >= self.every or self.sent >= self.size:
                self.last_log = now

    def status(self):
        """Return a human-readable summary of bytes, percentage, elapsed time, and rate.

        Returns:
            str: Formatted upload progress.
        """
        elapsed = time.monotonic() - self.start
        rate = self.sent / elapsed / 1e6 if elapsed else 0
        pct = 100 * self.sent / self.size if self.size else 100
        return (
            f"{self.sent / 1e9:.2f}/{self.size / 1e9:.2f} GB ({pct:.1f}%) "
            f"in {elapsed / 60:.1f} min, {rate:.1f} MB/s"
        )

    def wait_time(self):
        """Return elapsed time since upload completion, formatted in seconds.

        Returns:
            str: Elapsed seconds as a string, such as ``"5s"``.
        """
        return f"{time.monotonic() - (self.done_at or time.monotonic()):.0f}s"


class ProgressReader:
    """File wrapper for a single streamed PUT that feeds a Progress counter."""

    def __init__(self, path, progress, cancelled=lambda: False):
        """Open a file reader that updates progress as bytes are read.

        Args:
            path (str | Path): File to stream.
            progress (Progress): Counter to update.
            cancelled (Callable[[], bool]): Callback that returns whether to cancel.
        """
        self.fp = open(path, "rb")
        self.progress = progress
        self.cancelled = cancelled

    def __len__(self):
        """Return the total upload size in bytes."""
        return self.progress.size

    def read(self, n=-1):
        """Read up to ``n`` bytes and add the count to the progress tracker.

        Raises:
            UploadCancelled: If cancellation is requested before the read.
        """
        if self.cancelled():
            raise UploadCancelled
        chunk = self.fp.read(n)
        if chunk:
            self.progress.add(len(chunk))
        return chunk


class PartReader:
    """Stream a bounded byte range from a file for one multipart upload.

    Reads start at ``offset`` and stop after ``length`` bytes. Each read is
    limited by the requested size, the configured chunk size, and the
    remaining bytes in the part. The cancellation callback is checked before
    each read.

    Args:
        path (str | Path): File to read from.
        offset (int): Starting byte offset of this part.
        length (int): Maximum number of bytes to read.
        cancelled (Callable[[], bool]): Callback that indicates cancellation.
        chunk (int): Maximum bytes returned by one read; defaults to 1 MiB.
    """

    def __init__(self, path, offset, length, cancelled, chunk=1024 * 1024):
        """Open the file and seek to the start of this part."""
        self.fp = open(path, "rb")
        self.fp.seek(offset)
        self.left, self.length = length, length
        self.cancelled, self.chunk = cancelled, chunk

    def __len__(self):
        """Return the total length of this part in bytes."""
        return self.length

    def read(self, n=-1):
        """Read up to ``n`` bytes from this part.

        The read is capped by the configured chunk size and remaining part
        length. Returns ``b""`` when the part is exhausted.

        Raises:
            UploadCancelled: If cancellation is requested before reading.
        """
        if self.cancelled():
            raise UploadCancelled
        n = self.chunk if n is None or n < 0 else min(n, self.chunk)
        data = self.fp.read(min(n, self.left))
        self.left -= len(data)
        return data

    def close(self):
        """Close the underlying file handle."""
        self.fp.close()
