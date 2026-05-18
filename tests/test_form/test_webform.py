from unittest.mock import patch


def test_webform_get(client):
    response = client.get("/webform")
    assert response.status_code == 200
    assert b"Extract Metadata" in response.data


def test_submit_without_login_redirects(client):
    """Submitting without a session token should redirect to login."""
    with (
        patch(
            "biosimdb_interface.form.webform.validate_with_mdanalysis",
            return_value=None,
        ),
        patch("biosimdb_interface.form.webform.validate_metadata"),
    ):
        response = client.post("/webform", data={"submit": "submit"})
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_metadata_download(client):
    """Save action returns a downloadable JSON file."""
    response = client.post(
        "/webform",
        data={
            "save": "1",
            "simulation[1][simulation_name]": "test_sim",  # 1-based index
        },
    )
    assert response.status_code == 200


def test_submit_with_token_renders_loading(client):
    with client.session_transaction() as sess:
        sess["access_token"] = "tok"
    with (
        patch(
            "biosimdb_interface.form.webform.validate_with_mdanalysis",
            return_value=None,
        ),
        patch("biosimdb_interface.form.webform.validate_metadata"),
        patch("biosimdb_interface.form.webform.save_pending_submission"),
    ):
        response = client.post("/webform", data={"submit": "1"})
    assert response.status_code == 200
    assert b"Submitting" in response.data


def test_resume_submit_with_pending_data(client):
    """resume_submit renders loading page when session has pending submission."""
    with client.session_transaction() as sess:
        sess["access_token"] = "tok"
        sess["pending_form_data"] = {"x": ["y"]}
        sess["pending_files_dir"] = "/tmp/fake"
    response = client.get("/resume_submit")
    assert response.status_code == 200
