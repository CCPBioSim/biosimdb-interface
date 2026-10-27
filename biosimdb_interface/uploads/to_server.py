#!/usr/bin/env python
"""Upload helpers for deferred BioSimDB submission and Invenio transfer."""

import json
import os

from biosim_extractor.metadata.filemetadata import file_metadata, files_metadata
from flask import request
from werkzeug.utils import secure_filename

from .utils import (
    PENDING_FILE_META_FILENAME,
    PENDING_FORM_FILENAME,
    SIM_METADATA_FILENAME,
    load_extracted_files,
    pending_uploads_path,
)


def _pending_file_meta_path(tmpdir):
    """Build the path to the cached file metadata JSON.

    Args:
        tmpdir (str): Workflow directory containing submission artifacts.

    Returns:
        str: Path to the pending file metadata file.
    """
    return os.path.join(tmpdir, PENDING_FILE_META_FILENAME)


def _save_pending_file_meta(tmpdir, file_meta):
    """Write extracted file metadata to the workflow directory.

    Args:
        tmpdir (str): Workflow directory for submission artifacts.
        file_meta (list[dict]): Metadata records to persist.
    """
    with open(_pending_file_meta_path(tmpdir), "w") as f:
        json.dump(file_meta, f)


def _load_pending_file_meta(tmpdir):
    """Load cached file metadata when it exists.

    Args:
        tmpdir (str): Workflow directory containing submission artifacts.

    Returns:
        list[dict] | None: Cached metadata, or ``None`` if the cache file is
        missing.

    Raises:
        json.JSONDecodeError: If the cache file contains invalid JSON.
    """
    path = _pending_file_meta_path(tmpdir)
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return json.load(f)


def _pending_form_path(tmpdir):
    """Return the path to the persisted pending form payload JSON.

    Args:
    tmpdir (str): Temporary directory containing pending submission artifacts.

    Returns:
    str: Path to file.
    """
    return os.path.join(tmpdir, PENDING_FORM_FILENAME)


def cache_extracted_files(tmpdir, saved_files):
    """Persist extracted file paths and file metadata inside one workflow directory."""
    file_meta = files_metadata(saved_files)

    with open(pending_uploads_path(tmpdir), "w") as f:
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


def save_pending_submission(json_form, tmpdir):
    """Persist validated metadata and submitted form values for later upload.

    Adds cached file metadata to ``json_form``, then writes the simulation
    metadata and form values into the workflow directory. Requires an active
    Flask request context.
    """
    file_meta = _load_pending_file_meta(tmpdir) or []

    json_form["files"] = file_meta
    with open(os.path.join(tmpdir, SIM_METADATA_FILENAME), "w") as f:
        json.dump(json_form, f, indent=2)

    with open(_pending_form_path(tmpdir), "w") as f:
        form_values = request.form.to_dict(flat=False)
        form_values.pop("workflow_id", None)
        json.dump(form_values, f)
