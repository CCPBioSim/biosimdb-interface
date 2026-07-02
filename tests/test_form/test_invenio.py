from pathlib import Path
from unittest.mock import MagicMock

from biosimdb_interface.form import invenio


def test_create_files_dict_expands_globs(tmp_path):
    file_a = tmp_path / "a.file"
    file_a.write_text("a")

    subdir = tmp_path / "example"
    subdir.mkdir()
    file_b = subdir / "b.cif"
    file_b.write_text("b")

    patterns = [str(tmp_path / "*.file"), str(tmp_path / "example" / "*.cif")]
    result = invenio.create_files_dict(patterns)

    assert result["a.file"] == file_a
    assert result["b.cif"] == file_b
    assert set(result.keys()) == {"a.file", "b.cif"}


def test_create_files_dict_returns_empty_for_no_matches(tmp_path):
    patterns = [str(tmp_path / "*.does_not_exist")]
    result = invenio.create_files_dict(patterns)
    assert result == {}


def test_run_record_upload_calls_repository_flow(monkeypatch, tmp_path):
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text("{}")

    loaded_metadata = {"metadata": {"title": "test"}}
    files_dict = {"traj.xtc": Path("/tmp/traj.xtc")}

    loader = MagicMock(return_value=loaded_metadata)
    repo = MagicMock()

    created_draft = MagicMock()
    created_draft.get.return_value = {"id": "draft-123"}
    repo.depositions.create.return_value = created_draft

    draft_api = repo.depositions.draft.return_value

    monkeypatch.setattr(invenio, "InvenioRepository", lambda url, api_key: repo)
    monkeypatch.setattr(invenio, "get_loader", lambda _fmt: loader)
    monkeypatch.setattr(invenio, "create_files_dict", lambda _files: files_dict)

    returned_repo, draft_id = invenio.run_record_upload(
        api_url="https://example.org",
        api_key="secret",
        metadata_path=metadata_path,
        metadata_format="json",
        files=["*.xtc"],
        community="my-community",
    )

    assert returned_repo is repo
    assert draft_id == "draft-123"

    loader.assert_called_once_with(metadata_path)
    repo.depositions.create.assert_called_once_with()
    draft_api.update.assert_called_once_with(loaded_metadata)
    draft_api.files.upload.assert_called_once_with(files_dict)
    draft_api.bind.assert_called_once_with("my-community")
