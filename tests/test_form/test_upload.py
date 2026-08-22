import json
import os
import tempfile
from unittest.mock import patch

from werkzeug.datastructures import ImmutableMultiDict


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


def test_save_pending_submission(client):
    """A validated submission with extracted files is persisted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with client.session_transaction() as sess:
            sess["submission_tmpdir"] = tmpdir
            sess["topo_path"] = f"{tmpdir}/topology.pdb"
            sess["traj_files"] = [f"{tmpdir}/trajectory.xtc"]

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
            patch(
                "biosimdb_interface.form.webform.save_pending_submission"
            ) as mock_save,
        ):
            response = client.post("/webform", data={"submit": "1"})

        assert response.status_code == 302
        mock_save.assert_called_once()


def test_do_submit_calls_invenio(client):
    """Submission triggers Invenio upload with correct args."""
    tmpdir = tempfile.mkdtemp()
    with open(os.path.join(tmpdir, "pending_form_data.json"), "w") as f:
        json.dump({"simulation_name": ["test"]}, f)

    with client.session_transaction() as sess:
        sess["access_token"] = "fake-token"
        sess["submission_tmpdir"] = tmpdir

    with (
        patch("biosimdb_interface.form.webform.invite_user") as mock_invite,
        patch("biosimdb_interface.form.webform.prepare_for_invenio") as mock_prepare,
    ):
        mock_prepare.return_value = "draft-123"
        response = client.post("/do_submit", follow_redirects=True)
        assert response.status_code == 200
        assert b"View Record" in response.data
        assert b"Return to Webform" in response.data
        assert mock_invite.called
        assert mock_prepare.called

    with client.session_transaction() as sess:
        assert "submission_tmpdir" not in sess
        assert "access_token" not in sess
        assert "user_email" not in sess
        assert "post_login_redirect" not in sess
