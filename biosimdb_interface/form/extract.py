#!/usr/bin/env python
"""
Metadata extraction endpoint.

Receives uploaded topology and trajectory files, extracts simulation metadata
using :class:`biosim_extractor.metadata.populatemetadata.MetadataPopulator`, and
optionally validates the result against the BioSim schema.
"""

import os

from biosim_extractor.metadata.populatemetadata import MetadataPopulator
from flask import current_app, jsonify, request
from werkzeug.utils import secure_filename

from . import form_bp
from .upload import cache_extracted_files
from .workflows import WorkflowNotFound


def extract_files_validate(top_file, traj_file):
    """Extract metadata from simulation files and validate against the schema.

    Args:
        top_file (str): Path to the topology file.
        traj_file (str or list[str]): Path or list of paths to the trajectory file(s).

    Returns:
        tuple: A tuple containing:
            - result (dict): The extracted and populated metadata dictionary.
            - validation_errors (list[str]): A list of validation error messages,
              empty if validation succeeded.
    """
    populator = MetadataPopulator(
        schema_path=os.getenv("ENGINE_MAPPING_SCHEMA_PATH", ""),
        top_file=top_file,
        traj_file=traj_file,
        store_file_metadata=False,  # not on webform so exclude
    )

    result = populator.populate()
    biosimschema_path = os.getenv("BIOSIM_SCHEMA_PATH", "")
    validation_errors = []
    try:
        populator.validate(result, biosimschema_path, strict=True)
    except ValueError as e:
        validation_errors = str(e).splitlines()

    return result, validation_errors


@form_bp.route("/extract_metadata", methods=["POST"])
def extract_metadata():
    """Extract simulation metadata from uploaded topology and trajectory files.
    This is where the tmpdir for the files is created.

    Expects a multipart POST with:
        - ``topology``: a single topology file.
        - ``trajectory[]``: one or more trajectory files.

    Files are saved to temporary paths, passed to :class:`MetadataPopulator`,
    and the result is validated against the schema at ``BIOSIM_SCHEMA_PATH``.

    Returns:
        JSON response with one of:
        - ``{"simulation_metadata": ..., "message": "..."}`` on success.
        - ``{"simulation_metadata": ..., "validation_errors": [...]}`` if schema validation fails.
        - ``{"error": "..."}`` with status 400 if files are missing, or 500 on unexpected error.
    """
    workflow_id = request.form.get("workflow_id")
    topology = request.files.get("topology")
    trajectories = request.files.getlist("trajectory[]")

    if not topology or not trajectories:
        return jsonify({"error": "Simulation files are missing."}), 400

    try:
        workflow = current_app.extensions["workflow_store"].reset(workflow_id)
    except WorkflowNotFound as exc:
        return jsonify({"error": str(exc)}), 400

    tmpdir = workflow.tmpdir

    try:
        topology = request.files.get("topology")
        trajectories = request.files.getlist("trajectory[]")

        if not topology or not trajectories:
            return jsonify({"error": "Simulation files are missing."}), 400

        topo_path = os.path.join(tmpdir, secure_filename(topology.filename))
        topology.save(topo_path, buffer_size=16 * 1024 * 1024)  # 16 MB chunks

        traj_files = []
        for traj in trajectories:
            traj_path = os.path.join(tmpdir, secure_filename(traj.filename))
            traj.save(traj_path, buffer_size=16 * 1024 * 1024)
            traj_files.append(traj_path)

        saved_files = {"topology": [topo_path], "trajectory": traj_files}
        cache_extracted_files(tmpdir, saved_files)

        result, validation_errors = extract_files_validate(topo_path, traj_files)

        if validation_errors:
            return jsonify(
                {
                    "simulation_metadata": result,
                    "validation_errors": validation_errors,
                }
            )
        else:
            return jsonify(
                {
                    "simulation_metadata": result,
                    "message": "Metadata extracted successfully.",
                }
            )

    except Exception as e:
        current_app.extensions["workflow_store"].delete(workflow_id)
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@form_bp.route("/clear_extraction", methods=["POST"])
def clear_extraction():
    """Delete only the current tab's extracted workflow files."""
    current_app.extensions["workflow_store"].delete(request.form.get("workflow_id"))
    return jsonify({"success": True})
