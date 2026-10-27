import io
import json
from unittest.mock import patch

from biosimdb_interface.uploads import to_server


def test_load_extracted_files_handles_empty_manifest(tmp_path):
    """Missing roles return empty values."""
    (tmp_path / "pending_uploads.json").write_text("{}")
    assert to_server.load_extracted_files(tmp_path) == (None, [])


def test_verify_cached_file_meta_branches(tmp_path):
    """Cached metadata detects missing and changed files."""
    assert to_server.verify_cached_file_meta(tmp_path) == (
        False,
        "Missing cached file metadata. Please extract metadata again.",
    )

    to_server._save_pending_file_meta(
        tmp_path,
        [
            {"file_role": "unknown"},
            {"file_role": "topology", "file_name": "missing", "file_hash": "x"},
        ],
    )
    assert to_server.verify_cached_file_meta(tmp_path)[0] is False

    path = tmp_path / "top.pdb"
    path.write_text("topology")
    to_server._save_pending_file_meta(
        tmp_path,
        [{"file_role": "topology", "file_name": "top.pdb", "file_hash": "old"}],
    )

    with patch.object(to_server, "file_metadata", return_value={"file_hash": "new"}):
        assert to_server.verify_cached_file_meta(tmp_path)[0] is False

    with patch.object(to_server, "file_metadata", return_value={"file_hash": "old"}):
        assert to_server.verify_cached_file_meta(tmp_path) == (True, None)


def test_paths_are_reusable_validates_paths(tmp_path):
    """Only existing paths inside the workflow are reusable."""
    topology = tmp_path / "top.pdb"
    trajectory = tmp_path / "traj.xtc"
    topology.write_text("topology")
    trajectory.write_text("trajectory")

    assert not to_server._paths_are_reusable(tmp_path, None, [str(trajectory)])
    assert not to_server._paths_are_reusable(tmp_path, str(topology), [])
    assert not to_server._paths_are_reusable(tmp_path, "missing", [str(trajectory)])
    assert to_server._paths_are_reusable(tmp_path, str(topology), [str(trajectory)])


def test_save_request_files_uploads_and_normalizes_roles(app, tmp_path):
    """Uploaded trajectory[] files are saved under trajectory."""
    with app.test_request_context(
        "/",
        method="POST",
        data={
            "topology": (io.BytesIO(b"topology"), "top.pdb"),
            "trajectory[]": (io.BytesIO(b"trajectory"), "traj.xtc"),
        },
        content_type="multipart/form-data",
    ):
        with patch.object(to_server, "load_extracted_files", return_value=(None, [])):
            files = to_server._save_request_files(tmp_path)

    assert files["topology"] == [str(tmp_path / "top.pdb")]
    assert files["trajectory"] == [str(tmp_path / "traj.xtc")]


def test_extract_uploaded_file_metadata_uses_cache(app, tmp_path):
    """Cached metadata avoids reprocessing uploads."""
    cached = [{"file_name": "top.pdb"}]
    to_server._save_pending_file_meta(tmp_path, cached)

    with app.test_request_context("/"):
        assert to_server.extract_uploaded_file_metadata(tmp_path) == cached


def test_extract_uploaded_file_metadata_resets_stream(app, tmp_path):
    """Fresh metadata extraction rewinds uploaded streams."""
    stream = io.BytesIO(b"data")
    stream.read()

    with app.test_request_context("/"):
        with patch.object(
            to_server,
            "_save_files_and_extract_metadata",
            return_value=({}, [{"file_name": "top.pdb"}]),
        ):
            result = to_server.extract_uploaded_file_metadata(tmp_path)

    assert result == [{"file_name": "top.pdb"}]
    assert stream.tell() == len(stream.getvalue())


def test_save_pending_submission_writes_files_and_form(app, tmp_path):
    """Validated metadata and form values are persisted."""
    with app.test_request_context(
        "/",
        method="POST",
        data={"workflow_id": "workflow", "name": "test"},
    ):
        to_server.save_pending_submission({"engine": "GROMACS"}, tmp_path)

    metadata = json.loads((tmp_path / "simulation_metadata.json").read_text())
    form = json.loads((tmp_path / "pending_form_data.json").read_text())

    assert metadata["files"] == []
    assert form == {"name": ["test"]}
