#!/usr/bin/env python

import glob
import json
import os
import tempfile

from flask import current_app, request, session
from werkzeug.utils import secure_filename

from .invenio import run_record_upload
from .utils import fill_invenio_metadata, form_to_json


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


def prepare_for_invenio(form_data, tmpdir):
    """Convert form data and upload files from tmpdir to Invenio. Cleans up tmpdir.

    Args:
        form_data: Flat form data (ImmutableMultiDict or similar) from the webform submission.
        tmpdir: Path to temporary directory containing uploaded simulation files.

    Returns:
        draft_id: The Invenio draft record ID of the created upload.
    """
    import shutil

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


def save_pending_submission(json_form=None):
    """Save uploaded files and form data to a temp directory for post-login submission.

    Stores uploaded files in a new temporary directory and saves the form data and
    directory path in the Flask session so the submission can be resumed after OAuth login.
    If provided, the converted and validated BioSim metadata JSON is also saved
    there as ``biosim_metadata.json`` so it is uploaded with the record files.

    Args:
        json_form: Optional converted and validated BioSim metadata dictionary.

    Side effects:
        session["pending_form_data"]: Set to the submitted form data as a dict.
        session["pending_files_dir"]: Set to the path of the temporary directory.
    """
    tmpdir = tempfile.mkdtemp(prefix="biosimdb_pending_")
    for field in request.files:
        for file in request.files.getlist(field):
            if file.filename:
                file.save(os.path.join(tmpdir, secure_filename(file.filename)))

    if json_form is not None:
        json_path = os.path.join(tmpdir, "simulation_metadata.json")
        with open(json_path, "w") as f:
            json.dump(json_form, f, indent=2)

    session["pending_form_data"] = request.form.to_dict(flat=False)
    session["pending_files_dir"] = tmpdir
