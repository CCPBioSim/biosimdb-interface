#!/usr/bin/env python
"""
Simulation files metadata extraction endpoint.
"""

from flask import current_app, jsonify, request

from biosimdb_interface.core.errors import WebformError

from ..core.workflows import WorkflowNotFound
from ..uploads.chunked import UploadError, resolve_uploaded_file
from ..uploads.to_server import cache_extracted_files
from . import extract_bp
from .services import extract_files_validate


@extract_bp.route("/extract_metadata", methods=["POST"])
def extract_metadata():
    """Extract simulation metadata from files already uploaded in chunks.

    Expects a form POST with ``workflow_id``, ``topology_name`` and one or
    more ``trajectory_names[]`` (names returned by the chunked upload).

    Returns:
        JSON response:
        - ``{"simulation_metadata": ..., "message": "..."}``
    """
    topo_name = request.form.get("topology_name")
    traj_names = request.form.getlist("trajectory_names[]")

    if not topo_name or not traj_names:
        raise WebformError("Simulation files are missing!", status_code=404)

    try:
        workflow = current_app.extensions["workflow_store"].get(
            request.form.get("workflow_id")
        )
        tmpdir = workflow.tmpdir
        topo_path = resolve_uploaded_file(tmpdir, topo_name)
        traj_file_paths = [resolve_uploaded_file(tmpdir, n) for n in traj_names]
    except WorkflowNotFound as exc:
        return jsonify({"Workflow error": str(exc)}), 400
    except UploadError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

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
