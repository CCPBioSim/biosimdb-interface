from biosimdb_interface.core.utils import (
    cleanup_tmpdir,
    make_upload_tmpdir,
    remove_empty_fields,
)


def test_make_upload_tmpdir_creates_directory(app, tmp_path):
    """Creates a prefixed temporary directory under the configured upload folder."""
    upload_root = tmp_path / "uploads"
    app.config["UPLOAD_FOLDER"] = str(upload_root)

    with app.app_context():
        tmpdir = make_upload_tmpdir("submission_")

    assert tmpdir.startswith(str(upload_root))
    assert tmpdir.split("/")[-1].startswith("submission_")
    assert (upload_root / tmpdir.split("/")[-1]).is_dir()


def test_cleanup_tmpdir_removes_existing_directory(tmp_path):
    """Removes an existing temporary directory."""
    tmpdir = tmp_path / "submission"
    tmpdir.mkdir()

    cleanup_tmpdir(str(tmpdir))

    assert not tmpdir.exists()


def test_cleanup_tmpdir_ignores_missing_or_empty_path(tmp_path):
    """Does nothing when the path is empty or does not exist."""
    cleanup_tmpdir(None)
    cleanup_tmpdir(str(tmp_path / "missing"))


def test_remove_empty_fields_returns_non_dict_unchanged():
    """Returns non-dictionary input unchanged."""
    value = ["", None]

    assert remove_empty_fields(value) is value


def test_remove_empty_fields_cleans_nested_dicts_and_lists():
    """Removes empty values recursively while preserving populated values."""
    data = {
        "keep": "value",
        "empty_string": "",
        "none_value": None,
        "empty_dict": {},
        "nested": {"remove": None},
        "items": [
            None,
            "",
            {},
            {"remove": ""},
            {"keep": "nested value", "nested": {"remove": ""}},
        ],
        "zero": 0,
    }

    assert remove_empty_fields(data) == {
        "keep": "value",
        "items": [{"keep": "nested value"}],
        "zero": 0,
    }
