from unittest.mock import patch

from biosimdb_interface.login import login as login_module


def test_login_redirects_to_auth_url(client):
    response = client.get("/login")
    assert response.status_code == 302
    assert "response_type=code" in response.headers["Location"]


def test_callback_invalid_state_returns_400(client):
    with client.session_transaction() as sess:
        sess["oauth_state"] = "correct-state"
    response = client.get("/callback?state=wrong-state&code=abc")
    assert response.status_code == 400


def test_callback_no_code_redirects(client):
    with client.session_transaction() as sess:
        sess["oauth_state"] = "mystate"
    response = client.get("/callback?state=mystate")
    assert response.status_code == 302


def test_callback_token_exchange_fails_redirects(client):
    with client.session_transaction() as sess:
        sess["oauth_state"] = "mystate"
    with patch("biosimdb_interface.login.login.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"error": "invalid_grant"}
        response = client.get("/callback?state=mystate&code=abc")
    assert response.status_code == 302


def test_callback_success_sets_token(client):
    with client.session_transaction() as sess:
        sess["oauth_state"] = "mystate"
    with patch("biosimdb_interface.login.login.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"access_token": "tok123"}
        response = client.get("/callback?state=mystate&code=abc")
    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess["access_token"] == "tok123"


def test_logout_clears_token(client):
    with client.session_transaction() as sess:
        sess["access_token"] = "tok123"
    response = client.get("/logout")
    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert "access_token" not in sess


def test_fetch_user_email_returns_email(app):
    with app.app_context():
        with patch("biosimdb_interface.login.login.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"email": "user@example.org"}
            email = login_module._fetch_user_email("tok123")
    assert email == "user@example.org"


def test_fetch_user_email_returns_none_non_200(app):
    with app.app_context():
        with patch("biosimdb_interface.login.login.requests.get") as mock_get:
            mock_get.return_value.status_code = 401
            email = login_module._fetch_user_email("tok123")
    assert email is None


def test_fetch_user_email_returns_none_on_exception(app):
    with app.app_context():
        with patch(
            "biosimdb_interface.login.login.requests.get", side_effect=Exception("boom")
        ):
            email = login_module._fetch_user_email("tok123")
    assert email is None


def test_callback_success_sets_user_email(client):
    with client.session_transaction() as sess:
        sess["oauth_state"] = "mystate"
    with (
        patch("biosimdb_interface.login.login.requests.post") as mock_post,
        patch(
            "biosimdb_interface.login.login._fetch_user_email",
            return_value="user@example.org",
        ),
    ):
        mock_post.return_value.json.return_value = {"access_token": "tok123"}
        response = client.get("/callback?state=mystate&code=abc")

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess["access_token"] == "tok123"
        assert sess["user_email"] == "user@example.org"


def test_callback_success_clears_stale_user_email_when_not_found(client):
    with client.session_transaction() as sess:
        sess["oauth_state"] = "mystate"
        sess["user_email"] = "old@example.org"
    with (
        patch("biosimdb_interface.login.login.requests.post") as mock_post,
        patch("biosimdb_interface.login.login._fetch_user_email", return_value=None),
    ):
        mock_post.return_value.json.return_value = {"access_token": "tok123"}
        response = client.get("/callback?state=mystate&code=abc")

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess["access_token"] == "tok123"
        assert "user_email" not in sess
