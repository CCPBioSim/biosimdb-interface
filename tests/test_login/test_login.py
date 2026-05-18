from unittest.mock import patch


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
