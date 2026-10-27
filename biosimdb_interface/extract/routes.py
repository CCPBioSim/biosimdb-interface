#!/usr/bin/env python
"""
Simulation files metadata extraction endpoint.
"""

from flask import current_app, jsonify, request

from biosimdb_interface.core.errors import WebformError

from ..core.workflows import WorkflowNotFound
from ..uploads.to_server import cache_extracted_files, upload_files_to_server
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

    topo_path, traj_file_paths = upload_files_to_server(tmpdir, topology, trajectories)

    saved_files = {"topology": [topo_path], "trajectory": traj_file_paths}
    cache_extracted_files(tmpdir, saved_files)

    result = extract_files_validate(topo_path, traj_file_paths)

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
