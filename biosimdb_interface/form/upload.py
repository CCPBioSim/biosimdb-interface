#!/usr/bin/env python
"""Upload helpers for deferred BioSimDB submission and Invenio transfer."""

import json
import os
import shutil

from biosim_extractor.metadata.filemetadata import file_metadata, files_metadata
from flask import current_app, request, session
from werkzeug.utils import secure_filename

from .invenio import run_record_upload
from .utils import fill_invenio_metadata, form_to_json

PENDING_FORM_FILENAME = "pending_form_data.json"
PENDING_UPLOADS_FILENAME = "pending_uploads.json"
SIM_METADATA_FILENAME = "simulation_metadata.json"
PENDING_FILE_META_FILENAME = "pending_file_meta.json"
CANCELLED_FLAG_FILENAME = "CANCELLED"


def _pending_file_meta_path(tmpdir):
    return os.path.join(tmpdir, PENDING_FILE_META_FILENAME)


def _save_pending_file_meta(tmpdir, file_meta):
    with open(_pending_file_meta_path(tmpdir), "w") as f:
        json.dump(file_meta, f)


def _load_pending_file_meta(tmpdir):
    path = _pending_file_meta_path(tmpdir)
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_extracted_files(tmpdir):
    """Return topology and trajectory paths cached during extraction."""
    with open(_pending_uploads_path(tmpdir)) as f:
        saved_files = json.load(f)

    topology = saved_files.get("topology", [])
    trajectories = saved_files.get("trajectory", [])

    return (
        topology[0] if topology else None,
        trajectories,
    )


def cache_extracted_files(tmpdir, saved_files):
    """Persist extracted file paths and file metadata inside one workflow directory."""
    file_meta = files_metadata(saved_files)

    with open(_pending_uploads_path(tmpdir), "w") as f:
        json.dump(saved_files, f)
    _save_pending_file_meta(tmpdir, file_meta)

    return file_meta


def verify_cached_file_meta(tmpdir):
    """Verify tmpdir files against cached hashes from pending_file_meta.json.

    Returns:
        tuple[bool, str | None]: (is_valid, error_message)
    """
    cached = _load_pending_file_meta(tmpdir)
    if not cached:
        return False, "Missing cached file metadata. Please extract metadata again."

    for item in cached:
        role = item.get("file_role")
        name = item.get("file_name")
        expected_hash = item.get("file_hash")
        algo = item.get("file_hash_algorithm", "md5")

        if role not in ("topology", "trajectory") or not name or not expected_hash:
            continue

        path = os.path.join(tmpdir, name)
        if not os.path.isfile(path):
            return False, f"Missing file in submission directory: {name}"

        current = file_metadata(path, role=role, hash_algorithm=algo)
        if current["file_hash"] != expected_hash:
            return False, f"File changed since extraction: {name}"

    return True, None


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
    sim_meta_path = os.path.join(tmpdir, SIM_METADATA_FILENAME)
    if os.path.isfile(sim_meta_path):
        files.append(sim_meta_path)

    return files


def _paths_are_reusable(tmpdir, topo_path, traj_paths):
    """Check whether previously saved simulation paths can be reused safely.

    A path set is reusable when:
    - topology and trajectory paths are present,
    - each path exists as a file, and
    - each path is located under tmpdir.

    Args:
        tmpdir (str): Temporary directory expected to contain saved files.
        topo_path (str | None): Saved topology file path.
        traj_paths (list[str] | None): Saved trajectory file paths.

    Returns:
        bool: True if all paths are valid and under tmpdir; otherwise False.
    """
    if not topo_path or not traj_paths:
        return False

    tmpdir_abs = os.path.abspath(tmpdir)
    all_paths = [topo_path, *traj_paths]

    for path in all_paths:
        if not path or not os.path.isfile(path):
            return False
        path_abs = os.path.abspath(path)
        if os.path.commonpath([tmpdir_abs, path_abs]) != tmpdir_abs:
            return False

    return True


def _save_request_files(tmpdir):
    """Save uploaded request files into tmpdir, or reuse existing saved files.

    Reuses session-stored paths when they still point to valid files under
    tmpdir. Otherwise saves files from request.files, grouping by role.

    Notes:
        The HTML field name trajectory[] is normalized to the "trajectory" role.

    Args:
        tmpdir (str): Temporary directory where uploaded files are stored.

    Returns:
        dict[str, list[str]]: Mapping of file role to saved file paths.
    """
    # topo_path = session.get("topo_path")
    # traj_files = session.get("traj_files") or []

    topo_path, traj_files = load_extracted_files(tmpdir)

    if _paths_are_reusable(tmpdir, topo_path, traj_files):
        return {
            "topology": [topo_path],
            "trajectory": traj_files,
        }

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


def extract_uploaded_file_metadata(tmpdir):
    """Extract metadata for uploaded simulation files.

    Reuses cached pending_file_meta.json when present, otherwise saves or
    reuses uploaded files and computes metadata.

    Args:
        tmpdir (str): Temporary directory where uploaded files are stored.

    Returns:
        list[dict]: Extracted metadata records for uploaded files.
    """
    cached = _load_pending_file_meta(tmpdir)
    if cached is not None:
        return cached

    try:
        _, file_meta = _save_files_and_extract_metadata(tmpdir)
        _save_pending_file_meta(tmpdir, file_meta)
        return file_meta
    finally:
        for field in request.files:
            for file in request.files.getlist(field):
                file.stream.seek(0)


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


def cleanup_tmpdir(tmpdir):
    """Remove a temporary submission directory if it exists.

    Args:
    tmpdir (str | None): Directory path to delete.
    """
    if tmpdir and os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir, ignore_errors=True)


def save_pending_submission(json_form, tmpdir):
    """Persist validated submission data in the given workflow directory."""
    file_meta = _load_pending_file_meta(tmpdir) or []

    json_form["files"] = file_meta
    with open(os.path.join(tmpdir, SIM_METADATA_FILENAME), "w") as f:
        json.dump(json_form, f, indent=2)

    with open(_pending_form_path(tmpdir), "w") as f:
        form_values = request.form.to_dict(flat=False)
        form_values.pop("workflow_id", None)

        json.dump(form_values, f)


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


def mark_submission_cancelled(tmpdir):
    """Signal an in-flight do_submit to stop, without touching its files."""
    if tmpdir and os.path.isdir(tmpdir):
        open(os.path.join(tmpdir, CANCELLED_FLAG_FILENAME), "w").close()


def is_submission_cancelled(tmpdir):
    return bool(tmpdir) and os.path.isfile(
        os.path.join(tmpdir, CANCELLED_FLAG_FILENAME)
    )
