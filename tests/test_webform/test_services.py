from unittest.mock import patch

from biosimdb_interface.core.workflows import WorkflowNotFound


def test_submit_without_login_redirects(client, extracted_workflow):
    """Submitting an extracted workflow without login redirects to login."""
    with (
        patch(
            "biosimdb_interface.webform.routes.validate_with_mdanalysis",
            return_value=None,
        ),
        patch(
            "biosimdb_interface.webform.services.verify_cached_file_meta",
            return_value=(True, None),
        ),
        patch("biosimdb_interface.webform.services.validate_metadata"),
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
            "biosimdb_interface.webform.routes.validate_with_mdanalysis",
            return_value=None,
        ),
        patch(
            "biosimdb_interface.webform.services.extract_uploaded_file_metadata",
            return_value=[],
        ),
        patch("biosimdb_interface.webform.services.validate_metadata"),
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
            "biosimdb_interface.webform.routes.validate_with_mdanalysis",
            return_value=None,
        ),
        patch(
            "biosimdb_interface.webform.services.verify_cached_file_meta",
            return_value=(True, None),
        ),
        patch("biosimdb_interface.webform.services.validate_metadata"),
        patch("biosimdb_interface.webform.services.save_pending_submission"),
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


def test_webform_cached_files_invalid(client, extracted_workflow):
    """Rejects changed cached files."""
    with patch(
        "biosimdb_interface.webform.services.verify_cached_file_meta",
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


def test_cancel_submit_missing_workflow(client):
    """Rejects cancellation for an unknown workflow."""
    with patch(
        "biosimdb_interface.webform.services.get_workflow",
        side_effect=WorkflowNotFound("missing"),
    ):
        response = client.post("/cancel_submit?workflow_id=missing")
    assert response.status_code == 400


def test_save_pending_submission(client, extracted_workflow):
    """A validated workflow submission is persisted."""
    with (
        patch(
            "biosimdb_interface.webform.routes.validate_with_mdanalysis",
            return_value=None,
        ),
        patch("biosimdb_interface.webform.services.validate_metadata"),
        patch(
            "biosimdb_interface.webform.services.verify_cached_file_meta",
            return_value=(True, None),
        ),
        patch(
            "biosimdb_interface.webform.services.save_pending_submission"
        ) as mock_save,
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
