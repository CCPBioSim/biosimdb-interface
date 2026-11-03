import io
import os

import pytest

from biosimdb_interface.uploads.chunked import (
    ChunkedUpload,
    UploadError,
    resolve_uploaded_file,
)

DATA = bytes(range(256)) * 10  # 2560 bytes -> 3 chunks of 1000


def start(tmp_path, data=DATA, **kw):
    return ChunkedUpload.start(
        str(tmp_path), "traj.xtc", len(data), max_bytes=10**6, chunk_size=1000, **kw
    )


def send(upload, data, index):
    chunk = data[index * 1000 : (index + 1) * 1000]
    upload.write_chunk(index, io.BytesIO(chunk), len(chunk))


def test_out_of_order_upload_assembles_in_place(tmp_path):
    upload = start(tmp_path)
    for i in (2, 0, 1):
        send(upload, DATA, i)

    path = upload.complete()

    assert path == str(tmp_path / "traj.xtc")
    assert open(path, "rb").read() == DATA
    assert not (tmp_path / ".staging" / upload.upload_id).exists()


def test_resume_reports_received_chunks(tmp_path):
    send(start(tmp_path), DATA, 1)

    resumed = start(tmp_path).describe()

    assert resumed["received"] == [1]
    assert resumed["total_chunks"] == 3


def test_complete_requires_all_chunks(tmp_path):
    upload = start(tmp_path)
    send(upload, DATA, 0)
    with pytest.raises(UploadError) as exc:
        upload.complete()
    assert exc.value.status_code == 409


def test_wrong_size_chunk_rejected_and_not_marked(tmp_path):
    upload = start(tmp_path)
    with pytest.raises(UploadError):
        upload.write_chunk(0, io.BytesIO(b"x" * 10), 10)
    assert upload.received() == []


def test_truncated_stream_not_marked_received(tmp_path):
    upload = start(tmp_path)
    with pytest.raises(UploadError):
        upload.write_chunk(0, io.BytesIO(b"x" * 10), 1000)
    assert upload.received() == []


def test_chunk_index_out_of_range(tmp_path):
    with pytest.raises(UploadError):
        start(tmp_path).write_chunk(3, io.BytesIO(b""), 0)


def test_checksum_verified(tmp_path):
    import hashlib

    upload = start(tmp_path)
    for i in range(3):
        send(upload, DATA, i)
    with pytest.raises(UploadError) as exc:
        upload.complete(sha256="0" * 64)
    assert exc.value.status_code == 422
    assert upload.complete(hashlib.sha256(DATA).hexdigest())


@pytest.mark.parametrize(
    "name,size,status",
    [("", 10, 400), ("a.xtc", 0, 400), ("a.xtc", True, 400), ("a.xtc", 10**7, 413)],
)
def test_start_validation(tmp_path, name, size, status):
    with pytest.raises(UploadError) as exc:
        ChunkedUpload.start(str(tmp_path), name, size, max_bytes=10**6)
    assert exc.value.status_code == status


def test_filename_is_sanitised(tmp_path):
    upload = ChunkedUpload.start(str(tmp_path), "../../evil.xtc", 5, 10**6)
    assert upload.meta["name"] == "evil.xtc"


@pytest.mark.parametrize("bad", ["../x", "abc", "G" * 32, "A" * 32])
def test_invalid_upload_id(tmp_path, bad):
    with pytest.raises(UploadError):
        ChunkedUpload(str(tmp_path), bad)


def test_unknown_upload_404(tmp_path):
    with pytest.raises(UploadError) as exc:
        ChunkedUpload(str(tmp_path), "0" * 32).load()
    assert exc.value.status_code == 404


def test_resolve_uploaded_file(tmp_path):
    (tmp_path / "a.gro").write_bytes(b"x")
    assert resolve_uploaded_file(str(tmp_path), "a.gro") == str(tmp_path / "a.gro")
    for bad in ("../a.gro", "missing.gro", "", None):
        with pytest.raises(UploadError):
            resolve_uploaded_file(str(tmp_path), bad)
    assert os.path.isfile(tmp_path / "a.gro")
