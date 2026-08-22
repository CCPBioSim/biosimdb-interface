from unittest.mock import patch


def _set_extracted_files(client, tmp_path):
    """Seed the session with files produced by metadata extraction."""
    topology = tmp_path / "topol.gro"
    trajectory = tmp_path / "traj.xtc"
    topology.write_bytes(b"fake")
    trajectory.write_bytes(b"fake")

    with client.session_transaction() as sess:
        sess["submission_tmpdir"] = str(tmp_path)
        sess["topo_path"] = str(topology)
        sess["traj_files"] = [str(trajectory)]


def test_validate_direct_valid_files(client, tmp_path):
    _set_extracted_files(client, tmp_path)
    with patch("biosimdb_interface.form.validation.Universe"):
        response = client.post(
            "/webform",
            data={"save": "1"},
        )
        assert response.status_code == 200


def test_validate_direct_mda_error(client, tmp_path):
    _set_extracted_files(client, tmp_path)
    with patch(
        "biosimdb_interface.form.validation.Universe",
        side_effect=Exception("bad format"),
    ):
        response = client.post(
            "/webform",
            data={"save": "1"},
        )
        assert b"bad format" in response.data


def test_valid_topology_trajectory(client, tmp_path):
    """Validation passes when MDAnalysis accepts the files."""
    _set_extracted_files(client, tmp_path)
    with patch(
        "biosimdb_interface.form.webform.validate_with_mdanalysis", return_value=None
    ):
        response = client.post("/webform", data={"save": "1"})
        assert response.status_code == 200


def test_incompatible_files_returns_error(client, tmp_path):
    """Unreadable extracted files return a validation error."""
    _set_extracted_files(client, tmp_path)
    """Invalid files re-render the form with a flash error, not a redirect."""
    with patch(
        "biosimdb_interface.form.webform.validate_with_mdanalysis",
        return_value="invalid file format",
    ):
        response = client.post("/webform", data={"save": "1"})
        assert response.status_code == 200
        assert b"invalid file format" in response.data


def test_validation_no_files_returns_error():
    """Missing saved file paths produce a validation error."""
    from biosimdb_interface.form.validation import validate_with_mdanalysis

    result = validate_with_mdanalysis(None, [])
    assert result is not None
    assert "topology" in result.lower()


def test_validation_mda_success(client, tmp_path):
    _set_extracted_files(client, tmp_path)
    with patch(
        "biosimdb_interface.form.webform.validate_with_mdanalysis", return_value=None
    ):
        response = client.post("/webform", data={"save": "1"})
        assert response.status_code == 200


def test_validation_mda_failure_returns_error(client, tmp_path):
    """MDAnalysis failures are returned as JSON validation errors."""
    _set_extracted_files(client, tmp_path)
    with patch(
        "biosimdb_interface.form.webform.validate_with_mdanalysis",
        return_value="cannot read file",
    ):
        response = client.post("/webform", data={"save": "1"})
        assert b"cannot read file" in response.data
