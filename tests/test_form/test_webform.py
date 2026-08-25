import json
import os
from unittest.mock import patch


def _set_extracted_files(client, tmp_path, token=None):
    """Seed the session with files retained by metadata extraction."""
    topology = tmp_path / "topol.gro"
    trajectory = tmp_path / "traj.xtc"
    topology.write_bytes(b"fake")
    trajectory.write_bytes(b"fake")

    with client.session_transaction() as sess:
        if token:
            sess["access_token"] = token


def test_webform_get(client):
    response = client.get("/webform")
    assert response.status_code == 200
    assert b"Extract Metadata" in response.data


def test_submit_without_login_redirects(client, extracted_workflow):
    """Submitting an extracted workflow without login redirects to login."""
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
        response = client.post(
            "/webform",
            data={
                "workflow_id": extracted_workflow.workflow_id,
                "submit": "submit",
            },
        )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_metadata_download(client, extracted_workflow):
    """Save returns metadata from the extracted tab workflow."""
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
            data={
                "workflow_id": extracted_workflow.workflow_id,
                "save": "1",
                "simulation[1][simulation_name]": "test_sim",
            },
        )

    assert response.status_code == 200


def test_submit_with_token_renders_loading(client, extracted_workflow):
    with client.session_transaction() as sess:
        sess["access_token"] = "tok"

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
        response = client.post(
            "/webform",
            data={
                "workflow_id": extracted_workflow.workflow_id,
                "submit": "1",
            },
        )

    assert response.status_code == 200
    assert b"Submitting" in response.data


def test_resume_submit_with_pending_data(client, workflow):
    """Resume resolves the workflow ID passed in the query string."""
    with open(os.path.join(workflow.tmpdir, "pending_form_data.json"), "w") as f:
        json.dump({"x": ["y"]}, f)

    with client.session_transaction() as sess:
        sess["access_token"] = "tok"

    response = client.get(f"/resume_submit?workflow_id={workflow.workflow_id}")

    assert response.status_code == 200
