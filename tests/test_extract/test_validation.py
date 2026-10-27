from unittest.mock import patch


def test_validate_direct_valid_files(client, extracted_workflow):
    with patch("biosimdb_interface.extract.validation.Universe"):
        response = client.post(
            "/webform",
            data={"workflow_id": extracted_workflow.workflow_id, "save": "1"},
        )
        assert response.status_code == 200


def test_validate_direct_mda_error(client, extracted_workflow):
    with patch(
        "biosimdb_interface.extract.validation.Universe",
        side_effect=Exception("bad format"),
    ):
        response = client.post(
            "/webform",
            data={"workflow_id": extracted_workflow.workflow_id, "save": "1"},
        )
        assert b"bad format" in response.data


def test_valid_topology_trajectory(client, extracted_workflow):
    """Validation accepts files held by the tab workflow."""
    with patch(
        "biosimdb_interface.extract.validation.validate_with_mdanalysis",
        return_value=None,
    ):
        response = client.post(
            "/webform",
            data={
                "workflow_id": extracted_workflow.workflow_id,
                "save": "1",
            },
        )

    assert response.status_code == 200


def test_validation_no_files_returns_error():
    """Missing saved file paths produce a validation error."""
    from biosimdb_interface.extract.validation import validate_with_mdanalysis

    result = validate_with_mdanalysis(None, [])
    assert result is not None
    assert "topology" in result.lower()


def test_validation_mda_success(client, extracted_workflow):
    with patch(
        "biosimdb_interface.extract.validation.validate_with_mdanalysis",
        return_value=None,
    ):
        response = client.post(
            "/webform",
            data={
                "workflow_id": extracted_workflow.workflow_id,
                "save": "1",
            },
        )
        assert response.status_code == 200
