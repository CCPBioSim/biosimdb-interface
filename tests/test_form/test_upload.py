import io
import json
import os
import tempfile
from unittest.mock import patch

from flask import session
from werkzeug.datastructures import ImmutableMultiDict

from biosimdb_interface.form import upload


def test_prepare_for_invenio(app):
    """prepare_for_invenio writes metadata.json, calls _data_collections_upload, cleans up."""
    tmpdir = tempfile.mkdtemp()
    traj_path = os.path.join(tmpdir, "traj.xtc")
    open(traj_path, "w").close()  # dummy file
    # New allowlist manifest required by _load_pending_upload_paths()
    with open(os.path.join(tmpdir, "pending_uploads.json"), "w") as f:
        json.dump({"trajectory": [traj_path]}, f)

    form_data = ImmutableMultiDict([("simulation[1][name]", "test")])

    with app.app_context():
        with patch(
            "biosimdb_interface.form.upload._data_collections_upload"
        ) as mock_upload:
            mock_upload.return_value = (None, "draft-abc")
            from biosimdb_interface.form.upload import prepare_for_invenio

            draft_id = prepare_for_invenio(form_data, tmpdir)
            assert draft_id == "draft-abc"
            assert not os.path.exists(tmpdir)  # cleaned up
            _, files_path = mock_upload.call_args.args
            assert traj_path in files_path


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
        from biosimdb_interface.form.upload import _load_pending_upload_paths

        files = _load_pending_upload_paths(tmpdir)

    assert traj_path in files
    assert top_path in files
    assert sim_meta_path in files


def test_save_pending_submission(client, extracted_workflow):
    """A validated workflow submission is persisted."""
    with (
        patch(
            "biosimdb_interface.form.webform.validate_with_mdanalysis",
            return_value=None,
        ),
        patch("biosimdb_interface.form.webform.validate_metadata"),
        patch(
            "biosimdb_interface.form.webform.verify_cached_file_meta",
            return_value=(True, None),
        ),
        patch("biosimdb_interface.form.webform.save_pending_submission") as mock_save,
    ):
        response = client.post(
            "/webform",
            data={
                "workflow_id": extracted_workflow.workflow_id,
                "submit": "1",
            },
        )

    assert response.status_code == 302
    mock_save.assert_called_once()


def test_do_submit_calls_invenio(client, workflow):
    """Submission uploads files from the specified workflow."""
    with open(os.path.join(workflow.tmpdir, "simulation_metadata.json"), "w") as f:
        json.dump({"simulation_name": ["test"]}, f)

    with client.session_transaction() as sess:
        sess["access_token"] = "fake-token"

    with (
        patch("biosimdb_interface.form.webform.invite_user") as mock_invite,
        patch("biosimdb_interface.form.webform.prepare_for_invenio") as mock_prepare,
    ):
        mock_prepare.return_value = "draft-123"

        response = client.post(
            f"/do_submit?workflow_id={workflow.workflow_id}",
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert b"View Record" in response.data
    assert b"Return to Webform" in response.data
    assert mock_invite.called
    assert mock_prepare.called


def test_load_extracted_files_handles_empty_manifest(tmp_path):
    """Missing roles return empty values."""
    (tmp_path / "pending_uploads.json").write_text("{}")
    assert upload.load_extracted_files(tmp_path) == (None, [])


def test_verify_cached_file_meta_branches(tmp_path):
    """Cached metadata detects missing and changed files."""
    assert upload.verify_cached_file_meta(tmp_path) == (
        False,
        "Missing cached file metadata. Please extract metadata again.",
    )

    upload._save_pending_file_meta(
        tmp_path,
        [
            {"file_role": "unknown"},
            {"file_role": "topology", "file_name": "missing", "file_hash": "x"},
        ],
    )
    assert upload.verify_cached_file_meta(tmp_path)[0] is False

    path = tmp_path / "top.pdb"
    path.write_text("topology")
    upload._save_pending_file_meta(
        tmp_path,
        [{"file_role": "topology", "file_name": "top.pdb", "file_hash": "old"}],
    )

    with patch.object(upload, "file_metadata", return_value={"file_hash": "new"}):
        assert upload.verify_cached_file_meta(tmp_path)[0] is False

    with patch.object(upload, "file_metadata", return_value={"file_hash": "old"}):
        assert upload.verify_cached_file_meta(tmp_path) == (True, None)


def test_paths_are_reusable_validates_paths(tmp_path):
    """Only existing paths inside the workflow are reusable."""
    topology = tmp_path / "top.pdb"
    trajectory = tmp_path / "traj.xtc"
    topology.write_text("topology")
    trajectory.write_text("trajectory")

    assert not upload._paths_are_reusable(tmp_path, None, [str(trajectory)])
    assert not upload._paths_are_reusable(tmp_path, str(topology), [])
    assert not upload._paths_are_reusable(tmp_path, "missing", [str(trajectory)])
    assert upload._paths_are_reusable(tmp_path, str(topology), [str(trajectory)])


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
        with patch.object(upload, "load_extracted_files", return_value=(None, [])):
            files = upload._save_request_files(tmp_path)

    assert files["topology"] == [str(tmp_path / "top.pdb")]
    assert files["trajectory"] == [str(tmp_path / "traj.xtc")]


def test_extract_uploaded_file_metadata_uses_cache(app, tmp_path):
    """Cached metadata avoids reprocessing uploads."""
    cached = [{"file_name": "top.pdb"}]
    upload._save_pending_file_meta(tmp_path, cached)

    with app.test_request_context("/"):
        assert upload.extract_uploaded_file_metadata(tmp_path) == cached


def test_extract_uploaded_file_metadata_resets_stream(app, tmp_path):
    """Fresh metadata extraction rewinds uploaded streams."""
    stream = io.BytesIO(b"data")
    stream.read()

    with app.test_request_context("/"):
        with patch.object(
            upload,
            "_save_files_and_extract_metadata",
            return_value=({}, [{"file_name": "top.pdb"}]),
        ):
            result = upload.extract_uploaded_file_metadata(tmp_path)

    assert result == [{"file_name": "top.pdb"}]
    assert stream.tell() == len(stream.getvalue())


def test_data_collections_upload_passes_token_and_files(app):
    """The upload helper forwards configured API arguments."""
    with app.test_request_context("/"):
        session["access_token"] = "token"

        with patch.object(
            upload,
            "run_record_upload",
            return_value=("repo", "draft"),
        ) as run_upload:
            result = upload._data_collections_upload("metadata.json", ["top.pdb"])

    assert result == ("repo", "draft")
    assert run_upload.call_args.kwargs["api_key"] == "token"
    assert run_upload.call_args.kwargs["files"] == ["top.pdb"]


def test_save_pending_submission_writes_files_and_form(app, tmp_path):
    """Validated metadata and form values are persisted."""
    with app.test_request_context(
        "/",
        method="POST",
        data={"workflow_id": "workflow", "name": "test"},
    ):
        upload.save_pending_submission({"engine": "GROMACS"}, tmp_path)

    metadata = json.loads((tmp_path / "simulation_metadata.json").read_text())
    form = json.loads((tmp_path / "pending_form_data.json").read_text())

    assert metadata["files"] == []
    assert form == {"name": ["test"]}


def test_submission_cancellation_flag(tmp_path):
    """Cancellation flags are written and detected."""
    workflow = tmp_path / "workflow"

    assert not upload.is_submission_cancelled(workflow)

    upload.mark_submission_cancelled(workflow)
    assert not upload.is_submission_cancelled(workflow)

    workflow.mkdir()
    upload.mark_submission_cancelled(workflow)

    assert upload.is_submission_cancelled(workflow)
    assert not upload.is_submission_cancelled(None)
