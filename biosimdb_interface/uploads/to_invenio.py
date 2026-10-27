#!/usr/bin/env python
"""Upload helpers for deferred BioSimDB submission and Invenio transfer."""

import copy
import json
import os

from flask import current_app, session

from ..core.cancellation import is_submission_cancelled
from ..invenio.client import run_record_upload
from ..schema.invenio import INVENIO_FORM_EMPTY
from .utils import SIM_METADATA_FILENAME, pending_uploads_path


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
    path = pending_uploads_path(tmpdir)
    with open(path) as f:
        saved_files = json.load(f)
    files = [p for p in _flatten_saved_files(saved_files) if os.path.isfile(p)]
    sim_meta_path = os.path.join(tmpdir, SIM_METADATA_FILENAME)
    if os.path.isfile(sim_meta_path):
        files.append(sim_meta_path)

    return files


def _data_collections_upload(metadata_path, files_path, cancelled=lambda: False):
    """Upload metadata as a draft PSDI data-collections record.

    Args:
    metadata_path: Path to the JSON file containing record metadata.
    files_path: List of file paths to upload alongside the record.

    Returns:
    tuple: (repository, draft_id) from the Invenio upload response.
    """
    token = session.get("access_token")
    API_BASE = current_app.config["API_BASE"]
    return run_record_upload(
        api_url=API_BASE,
        api_key=token,
        metadata_path=metadata_path,
        files=files_path,
        community="biosimdb",
        cancelled=cancelled,
    )


def _fill_invenio_metadata(form_data):
    """Populate a blank Invenio record with form data.

    Args:
        form_data: Dictionary of parsed form values from form_to_json().

    Returns:
        dict: Invenio-compatible record dictionary with custom_fields populated.
    """
    invenio_data = copy.deepcopy(INVENIO_FORM_EMPTY)
    invenio_data["custom_fields"]["dsmd"] = [form_data]
    # add generated keywords
    # add generated subjects

    return invenio_data


def prepare_for_invenio(sim_metadata, tmpdir):
    """Create Invenio metadata and upload allow listed files from tmpdir.

    Args:
    form_data (ImmutableMultiDict | Mapping): Submitted webform payload.
    tmpdir (str): Temporary directory containing pending files and manifests.

    Returns:
    draft_id (str): Created Invenio draft record ID.

    Side Effects:
    Writes metadata.json in tmpdir.
    """

    invenio_data = _fill_invenio_metadata(sim_metadata)
    metadata_path = os.path.join(tmpdir, "invenio_metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(invenio_data, f, indent=2)

    file_paths = _load_pending_upload_paths(tmpdir)
    _, draft_id = _data_collections_upload(
        metadata_path, file_paths, cancelled=lambda: is_submission_cancelled(tmpdir)
    )
    return draft_id
