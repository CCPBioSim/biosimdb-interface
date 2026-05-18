#!/usr/bin/env python

import os
import glob
import json
import tempfile
from werkzeug.utils import secure_filename

from flask import session, current_app, request

from .invenio import run_record_upload
from .utils import form_to_json, fill_invenio_metadata


def _data_collections_upload(metadata_path, files_path):
    """Upload metadata as a draft PSDI data-collections record.

    Args:
        metadata_path: Path to the JSON file containing record metadata.
        files_path: List of file paths to upload alongside the record.

    Returns:
        tuple: (repository, draft_id) from the Invenio upload response.
    """
    token = session.get("access_token")
    API_BASE = current_app.config['API_BASE']
    repository, draft_id = run_record_upload(
        api_url=API_BASE, api_key=token, metadata_path=metadata_path, metadata_format="json", files=files_path, community="biosimdb",
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
        file_paths = [p for p in glob.glob(os.path.join(tmpdir, "*")) if p != metadata_path]
        _, draft_id = _data_collections_upload(metadata_path, file_paths)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return draft_id


def save_pending_submission():
    """
    Save uploaded files and form data to a temp directory for post-login submission.
    """
    tmpdir = tempfile.mkdtemp(prefix="biosimdb_pending_")
    for field in request.files:
        for file in request.files.getlist(field):
            if file.filename:
                file.save(os.path.join(tmpdir, secure_filename(file.filename)))
    session["pending_form_data"] = request.form.to_dict(flat=False)
    session["pending_files_dir"] = tmpdir
