from unittest.mock import patch

from biosim_extractor.metadata.validatemetadata import MetadataValidationError

from biosimdb_interface.core.workflows import WorkflowNotFound


def test_webform_get(client):
    response = client.get("/webform")
    assert response.status_code == 200
    assert b"Extract Metadata" in response.data


def test_webform_missing_workflow(client):
    """Rejects an unknown workflow."""
    with patch(
        "biosimdb_interface.webform.routes.get_workflow",
        side_effect=WorkflowNotFound("missing"),
    ):
        response = client.post("/webform", data={"save": "1"})
    assert response.status_code == 400


def test_webform_missing_files(client, workflow):
    """Rejects submissions without extracted files."""
    with patch(
        "biosimdb_interface.webform.routes.load_extracted_files",
        return_value=(None, []),
    ):
        response = client.post(
            "/webform",
            data={"workflow_id": workflow.workflow_id, "submit": "1"},
        )
    assert response.status_code == 400


def test_webform_metadata_invalid(client, extracted_workflow):
    """Returns schema validation errors."""
    with (
        patch(
            "biosimdb_interface.webform.routes.validate_with_mdanalysis",
            return_value=None,
        ),
        patch(
            "biosimdb_interface.webform.services.validate_metadata",
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


def test_do_submit_missing_metadata(client, workflow):
    """Redirects when metadata is missing."""
    response = client.post(f"/do_submit?workflow_id={workflow.workflow_id}")
    assert response.status_code == 302


def test_validation_mda_failure_returns_error(client, extracted_workflow):
    """MDAnalysis failures are returned as JSON validation errors."""
    with patch(
        "biosimdb_interface.webform.routes.validate_with_mdanalysis",
        return_value="cannot read file",
    ):
        response = client.post(
            "/webform",
            data={
                "workflow_id": extracted_workflow.workflow_id,
                "save": "1",
            },
        )
        assert b"cannot read file" in response.data


def test_incompatible_files_returns_error(client, extracted_workflow):
    """Invalid files re-render the form with a flash error, not a redirect."""
    with patch(
        "biosimdb_interface.webform.routes.validate_with_mdanalysis",
        return_value="invalid file format",
    ):
        response = client.post(
            "/webform",
            data={
                "workflow_id": extracted_workflow.workflow_id,
                "save": "1",
            },
        )
        assert response.status_code == 200
        assert b"invalid file format" in response.data
