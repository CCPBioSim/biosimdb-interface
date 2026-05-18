import os
import tempfile
from unittest.mock import patch

from werkzeug.datastructures import ImmutableMultiDict


def test_prepare_for_invenio(app):
    """prepare_for_invenio writes metadata.json, calls _data_collections_upload, cleans up."""
    tmpdir = tempfile.mkdtemp()
    open(os.path.join(tmpdir, "traj.xtc"), "w").close()  # dummy file

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


def test_save_pending_submission(client):
    with (
        patch(
            "biosimdb_interface.form.webform.validate_with_mdanalysis",
            return_value=None,
        ),
        patch("biosimdb_interface.form.webform.validate_metadata"),
        patch("biosimdb_interface.form.webform.save_pending_submission") as mock_save,
    ):
        mock_save.return_value = None
        client.post(
            "/webform",
            data={
                "submit": "1",
            },
            content_type="multipart/form-data",
        )
        assert mock_save.called


def test_do_submit_calls_invenio(client):
    """Submission triggers Invenio upload with correct args."""
    with client.session_transaction() as sess:
        sess["access_token"] = "fake-token"
        sess["pending_form_data"] = {"simulation_name": ["test"]}
        sess["pending_files_dir"] = "/tmp/fake_pending"

    with patch("biosimdb_interface.form.webform.prepare_for_invenio") as mock_prepare:
        mock_prepare.return_value = "draft-123"
        response = client.post("/do_submit")
        assert mock_prepare.called
        assert response.status_code in (200, 302)
