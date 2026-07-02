#!/usr/bin/env python

import glob
import json
import os
import shutil
import tempfile

from biosim_extractor.metadata.filemetadata import files_metadata
from flask import current_app, request, session
from werkzeug.utils import secure_filename

from .invenio import run_record_upload
from .utils import fill_invenio_metadata, form_to_json


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
    tmpdir = tempfile.mkdtemp(prefix="biosimdb_file_metadata_")
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
        session["pending_form_data"]: Set to submitted form data (dict of lists).
        session["pending_files_dir"]: Set to temporary directory path containing
            uploaded files and optional ``simulation_metadata.json``.
    """
    tmpdir = tempfile.mkdtemp(prefix="biosimdb_pending_")
    _, file_meta = _save_files_and_extract_metadata(tmpdir)

    if json_form is not None:
        json_form["files"] = file_meta
        json_path = os.path.join(tmpdir, "simulation_metadata.json")
        with open(json_path, "w") as f:
            json.dump(json_form, f, indent=2)

    session["pending_form_data"] = request.form.to_dict(flat=False)
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
        file_paths = [
            p for p in glob.glob(os.path.join(tmpdir, "*")) if p != metadata_path
        ]
        _, draft_id = _data_collections_upload(metadata_path, file_paths)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return draft_id
