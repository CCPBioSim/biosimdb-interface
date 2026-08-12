#!/usr/bin/env python

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
    return os.path.join(tmpdir, PENDING_FORM_FILENAME)


def _pending_uploads_path(tmpdir):
    return os.path.join(tmpdir, PENDING_UPLOADS_FILENAME)


def _flatten_saved_files(saved_files):
    return [p for paths in saved_files.values() for p in paths]


def _load_pending_upload_paths(tmpdir):
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
    """Save uploaded files and form data for deferred post-login submission.

    Writes uploaded request files to a new temporary directory, computes file
    metadata from those saved files, and stores pending submission state in the
    Flask session so submission can resume after OAuth login.

    If ``json_form`` is provided, this function attaches the computed file
    metadata under ``json_form["files"]`` and writes the result to
    ``simulation_metadata.json`` in the temporary directory.

    Args:
        json_form: Optional converted/validated BioSim metadata dictionary to
        persist alongside uploaded files. When provided, file metadata is
        added before writing.

    Side effects:
        session["pending_files_dir"]: Set to temporary directory path containing
        uploaded files plus persisted JSON payloads used after login.
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
    """Convert form data and upload files from tmpdir to Invenio. Cleans up tmpdir.

    Args:
        form_data: Flat form data (ImmutableMultiDict or similar) from the webform submission.
        tmpdir: Path to temporary directory containing uploaded simulation files.

    Returns:
        draft_id: The Invenio draft record ID of the created upload.
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
