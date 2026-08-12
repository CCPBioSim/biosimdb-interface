#!/usr/bin/env python
"""Upload helpers for deferred BioSimDB submission and Invenio transfer."""

import json
import os
import shutil

from biosim_extractor.metadata.filemetadata import files_metadata
from flask import current_app, request, session
from werkzeug.utils import secure_filename

from .invenio import run_record_upload
from .utils import fill_invenio_metadata, form_to_json, make_upload_tmpdir

PENDING_FORM_FILENAME = "pending_form_data.json"
PENDING_UPLOADS_FILENAME = "pending_uploads.json"
SIM_METADATA_FILENAME = "simulation_metadata.json"

INTERNAL_TMP_FILENAMES = {
    PENDING_FORM_FILENAME,
    PENDING_UPLOADS_FILENAME,
    "metadata.json",
}


def _pending_form_path(tmpdir):
    """Return the path to the persisted pending form payload JSON.

    Args:
    tmpdir (str): Temporary directory containing pending submission artifacts.

    Returns:
    str: Path to file.
    """
    return os.path.join(tmpdir, PENDING_FORM_FILENAME)


def _pending_uploads_path(tmpdir):
    """Return the path to the persisted uploaded-files manifest JSON.

    Args:
    tmpdir (str): Temporary directory containing pending submission artifacts.

    Returns:
    str: Path to file.
    """
    return os.path.join(tmpdir, PENDING_UPLOADS_FILENAME)


def _flatten_saved_files(saved_files):
    """Flatten a role-to-path mapping into a single file path list.

    Args:
    saved_files (dict[str, list[str]]): Mapping of file role to saved file paths.

    Returns:
    list[str]: Flattened list of saved file paths.
    """
    return [p for paths in saved_files.values() for p in paths]


def _load_pending_upload_paths(tmpdir):
    """Load allowed upload file paths for deferred submission.

    Reads the persisted uploads manifest and returns existing files only.
    If simulation_metadata.json exists, it is appended to the upload list.

    Args:
    tmpdir (str): Temporary directory containing pending submission artifacts.

    Returns:
    list[str]: File paths that should be uploaded to Invenio.

    Raises:
    FileNotFoundError: If pending_uploads.json is missing.
    json.JSONDecodeError: If pending_uploads.json is not valid JSON.
    """
    path = _pending_uploads_path(tmpdir)
    with open(path) as f:
        saved_files = json.load(f)
    files = [p for p in _flatten_saved_files(saved_files) if os.path.isfile(p)]

    # Optional: keep this if simulation_metadata.json must be included in record files
    sim_meta_path = os.path.join(tmpdir, SIM_METADATA_FILENAME)
    if os.path.isfile(sim_meta_path):
        files.append(sim_meta_path)

    return files


def _save_request_files(tmpdir):
    """Save uploaded request files into a temporary directory grouped by role.

    Maps the trajectory[] field to trajectory and keeps other field names as roles.

    Args:
        tmpdir: Path to the temporary directory where uploaded files are written.

    Returns:
        Dictionary mapping file roles to lists of saved file paths.
    """
    saved_files = {"topology": [], "trajectory": []}
    for field in request.files:
        role = "trajectory" if field == "trajectory[]" else field
        for file in request.files.getlist(field):
            if file.filename:
                path = os.path.join(tmpdir, secure_filename(file.filename))
                file.save(path)
                saved_files.setdefault(role, []).append(path)
    return saved_files


def _save_files_and_extract_metadata(tmpdir):
    """Save uploaded request files and compute file metadata in one step.

    Args:
        tmpdir: Path to the temporary directory where uploaded files are written.

    Returns:
        Tuple of:
        - saved_files: Dictionary of role to saved file paths.
        - file_meta: List of extracted file metadata dictionaries.
    """
    saved_files = _save_request_files(tmpdir)
    file_meta = files_metadata(saved_files)
    return saved_files, file_meta


def extract_uploaded_file_metadata():
    """Extract file metadata from the current request's uploaded files."""
    tmpdir = make_upload_tmpdir("biosimdb_file_metadata_")
    try:
        _, file_meta = _save_files_and_extract_metadata(tmpdir)
        return file_meta
    finally:
        for field in request.files:
            for file in request.files.getlist(field):
                file.stream.seek(0)
        shutil.rmtree(tmpdir, ignore_errors=True)


def _data_collections_upload(metadata_path, files_path):
    """Upload metadata as a draft PSDI data-collections record.

    Args:
        metadata_path: Path to the JSON file containing record metadata.
        files_path: List of file paths to upload alongside the record.

    Returns:
        tuple: (repository, draft_id) from the Invenio upload response.
    """
    token = session.get("access_token")
    API_BASE = current_app.config["API_BASE"]
    repository, draft_id = run_record_upload(
        api_url=API_BASE,
        api_key=token,
        metadata_path=metadata_path,
        metadata_format="json",
        files=files_path,
        community="biosimdb",
    )
    return repository, draft_id


def save_pending_submission(json_form=None):
    """Persist uploaded files and form payload for post-login submission resume.

    Saves uploaded request files into a temp directory, writes a manifest of
    allowed upload paths, optionally writes simulation_metadata.json, and stores
    the form payload as pending_form_data.json.

    Args:
    json_form (dict | None): Validated BioSim metadata to persist. When
    provided, file metadata is attached at json_form["files"] before
    writing simulation_metadata.json.

    Side Effects:
    Writes JSON artifacts under tmpdir.
    Sets session["pending_files_dir"].
    """
    tmpdir = make_upload_tmpdir("biosimdb_pending_")
    saved_files, file_meta = _save_files_and_extract_metadata(tmpdir)

    # Persist exact user-uploaded paths for later allowlist upload
    with open(_pending_uploads_path(tmpdir), "w") as f:
        json.dump(saved_files, f)

    if json_form is not None:
        json_form["files"] = file_meta
        json_path = os.path.join(tmpdir, SIM_METADATA_FILENAME)
        with open(json_path, "w") as f:
            json.dump(json_form, f, indent=2)

    with open(_pending_form_path(tmpdir), "w") as f:
        json.dump(request.form.to_dict(flat=False), f)

    session["pending_files_dir"] = tmpdir


def prepare_for_invenio(form_data, tmpdir):
    """Create Invenio metadata and upload allowlisted files from tmpdir.

    Args:
    form_data (ImmutableMultiDict | Mapping): Submitted webform payload.
    tmpdir (str): Temporary directory containing pending files and manifests.

    Returns:
    draft_id (str): Created Invenio draft record ID.

    Side Effects:
    Writes metadata.json in tmpdir.
    Deletes tmpdir on exit.
    """
    try:
        json_form = form_to_json(form_data)
        invenio_data = fill_invenio_metadata(json_form)
        metadata_path = os.path.join(tmpdir, "metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(invenio_data, f, indent=2)

        file_paths = _load_pending_upload_paths(tmpdir)
        _, draft_id = _data_collections_upload(metadata_path, file_paths)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return draft_id
