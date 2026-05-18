import io
from unittest.mock import patch


def test_extract_missing_files_returns_400(client):
    response = client.post("/extract_metadata", data={})
    assert response.status_code == 400
    assert "missing" in response.get_json()["error"].lower()


def test_extract_success(client):
    with patch("biosimdb_interface.form.extract.SchemaPopulator") as MockSP:
        MockSP.return_value.populate.return_value = {"engine": "GROMACS"}
        data = {
            "topology": (io.BytesIO(b"fake"), "topol.gro"),
            "trajectory[]": (io.BytesIO(b"fake"), "traj.xtc"),
        }
        response = client.post(
            "/extract_metadata", data=data, content_type="multipart/form-data"
        )
        assert response.status_code == 200
        assert response.get_json()["simulation_metadata"] == {"engine": "GROMACS"}


def test_extract_exception_returns_500(client):
    with patch("biosimdb_interface.form.extract.SchemaPopulator") as MockSP:
        MockSP.return_value.populate.side_effect = RuntimeError("bad file")
        data = {
            "topology": (io.BytesIO(b"fake"), "topol.gro"),
            "trajectory[]": (io.BytesIO(b"fake"), "traj.xtc"),
        }
        response = client.post(
            "/extract_metadata", data=data, content_type="multipart/form-data"
        )
        assert response.status_code == 500
