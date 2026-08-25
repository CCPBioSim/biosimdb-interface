import io
import os
from unittest.mock import patch


def test_extract_missing_files_returns_400(client):
    response = client.post("/extract_metadata", data={})
    assert response.status_code == 400
    assert "missing" in response.get_json()["error"].lower()


def test_extract_success(client):
    with patch("biosimdb_interface.form.extract.MetadataPopulator") as MockSP:
        MockSP.return_value.populate.return_value = {"engine": "GROMACS"}
        data = {
            "workflow_id": "11111111-1111-4111-8111-111111111111",
            "topology": (io.BytesIO(b"fake"), "topol.gro"),
            "trajectory[]": (io.BytesIO(b"fake"), "traj.xtc"),
        }
        response = client.post(
            "/extract_metadata", data=data, content_type="multipart/form-data"
        )
        assert response.status_code == 200
        assert response.get_json()["simulation_metadata"] == {"engine": "GROMACS"}


def test_extract_exception_returns_500(client):
    with patch("biosimdb_interface.form.extract.MetadataPopulator") as MockSP:
        MockSP.return_value.populate.side_effect = RuntimeError("bad file")
        data = {
            "workflow_id": "11111111-1111-4111-8111-111111111111",
            "topology": (io.BytesIO(b"fake"), "topol.gro"),
            "trajectory[]": (io.BytesIO(b"fake"), "traj.xtc"),
        }
        response = client.post(
            "/extract_metadata", data=data, content_type="multipart/form-data"
        )
        assert response.status_code == 500


def test_two_tabs_keep_separate_extraction_directories(client, app):
    """Separate workflow IDs must never share or delete extracted files."""
    with patch("biosimdb_interface.form.extract.MetadataPopulator") as populator:
        populator.return_value.populate.return_value = {"engine": "GROMACS"}

        def extract(workflow_id, filename):
            return client.post(
                "/extract_metadata",
                data={
                    "workflow_id": workflow_id,
                    "topology": (io.BytesIO(b"topology"), f"{filename}.gro"),
                    "trajectory[]": (io.BytesIO(b"trajectory"), f"{filename}.xtc"),
                },
                content_type="multipart/form-data",
            )

        first_id = "11111111-1111-4111-8111-111111111111"
        second_id = "22222222-2222-4222-8222-222222222222"

        assert extract(first_id, "first").status_code == 200
        first_dir = app.extensions["workflow_store"].get(first_id).tmpdir

        assert extract(second_id, "second").status_code == 200
        second_dir = app.extensions["workflow_store"].get(second_id).tmpdir

    assert first_dir != second_dir
    assert os.path.isfile(os.path.join(first_dir, "first.gro"))
    assert os.path.isfile(os.path.join(second_dir, "second.gro"))

    client.post("/clear_extraction", data={"workflow_id": second_id})

    assert os.path.isdir(first_dir)
    assert not os.path.exists(second_dir)
