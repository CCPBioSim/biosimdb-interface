from unittest.mock import patch

from biosim_extractor.metadata.validatemetadata import MetadataValidationError

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
            side_effect=MetadataValidationError(["bad metadata"]),
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


def test_cancel_submit_missing_workflow(client):
    """Rejects cancellation for an unknown workflow."""
    with patch(
        "biosimdb_interface.form.webform._get_workflow",
        side_effect=WorkflowNotFound("missing"),
    ):
        response = client.post("/cancel_submit?workflow_id=missing")
    assert response.status_code == 400
