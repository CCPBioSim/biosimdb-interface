import json
import os
from unittest.mock import Mock, patch

import requests

from biosimdb_interface.core.workflows import WorkflowNotFound
from biosimdb_interface.submit import routes


def test_resume_submit_with_pending_data(client, workflow):
    """Resume resolves the workflow ID passed in the query string."""
    with open(os.path.join(workflow.tmpdir, "pending_form_data.json"), "w") as f:
        json.dump({"x": ["y"]}, f)

    with client.session_transaction() as sess:
        sess["access_token"] = "tok"

    response = client.get(f"/resume_submit?workflow_id={workflow.workflow_id}")

    assert response.status_code == 200


def test_do_submit_cancelled(client, workflow):
    """Stops cancelled submissions."""
    with patch(
        "biosimdb_interface.submit.routes.is_submission_cancelled",
        return_value=True,
    ):
        response = client.post(f"/do_submit?workflow_id={workflow.workflow_id}")
    assert response.status_code == 302


def test_do_submit_upload_failure(client, workflow):
    """Redirects when upload returns no draft."""
    metadata = os.path.join(workflow.tmpdir, "simulation_metadata.json")
    with open(metadata, "w") as file:
        json.dump({}, file)

    with (
        patch("biosimdb_interface.submit.routes.invite_user"),
        patch(
            "biosimdb_interface.submit.routes.prepare_for_invenio",
            return_value=None,
        ),
    ):
        response = client.post(f"/do_submit?workflow_id={workflow.workflow_id}")

    assert response.status_code == 302


def _write_metadata(workflow):
    metadata = os.path.join(workflow.tmpdir, "simulation_metadata.json")
    with open(metadata, "w") as file:
        json.dump({}, file)


def test_do_submit_flashes_invite_message(client, workflow):
    """Tells a newly invited user to check their email."""
    _write_metadata(workflow)

    with (
        patch("biosimdb_interface.submit.routes.invite_user", return_value="invited"),
        patch(
            "biosimdb_interface.submit.routes.prepare_for_invenio",
            return_value="draft-1",
        ),
    ):
        response = client.post(
            f"/do_submit?workflow_id={workflow.workflow_id}",
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert b"check your email" in response.data


def test_do_submit_no_invite_message_for_existing_member(client, workflow):
    """Does not show the invite message to existing members."""
    _write_metadata(workflow)

    with (
        patch(
            "biosimdb_interface.submit.routes.invite_user",
            return_value="already_member",
        ),
        patch(
            "biosimdb_interface.submit.routes.prepare_for_invenio",
            return_value="draft-1",
        ),
    ):
        response = client.post(
            f"/do_submit?workflow_id={workflow.workflow_id}",
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert b"check your email" not in response.data


def test_do_submit_no_invite_message_if_upload_fails(client, workflow):
    """Does not mention an invitation when the upload fails."""
    _write_metadata(workflow)

    with (
        patch("biosimdb_interface.submit.routes.invite_user", return_value="invited"),
        patch(
            "biosimdb_interface.submit.routes.prepare_for_invenio",
            return_value=None,
        ),
    ):
        response = client.post(
            f"/do_submit?workflow_id={workflow.workflow_id}",
            follow_redirects=True,
        )

    assert b"check your email" not in response.data


def test_do_submit_http_error(client, workflow):
    """Redirects after an upload HTTP failure."""
    metadata = os.path.join(workflow.tmpdir, "simulation_metadata.json")
    with open(metadata, "w") as file:
        json.dump({}, file)

    error = requests.HTTPError(response=Mock(status_code=500))
    with (
        patch("biosimdb_interface.submit.routes.invite_user"),
        patch(
            "biosimdb_interface.submit.routes.prepare_for_invenio",
            side_effect=error,
        ),
    ):
        response = client.post(f"/do_submit?workflow_id={workflow.workflow_id}")

    assert response.status_code == 302


def test_cancel_submit(client, workflow):
    """Marks a submission as cancelled and clears session state."""
    with client.session_transaction() as sess:
        sess["access_token"] = "token"
        sess["user_email"] = "user"

    with patch("biosimdb_interface.submit.routes.mark_submission_cancelled") as cancel:
        response = client.post(f"/cancel_submit?workflow_id={workflow.workflow_id}")

    assert response.status_code == 200
    cancel.assert_called_once_with(workflow.tmpdir)


def test_submit_success_without_record(client):
    """Redirects when no submitted record exists."""
    response = client.get("/submit_success")
    assert response.status_code == 302


def test_submission_cancellation_flag(tmp_path):
    """Cancellation flags are written and detected."""
    workflow = tmp_path / "workflow"

    assert not routes.is_submission_cancelled(workflow)

    routes.mark_submission_cancelled(workflow)
    assert not routes.is_submission_cancelled(workflow)

    workflow.mkdir()
    routes.mark_submission_cancelled(workflow)

    assert routes.is_submission_cancelled(workflow)
    assert not routes.is_submission_cancelled(None)


def test_do_submit_calls_invenio(client, workflow):
    """Submission uploads files from the specified workflow."""
    with open(os.path.join(workflow.tmpdir, "simulation_metadata.json"), "w") as f:
        json.dump({"simulation_name": ["test"]}, f)

    with client.session_transaction() as sess:
        sess["access_token"] = "fake-token"

    with (
        patch("biosimdb_interface.submit.routes.invite_user") as mock_invite,
        patch("biosimdb_interface.submit.routes.prepare_for_invenio") as mock_prepare,
    ):
        mock_prepare.return_value = "draft-123"

        response = client.post(
            f"/do_submit?workflow_id={workflow.workflow_id}",
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert b"View Record" in response.data
    assert b"Return to Webform" in response.data
    assert mock_invite.called
    assert mock_prepare.called


def test_do_submit_http_unauthorized_redirects_to_login(client, workflow):
    """Clears an expired token and redirects to login after a 401."""
    metadata = os.path.join(workflow.tmpdir, "simulation_metadata.json")
    with open(metadata, "w") as file:
        json.dump({}, file)

    with client.session_transaction() as sess:
        sess["access_token"] = "expired-token"

    error = requests.HTTPError(response=Mock(status_code=401))
    with (
        patch("biosimdb_interface.submit.routes.invite_user"),
        patch(
            "biosimdb_interface.submit.routes.prepare_for_invenio",
            side_effect=error,
        ),
    ):
        response = client.post(
            f"/do_submit?workflow_id={workflow.workflow_id}",
            data={"workflow_id": workflow.workflow_id},
        )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

    with client.session_transaction() as sess:
        assert "access_token" not in sess
        assert workflow.workflow_id in sess["post_login_redirect"]


def test_resume_submit_requires_login(client, workflow):
    """Redirects unauthenticated users."""
    response = client.get(f"/resume_submit?workflow_id={workflow.workflow_id}")
    assert response.status_code == 302


def test_resume_submit_missing_pending_data(client, workflow):
    """Redirects when no pending submission exists."""
    with client.session_transaction() as sess:
        sess["access_token"] = "token"

    response = client.get(f"/resume_submit?workflow_id={workflow.workflow_id}")
    assert response.status_code == 302
    assert "/webform" in response.headers["Location"]


def test_do_submit_missing_workflow(client, app):
    """Rejects an unknown submission workflow."""
    with patch.object(
        app.extensions["workflow_store"],
        "get",
        side_effect=WorkflowNotFound("missing"),
    ):
        response = client.post("/do_submit?workflow_id=missing")

    assert response.status_code == 400
