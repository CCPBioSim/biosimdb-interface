from unittest.mock import Mock, patch

import pytest

from biosimdb_interface.login import community_invite as mod


def _resp(payload):
    r = Mock()
    r.json.return_value = payload
    return r


def test_fetch_user_id_returns_id(app):
    with (
        app.app_context(),
        patch("biosimdb_interface.login.community_invite.requests.get") as get,
    ):
        get.return_value = _resp({"id": 7})
        assert mod._fetch_user_id("tok") == 7
        get.assert_called_once_with(
            "http://localhost/api/me",
            headers={"Authorization": "Bearer tok"},
            timeout=10,
        )


@pytest.mark.parametrize("payload", [[], {"username": "x"}])
def test_fetch_user_id_returns_none_for_non_id_payloads(app, payload):
    with (
        app.app_context(),
        patch("biosimdb_interface.login.community_invite.requests.get") as get,
    ):
        get.return_value = _resp(payload)
        assert mod._fetch_user_id("tok") is None


def test_invite_user_does_not_post_if_member_exists(app):
    with (
        app.app_context(),
        patch(
            "biosimdb_interface.login.community_invite._fetch_user_id", return_value=42
        ),
        patch("biosimdb_interface.login.community_invite.requests.get") as get,
        patch("biosimdb_interface.login.community_invite.requests.post") as post,
    ):
        get.side_effect = [
            _resp({"id": "comm-1"}),
            _resp({"hits": {"hits": [{"member": {"id": "42"}}]}}),
        ]

        result = mod.invite_user("biosimdb", "tok")

        post.assert_not_called()
        assert result == mod.INVITE_ALREADY_MEMBER


def test_invite_user_posts_if_member_missing(app):
    app.config["BIOSIMDB_SERVICE_TOKEN"] = "svc-token"
    with (
        app.app_context(),
        patch(
            "biosimdb_interface.login.community_invite._fetch_user_id", return_value=42
        ),
        patch("biosimdb_interface.login.community_invite.requests.get") as get,
        patch("biosimdb_interface.login.community_invite.requests.post") as post,
    ):
        get.side_effect = [
            _resp({"id": "comm-1"}),
            _resp({"hits": {"hits": [{"member": {"id": "99"}}]}}),
        ]
        post.return_value.ok = True

        result = mod.invite_user("biosimdb", "tok")

        post.assert_called_once_with(
            "http://localhost/api/communities/comm-1/invitations",
            json={"members": [{"id": "42", "type": "user"}], "role": "reader"},
            headers={"Authorization": "Bearer svc-token"},
            timeout=10,
        )
        assert result == mod.INVITE_SENT


def test_invite_user_returns_failed_if_post_fails(app):
    with (
        app.app_context(),
        patch(
            "biosimdb_interface.login.community_invite._fetch_user_id", return_value=42
        ),
        patch("biosimdb_interface.login.community_invite.requests.get") as get,
        patch("biosimdb_interface.login.community_invite.requests.post") as post,
    ):
        get.side_effect = [
            _resp({"id": "comm-1"}),
            _resp({"hits": {"hits": []}}),
        ]
        post.return_value.ok = False
        post.return_value.status_code = 500
        post.return_value.text = "error"

        assert mod.invite_user("biosimdb", "tok") == mod.INVITE_FAILED


def test_invite_user_returns_pending_if_already_invited(app):
    with (
        app.app_context(),
        patch(
            "biosimdb_interface.login.community_invite._fetch_user_id", return_value=42
        ),
        patch("biosimdb_interface.login.community_invite.requests.get") as get,
        patch("biosimdb_interface.login.community_invite.requests.post") as post,
    ):
        get.side_effect = [
            _resp({"id": "comm-1"}),
            _resp({"hits": {"hits": []}}),
        ]
        post.return_value.ok = False
        post.return_value.status_code = 400
        post.return_value.text = (
            '{"status": 400, "message": "A member was already added or invited."}'
        )

        assert mod.invite_user("biosimdb", "tok") == mod.INVITE_PENDING
