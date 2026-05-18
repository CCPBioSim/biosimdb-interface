import io
from unittest.mock import patch


def test_validate_direct_valid_files(client):
    with patch("biosimdb_interface.form.validation.Universe"):
        response = client.post(
            "/webform",
            data={
                "save": "1",
                "topology": (io.BytesIO(b"fake"), "topol.gro"),
                "trajectory[]": (io.BytesIO(b"fake"), "traj.xtc"),
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 200


def test_validate_direct_mda_error(client):
    with patch(
        "biosimdb_interface.form.validation.Universe",
        side_effect=Exception("bad format"),
    ):
        response = client.post(
            "/webform",
            data={
                "save": "1",
                "topology": (io.BytesIO(b"fake"), "topol.gro"),
                "trajectory[]": (io.BytesIO(b"fake"), "traj.xtc"),
            },
            content_type="multipart/form-data",
        )
        assert b"bad format" in response.data


def test_valid_topology_trajectory(client):
    """Validation passes when MDAnalysis accepts the files."""
    with patch(
        "biosimdb_interface.form.webform.validate_with_mdanalysis", return_value=None
    ):
        response = client.post("/webform", data={"save": "1"})
        assert response.status_code == 200


def test_incompatible_files_returns_error(client):
    """Invalid files re-render the form with a flash error, not a redirect."""
    with patch(
        "biosimdb_interface.form.webform.validate_with_mdanalysis",
        return_value="invalid file format",
    ):
        response = client.post("/webform", data={"save": "1"})
        assert response.status_code == 200
        assert b"invalid file format" in response.data


def test_validation_no_files_returns_none(client):
    """No topology uploaded — validation returns an error message."""
    with client.application.test_request_context("/webform", method="POST"):
        from biosimdb_interface.form.validation import validate_with_mdanalysis

        result = validate_with_mdanalysis()
        assert result is not None
        assert "topology" in result.lower()


def test_validation_mda_success(client):
    with patch(
        "biosimdb_interface.form.webform.validate_with_mdanalysis", return_value=None
    ):
        response = client.post("/webform", data={"save": "1"})
        assert response.status_code == 200


def test_validation_mda_failure_flashes_error(client):
    with patch(
        "biosimdb_interface.form.webform.validate_with_mdanalysis",
        return_value="cannot read file",
    ):
        response = client.post("/webform", data={"save": "1"})
        assert b"cannot read file" in response.data
