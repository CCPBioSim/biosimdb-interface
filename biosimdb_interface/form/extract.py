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

from biosimdb_interface.form.errors import WebformError

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
    """
    populator = MetadataPopulator(
        schema_path=current_app.config["ENGINE_MAPPING_SCHEMA_PATH"],
        top_file=top_file,
        traj_file=traj_file,
        store_file_metadata=False,  # not on webform so exclude
    )

    result = populator.populate()
    biosimschema_path = current_app.config["BIOSIM_SCHEMA_PATH"]
    populator.validate(result, biosimschema_path, strict=True)

    return result


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


@form_bp.route("/clear_extraction", methods=["POST"])
def clear_extraction():
    """Delete only the current tab's extracted workflow files."""
    current_app.extensions["workflow_store"].delete(request.form.get("workflow_id"))
    return jsonify({"success": True})
