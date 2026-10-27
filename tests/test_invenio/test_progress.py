import pytest

from biosimdb_interface.core.cancellation import UploadCancelled
from biosimdb_interface.invenio import progress


def test_progress_wait_time_uses_completion_time(monkeypatch):
    """Reports elapsed time since all bytes were sent."""
    tracker = progress.Progress(size=10)
    tracker.done_at = 100.0
    monkeypatch.setattr(progress.time, "monotonic", lambda: 105.0)

    assert tracker.wait_time() == "5s"


def test_progress_reader_tracks_bytes_and_reports_length(tmp_path):
    """Reads file data while updating progress."""
    path = tmp_path / "data.bin"
    path.write_bytes(b"abcdef")
    tracker = progress.Progress(size=6)
    reader = progress.ProgressReader(path, tracker)

    try:
        assert len(reader) == 6
        assert reader.read(2) == b"ab"
        assert tracker.sent == 2
        assert reader.read() == b"cdef"
        assert tracker.sent == 6
    finally:
        reader.fp.close()


def test_progress_reader_raises_when_cancelled(tmp_path):
    """Stops reading when cancellation is requested."""
    path = tmp_path / "data.bin"
    path.write_bytes(b"data")
    reader = progress.ProgressReader(
        path, progress.Progress(size=4), cancelled=lambda: True
    )

    try:
        with pytest.raises(UploadCancelled):
            reader.read()
    finally:
        reader.fp.close()


def test_part_reader_reads_only_its_byte_range(tmp_path):
    """Reads from the requested offset and never exceeds its part length."""
    path = tmp_path / "data.bin"
    path.write_bytes(b"abcdefgh")
    reader = progress.PartReader(path, offset=2, length=3, cancelled=lambda: False)

    try:
        assert len(reader) == 3
        assert reader.read() == b"cde"
        assert reader.read() == b""
    finally:
        reader.close()


def test_part_reader_raises_when_cancelled(tmp_path):
    """Stops reading a part when cancellation is requested."""
    path = tmp_path / "data.bin"
    path.write_bytes(b"data")
    reader = progress.PartReader(path, offset=0, length=4, cancelled=lambda: True)

    try:
        with pytest.raises(UploadCancelled):
            reader.read()
    finally:
        reader.close()
