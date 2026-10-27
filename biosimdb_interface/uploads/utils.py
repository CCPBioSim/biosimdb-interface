#!/usr/bin/env python
"""Upload helpers for deferred BioSimDB submission and Invenio transfer."""

import json
import os

PENDING_FORM_FILENAME = "pending_form_data.json"
PENDING_UPLOADS_FILENAME = "pending_uploads.json"
SIM_METADATA_FILENAME = "simulation_metadata.json"
PENDING_FILE_META_FILENAME = "pending_file_meta.json"
# CANCELLED_FLAG_FILENAME = "CANCELLED"


def pending_uploads_path(tmpdir):
    """Return the path to the persisted uploaded-files manifest JSON.

    Args:
    tmpdir (str): Temporary directory containing pending submission artifacts.

    Returns:
    str: Path to file.
    """
    return os.path.join(tmpdir, PENDING_UPLOADS_FILENAME)


def load_extracted_files(tmpdir):
    """Return topology and trajectory paths cached during extraction."""
    with open(pending_uploads_path(tmpdir)) as f:
        saved_files = json.load(f)

    topology = saved_files.get("topology", [])
    trajectories = saved_files.get("trajectory", [])

    return (
        topology[0] if topology else None,
        trajectories,
    )
