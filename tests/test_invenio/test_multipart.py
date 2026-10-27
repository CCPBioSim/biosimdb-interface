from unittest.mock import MagicMock

import pytest
import requests

from biosimdb_interface.core.cancellation import MultipartTooSlow, UploadCancelled
from biosimdb_interface.invenio import multipart


def test_upload_single_sends_content_and_returns_commit_url(app, tmp_path):
    """Uploads a file in one PUT and returns its commit URL."""
    path = tmp_path / "topol.gro"
    path.write_bytes(b"topology")
    session = MagicMock()
    session.post.return_value = make_response(
        201,
        payload={
            "entries": [
                {
                    "key": path.name,
                    "links": {
                        "content": "https://example.org/content",
                        "commit": "https://example.org/commit",
                    },
                }
            ]
        },
    )
    session.put.return_value = make_response(200)

    with app.app_context():
        result = multipart.upload_single(
            session,
            "https://example.org",
            "draft-1",
            path,
            path.name,
            path.stat().st_size,
        )

    assert result == "https://example.org/commit"
    session.put.assert_called_once()
    assert session.put.call_args.kwargs["headers"] == {
        "Content-Type": "application/octet-stream"
    }


def test_upload_single_propagates_cancellation(app, tmp_path):
    """Propagates cancellation raised during the content PUT."""
    path = tmp_path / "topol.gro"
    path.write_bytes(b"topology")
    session = MagicMock()
    session.post.return_value = make_response(
        201,
        payload={
            "entries": [
                {
                    "key": path.name,
                    "links": {"content": "https://example.org/content"},
                }
            ]
        },
    )
    session.put.side_effect = UploadCancelled

    with app.app_context(), pytest.raises(UploadCancelled):
        multipart.upload_single(
            session,
            "https://example.org",
            "draft-1",
            path,
            path.name,
            path.stat().st_size,
        )


def test_upload_single_propagates_request_failure(app, tmp_path):
    """Propagates a network failure during the content PUT."""
    path = tmp_path / "topol.gro"
    path.write_bytes(b"topology")
    session = MagicMock()
    session.post.return_value = make_response(
        201,
        payload={
            "entries": [
                {
                    "key": path.name,
                    "links": {"content": "https://example.org/content"},
                }
            ]
        },
    )
    session.put.side_effect = requests.ConnectionError("connection lost")

    with app.app_context(), pytest.raises(requests.RequestException):
        multipart.upload_single(
            session,
            "https://example.org",
            "draft-1",
            path,
            path.name,
            path.stat().st_size,
        )


def test_put_part_retries_request_exception(tmp_path, monkeypatch):
    """Retries a request exception and succeeds on a later attempt."""
    path = tmp_path / "part.bin"
    path.write_bytes(b"payload")
    s3 = MagicMock()
    s3.put.side_effect = [
        requests.ConnectionError("temporary failure"),
        make_response(200),
    ]
    monkeypatch.setattr(multipart.time, "sleep", lambda _: None)

    progress = multipart.Progress(path.stat().st_size)
    multipart.put_part(
        s3,
        path,
        1,
        "https://storage/part-1",
        part_size=10,
        size=path.stat().st_size,
        progress=progress,
        cancelled=lambda: False,
    )

    assert s3.put.call_count == 2
    assert progress.sent == path.stat().st_size


def test_put_part_raises_after_all_attempts_fail(tmp_path, monkeypatch):
    """Raises after exhausting retries for a part."""
    path = tmp_path / "part.bin"
    path.write_bytes(b"payload")
    s3 = MagicMock()
    s3.put.return_value = make_response(500, "storage error")
    monkeypatch.setattr(multipart.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="failed after"):
        multipart.put_part(
            s3,
            path,
            1,
            "https://storage/part-1",
            part_size=10,
            size=path.stat().st_size,
            progress=multipart.Progress(path.stat().st_size),
            cancelled=lambda: False,
        )


def test_upload_multipart_rejects_missing_part_links(app, tmp_path):
    """Rejects initialization responses that omit the expected part links."""
    path = tmp_path / "traj.xtc"
    path.write_bytes(b"trajectory")
    session = MagicMock()
    session.post.return_value = make_response(
        201,
        payload={
            "entries": [
                {
                    "key": path.name,
                    "links": {"parts": [], "commit": "https://example.org/commit"},
                }
            ]
        },
    )

    with app.app_context(), pytest.raises(RuntimeError, match="part links"):
        multipart.upload_multipart(
            session,
            "https://example.org",
            "draft-1",
            path,
            path.name,
            path.stat().st_size,
            chunk_mb=1,
            workers=1,
        )


def test_upload_file_stop_callback_cancels(app, monkeypatch, tmp_path):
    """Stops a small-file multipart attempt when cancellation is requested."""
    path = tmp_path / "small.bin"

    def multipart_attempt(*args):
        cancelled = args[-1]
        cancelled()

    monkeypatch.setattr(multipart, "upload_multipart", multipart_attempt)

    with app.app_context(), pytest.raises(UploadCancelled):
        multipart.upload_file(
            MagicMock(),
            "https://example.org",
            "draft-1",
            path,
            path.name,
            100,
            chunk_mb=1,
            cancelled=lambda: True,
        )


def test_upload_file_stop_callback_enforces_deadline(app, monkeypatch, tmp_path):
    """Falls back to a single PUT when the multipart deadline expires."""
    path = tmp_path / "small.bin"
    session = MagicMock()
    single_upload = MagicMock(return_value="single-commit")
    monkeypatch.setattr(multipart, "upload_single", single_upload)
    monkeypatch.setattr(
        multipart.time, "monotonic", iter([0, multipart.SLOW_AFTER + 1]).__next__
    )

    def multipart_attempt(*args):
        cancelled = args[-1]
        cancelled()

    monkeypatch.setattr(multipart, "upload_multipart", multipart_attempt)

    with app.app_context():
        result = multipart.upload_file(
            session,
            "https://example.org",
            "draft-1",
            path,
            "folder/file.bin",
            100,
            chunk_mb=1,
        )

    assert result == "single-commit"
    session.delete.assert_called_once()
    single_upload.assert_called_once()


def make_response(status_code=200, text="ok", payload=None):
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.headers = {}
    response.json.return_value = payload or {}
    return response


def test_check_accepts_expected_status():
    multipart.check(make_response(201), 201, "File init")


def test_check_includes_auth_hint_for_unauthorized_response():
    with pytest.raises(Exception, match="token was rejected"):
        multipart.check(make_response(401, "unauthorized"), 201, "File init")


def test_put_part_retries_then_succeeds(tmp_path, monkeypatch):
    """Retries a failed part and records its bytes after success."""
    path = tmp_path / "part.bin"
    path.write_bytes(b"payload")

    s3 = MagicMock()
    s3.put.side_effect = [
        make_response(500, "temporary failure"),
        make_response(200),
    ]
    progress = multipart.Progress(path.stat().st_size)
    monkeypatch.setattr(multipart.time, "sleep", lambda _: None)

    multipart.put_part(
        s3,
        path,
        1,
        "https://storage/part-1",
        part_size=10,
        size=path.stat().st_size,
        progress=progress,
        cancelled=lambda: False,
    )

    assert s3.put.call_count == 2
    assert progress.sent == path.stat().st_size


def test_put_part_stops_if_cancelled(tmp_path):
    path = tmp_path / "part.bin"
    path.write_bytes(b"payload")
    s3 = MagicMock()

    with pytest.raises(UploadCancelled):
        multipart.put_part(
            s3,
            path,
            1,
            "https://storage/part-1",
            part_size=10,
            size=path.stat().st_size,
            progress=multipart.Progress(path.stat().st_size),
            cancelled=lambda: True,
        )

    s3.put.assert_not_called()


def test_upload_multipart_uploads_parts_and_returns_commit_url(
    app, monkeypatch, tmp_path
):
    """Initializes multipart transfer, uploads its part, and returns commit link."""
    path = tmp_path / "traj.xtc"
    path.write_bytes(b"trajectory")

    api_session = MagicMock()
    api_session.post.return_value = make_response(
        201,
        payload={
            "entries": [
                {
                    "key": path.name,
                    "links": {
                        "parts": [{"part": 1, "url": "https://storage/part-1"}],
                        "commit": "https://example.org/commit",
                    },
                }
            ]
        },
    )

    s3_session = MagicMock()
    s3_session.put.return_value = make_response(200)
    monkeypatch.setattr(multipart.requests, "Session", lambda: s3_session)

    with app.app_context():
        commit_url = multipart.upload_multipart(
            api_session,
            "https://example.org",
            "draft-1",
            path,
            path.name,
            path.stat().st_size,
            chunk_mb=1,
            workers=1,
        )

    assert commit_url == "https://example.org/commit"
    assert s3_session.put.call_count == 1
    assert api_session.post.call_args.kwargs["json"][0]["transfer"]["type"] == "M"


def test_upload_file_uses_multipart_for_large_file(monkeypatch, tmp_path):
    path = tmp_path / "large.bin"
    upload = MagicMock(return_value="commit-url")
    monkeypatch.setattr(multipart, "upload_multipart", upload)

    result = multipart.upload_file(
        MagicMock(),
        "https://example.org",
        "draft-1",
        path,
        path.name,
        multipart.SINGLE_MAX + 1,
        chunk_mb=10,
    )

    assert result == "commit-url"
    assert upload.call_args.args[7] == 1  # one worker for large files


def test_upload_file_falls_back_to_single_put_after_timeout(app, monkeypatch, tmp_path):
    path = tmp_path / "small.bin"
    multipart_upload = MagicMock(side_effect=MultipartTooSlow)
    single_upload = MagicMock(return_value="single-commit")
    session = MagicMock()

    monkeypatch.setattr(multipart, "upload_multipart", multipart_upload)
    monkeypatch.setattr(multipart, "upload_single", single_upload)

    with app.app_context():
        result = multipart.upload_file(
            session,
            "https://example.org",
            "draft-1",
            path,
            "folder/a b.bin",
            100,
            chunk_mb=10,
        )

    assert result == "single-commit"
    session.delete.assert_called_once()
    single_upload.assert_called_once()
