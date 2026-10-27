import json
from unittest.mock import MagicMock

from biosimdb_interface.invenio import client


def test_run_record_upload_calls_repository_flow(monkeypatch, tmp_path):
    """Verify record creation, multipart file upload, and community submission."""
    metadata_path = tmp_path / "metadata.json"
    metadata = {"metadata": {"title": "test"}}
    metadata_path.write_text(json.dumps(metadata))

    traj_path = tmp_path / "traj.xtc"
    traj_path.write_bytes(b"trajectory")

    session = MagicMock()
    create_response = MagicMock()
    create_response.json.return_value = {"id": "draft-123"}

    community_response = MagicMock()
    community_response.json.return_value = {"id": "community-id"}

    session.post.side_effect = [create_response, MagicMock()]
    session.get.return_value = community_response

    monkeypatch.setattr(client.requests, "Session", lambda: session)

    upload_file_mock = MagicMock(return_value="https://example.org/commit")
    monkeypatch.setattr(client, "upload_file", upload_file_mock)

    returned_repo, draft_id = client.run_record_upload(
        api_url="https://example.org/api",
        api_key="secret",
        metadata_path=metadata_path,
        files=[traj_path],
        community="my-community",
    )

    assert returned_repo is None
    assert draft_id == "draft-123"

    session.headers.update.assert_called_once_with(
        {
            "Accept": "application/json",
            "Authorization": "Bearer secret",
        }
    )
    session.post.assert_any_call(
        "https://example.org/api/records",
        json=metadata,
    )
    upload_file_mock.assert_called_once()
    assert upload_file_mock.call_args.args[1:6] == (
        "https://example.org",
        "draft-123",
        traj_path,
        "traj.xtc",
        traj_path.stat().st_size,
    )
    session.post.assert_any_call("https://example.org/commit")
    session.get.assert_called_once_with(
        "https://example.org/api/communities/my-community"
    )
    session.put.assert_called_once_with(
        "https://example.org/api/records/draft-123/draft/review",
        json={
            "receiver": {"community": "community-id"},
            "type": "community-submission",
        },
    )
