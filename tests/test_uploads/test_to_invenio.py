import json
import os
import tempfile
from unittest.mock import patch

from flask import session
from werkzeug.datastructures import ImmutableMultiDict

from biosimdb_interface.uploads import to_invenio


def test_prepare_for_invenio_writes_metadata_and_uploads_files(app, tmp_path):
    """prepare_for_invenio writes metadata and uploads manifest-listed files."""
    traj_path = tmp_path / "traj.xtc"
    traj_path.touch()

    (tmp_path / "pending_uploads.json").write_text(
        json.dumps({"trajectory": [str(traj_path)]})
    )

    form_data = ImmutableMultiDict([("simulation[1][name]", "test")])

    with app.app_context():
        with patch(
            "biosimdb_interface.uploads.to_invenio._data_collections_upload"
        ) as mock_upload:
            mock_upload.return_value = (None, "draft-abc")

            draft_id = to_invenio.prepare_for_invenio(form_data, str(tmp_path))

    assert draft_id == "draft-abc"
    assert tmp_path.exists()
    assert (tmp_path / "invenio_metadata.json").is_file()

    _, files_path = mock_upload.call_args.args
    assert str(traj_path) in files_path


def test_load_pending_upload_paths_uses_manifest_and_includes_sim_metadata(app):
    tmpdir = tempfile.mkdtemp()
    traj_path = os.path.join(tmpdir, "traj.xtc")
    top_path = os.path.join(tmpdir, "top.pdb")
    sim_meta_path = os.path.join(tmpdir, "simulation_metadata.json")

    open(traj_path, "w").close()
    open(top_path, "w").close()
    open(sim_meta_path, "w").close()

    with open(os.path.join(tmpdir, "pending_uploads.json"), "w") as f:
        json.dump({"trajectory": [traj_path], "topology": [top_path]}, f)
    with app.app_context():
        from biosimdb_interface.uploads.to_invenio import _load_pending_upload_paths

        files = _load_pending_upload_paths(tmpdir)

    assert traj_path in files
    assert top_path in files
    assert sim_meta_path in files


def test_data_collections_upload_passes_token_and_files(app):
    """The upload helper forwards configured API arguments."""
    with app.test_request_context("/"):
        session["access_token"] = "token"

        with patch.object(
            to_invenio,
            "run_record_upload",
            return_value=("repo", "draft"),
        ) as run_upload:
            result = to_invenio._data_collections_upload("metadata.json", ["top.pdb"])

    assert result == ("repo", "draft")
    assert run_upload.call_args.kwargs["api_key"] == "token"
    assert run_upload.call_args.kwargs["files"] == ["top.pdb"]


def test_fill_invenio_metadata_returns_dict():
    result = to_invenio._fill_invenio_metadata({})
    assert isinstance(result, dict)
    assert "custom_fields" in result
