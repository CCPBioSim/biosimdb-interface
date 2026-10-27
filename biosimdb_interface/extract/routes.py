#!/usr/bin/env python
"""
Metadata extraction endpoint.
"""

import os

from flask import current_app, jsonify, request
from werkzeug.utils import secure_filename

from biosimdb_interface.core.errors import WebformError

from ..core.workflows import WorkflowNotFound
from ..uploads.to_server import cache_extracted_files
from . import extract_bp
from .services import extract_files_validate


@extract_bp.route("/extract_metadata", methods=["POST"])
def extract_metadata():
    """Extract simulation metadata from uploaded topology and trajectory files.
    This is where the tmpdir for the files is created.

    Expects a multipart POST with:
        - ``topology``: a single topology file.
        - ``trajectory[]``: one or more trajectory files.

    Returns:
        JSON response:
        - ``{"simulation_metadata": ..., "message": "..."}``
    """
    workflow_id = request.form.get("workflow_id")
    topology = request.files.get("topology")
    trajectories = request.files.getlist("trajectory[]")

    if not topology or not trajectories:
        raise WebformError("Simulation files are missing!", status_code=404)

    try:
        workflow = current_app.extensions["workflow_store"].reset(workflow_id)
    except WorkflowNotFound as exc:
        return jsonify({"Workflow error": str(exc)}), 400

    tmpdir = workflow.tmpdir

    topo_path = os.path.join(tmpdir, secure_filename(topology.filename))
    topology.save(topo_path, buffer_size=16 * 1024 * 1024)  # 16 MB chunks

    traj_files = []
    for traj in trajectories:
        traj_path = os.path.join(tmpdir, secure_filename(traj.filename))
        traj.save(traj_path, buffer_size=16 * 1024 * 1024)
        traj_files.append(traj_path)

    saved_files = {"topology": [topo_path], "trajectory": traj_files}
    cache_extracted_files(tmpdir, saved_files)

    result = extract_files_validate(topo_path, traj_files)

    return jsonify(
        {
            "simulation_metadata": result,
            "message": "Metadata extracted successfully.",
        }
    )


@extract_bp.route("/clear_extraction", methods=["POST"])
def clear_extraction():
    """Delete only the current tab's extracted workflow files."""
    current_app.extensions["workflow_store"].delete(request.form.get("workflow_id"))
    return jsonify({"success": True})
