import json
import os
from unittest.mock import Mock, patch

import requests

from biosimdb_interface.form.workflows import WorkflowNotFound


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


def test_webform_missing_workflow(client):
    """Rejects an unknown workflow."""
    with patch(
        "biosimdb_interface.form.webform._get_workflow",
        side_effect=WorkflowNotFound("missing"),
    ):
        response = client.post("/webform", data={"save": "1"})
    assert response.status_code == 400


def test_webform_missing_files(client, workflow):
    """Rejects submissions without extracted files."""
    with patch(
        "biosimdb_interface.form.webform.load_extracted_files",
        return_value=(None, []),
    ):
        response = client.post(
            "/webform",
            data={"workflow_id": workflow.workflow_id, "submit": "1"},
        )
    assert response.status_code == 400


def test_webform_cached_files_invalid(client, extracted_workflow):
    """Rejects changed cached files."""
    with patch(
        "biosimdb_interface.form.webform.verify_cached_file_meta",
        return_value=(False, "changed files"),
    ):
        response = client.post(
            "/webform",
            data={
                "workflow_id": extracted_workflow.workflow_id,
                "submit": "1",
            },
        )
    assert response.status_code == 400
    assert b"changed files" in response.data


def test_webform_metadata_invalid(client, extracted_workflow):
    """Returns schema validation errors."""
    with (
        patch(
            "biosimdb_interface.form.webform.validate_with_mdanalysis",
            return_value=None,
        ),
        patch(
            "biosimdb_interface.form.webform.validate_metadata",
            side_effect=ValueError("bad metadata"),
        ),
    ):
        response = client.post(
            "/webform",
            data={
                "workflow_id": extracted_workflow.workflow_id,
                "save": "1",
            },
        )
    assert response.status_code == 200
    assert b"bad metadata" in response.data


def test_resume_submit_requires_login(client, workflow):
    """Redirects unauthenticated users."""
    response = client.get(f"/resume_submit?workflow_id={workflow.workflow_id}")
    assert response.status_code == 302


def test_resume_submit_missing_pending_data(client, workflow):
    """Redirects when no pending submission exists."""
    with client.session_transaction() as sess:
        sess["access_token"] = "token"

    response = client.get(f"/resume_submit?workflow_id={workflow.workflow_id}")
    assert response.status_code == 302
    assert "/webform" in response.headers["Location"]


def test_do_submit_missing_workflow(client, app):
    """Rejects an unknown submission workflow."""
    with patch.object(
        app.extensions["workflow_store"],
        "get",
        side_effect=WorkflowNotFound("missing"),
    ):
        response = client.post("/do_submit?workflow_id=missing")

    assert response.status_code == 400


def test_do_submit_missing_metadata(client, workflow):
    """Redirects when metadata is missing."""
    response = client.post(f"/do_submit?workflow_id={workflow.workflow_id}")
    assert response.status_code == 302


def test_do_submit_cancelled(client, workflow):
    """Stops cancelled submissions."""
    with patch(
        "biosimdb_interface.form.webform.is_submission_cancelled",
        return_value=True,
    ):
        response = client.post(f"/do_submit?workflow_id={workflow.workflow_id}")
    assert response.status_code == 302


def test_do_submit_upload_failure(client, workflow):
    """Redirects when upload returns no draft."""
    metadata = os.path.join(workflow.tmpdir, "simulation_metadata.json")
    with open(metadata, "w") as file:
        json.dump({}, file)

    with (
        patch("biosimdb_interface.form.webform.invite_user"),
        patch(
            "biosimdb_interface.form.webform.prepare_for_invenio",
            return_value=None,
        ),
    ):
        response = client.post(f"/do_submit?workflow_id={workflow.workflow_id}")

    assert response.status_code == 302


def test_do_submit_http_error(client, workflow):
    """Redirects after an upload HTTP failure."""
    metadata = os.path.join(workflow.tmpdir, "simulation_metadata.json")
    with open(metadata, "w") as file:
        json.dump({}, file)

    error = requests.HTTPError(response=Mock(status_code=500))
    with (
        patch("biosimdb_interface.form.webform.invite_user"),
        patch(
            "biosimdb_interface.form.webform.prepare_for_invenio",
            side_effect=error,
        ),
    ):
        response = client.post(f"/do_submit?workflow_id={workflow.workflow_id}")

    assert response.status_code == 302


def test_cancel_submit(client, workflow):
    """Marks a submission as cancelled and clears session state."""
    with client.session_transaction() as sess:
        sess["access_token"] = "token"
        sess["user_email"] = "user"

    with patch("biosimdb_interface.form.webform.mark_submission_cancelled") as cancel:
        response = client.post(f"/cancel_submit?workflow_id={workflow.workflow_id}")

    assert response.status_code == 200
    cancel.assert_called_once_with(workflow.tmpdir)


def test_cancel_submit_missing_workflow(client):
    """Rejects cancellation for an unknown workflow."""
    with patch(
        "biosimdb_interface.form.webform._get_workflow",
        side_effect=WorkflowNotFound("missing"),
    ):
        response = client.post("/cancel_submit?workflow_id=missing")
    assert response.status_code == 400


def test_submit_success_without_record(client):
    """Redirects when no submitted record exists."""
    response = client.get("/submit_success")
    assert response.status_code == 302


def test_do_submit_http_unauthorized(client, workflow):
    """Forces login after an expired upload session."""
    metadata = os.path.join(workflow.tmpdir, "simulation_metadata.json")
    with open(metadata, "w") as file:
        json.dump({}, file)

    error = requests.HTTPError(response=Mock(status_code=401))
    with (
        patch("biosimdb_interface.form.webform.invite_user"),
        patch(
            "biosimdb_interface.form.webform.prepare_for_invenio",
            side_effect=error,
        ),
    ):
        response = client.post(
            f"/do_submit?workflow_id={workflow.workflow_id}",
            data={"workflow_id": workflow.workflow_id},
        )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
