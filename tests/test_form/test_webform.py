import json
import os
import tempfile
from unittest.mock import patch


def _set_extracted_files(client, tmp_path, token=None):
    """Seed the session with files retained by metadata extraction."""
    topology = tmp_path / "topol.gro"
    trajectory = tmp_path / "traj.xtc"
    topology.write_bytes(b"fake")
    trajectory.write_bytes(b"fake")

    with client.session_transaction() as sess:
        sess["submission_tmpdir"] = str(tmp_path)
        sess["topo_path"] = str(topology)
        sess["traj_files"] = [str(trajectory)]
        if token:
            sess["access_token"] = token


def test_webform_get(client):
    response = client.get("/webform")
    assert response.status_code == 200
    assert b"Extract Metadata" in response.data


def test_submit_without_login_redirects(client, tmp_path):
    """Submitting extracted files without a token redirects to login."""
    _set_extracted_files(client, tmp_path)

    with (
        patch(
            "biosimdb_interface.form.webform.validate_with_mdanalysis",
            return_value=None,
        ),
        patch(
            "biosimdb_interface.form.webform.verify_cached_file_meta",
            return_value=(True, None),
        ),
        patch("biosimdb_interface.form.webform.validate_metadata"),
    ):
        response = client.post("/webform", data={"submit": "submit"})

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_metadata_download(client, tmp_path):
    """Save returns JSON after files have been extracted."""
    _set_extracted_files(client, tmp_path)

    with (
        patch(
            "biosimdb_interface.form.webform.validate_with_mdanalysis",
            return_value=None,
        ),
        patch(
            "biosimdb_interface.form.webform.extract_uploaded_file_metadata",
            return_value=[],
        ),
        patch("biosimdb_interface.form.webform.validate_metadata"),
    ):
        response = client.post(
            "/webform",
            data={"save": "1", "simulation[1][simulation_name]": "test_sim"},
        )

    assert response.status_code == 200


def test_submit_with_token_renders_loading(client, tmp_path):
    _set_extracted_files(client, tmp_path, token="tok")

    with (
        patch(
            "biosimdb_interface.form.webform.validate_with_mdanalysis",
            return_value=None,
        ),
        patch(
            "biosimdb_interface.form.webform.verify_cached_file_meta",
            return_value=(True, None),
        ),
        patch("biosimdb_interface.form.webform.validate_metadata"),
        patch("biosimdb_interface.form.webform.save_pending_submission"),
    ):
        response = client.post("/webform", data={"submit": "1"})

    assert response.status_code == 200
    assert b"Submitting" in response.data


def test_resume_submit_with_pending_data(client):
    """resume_submit renders loading page when session has pending submission."""
    tmpdir = tempfile.mkdtemp()
    with open(os.path.join(tmpdir, "pending_form_data.json"), "w") as f:
        json.dump({"x": ["y"]}, f)

    with client.session_transaction() as sess:
        sess["access_token"] = "tok"
        sess["submission_tmpdir"] = tmpdir
    response = client.get("/resume_submit")
    assert response.status_code == 200
