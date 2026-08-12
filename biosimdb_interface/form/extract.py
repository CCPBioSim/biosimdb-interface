#!/usr/bin/env python
"""
Metadata extraction endpoint.

Receives uploaded topology and trajectory files, extracts simulation metadata
using :class:`biosim_extractor.metadata.populatemetadata.MetadataPopulator`, and
optionally validates the result against the BioSim schema.
"""

import os
import shutil

from biosim_extractor.metadata.populatemetadata import MetadataPopulator
from flask import jsonify, request

from . import form_bp
from .utils import make_upload_tmpdir


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
    try:
        topology = request.files.get("topology")
        trajectories = request.files.getlist("trajectory[]")

        if not topology or not trajectories:
            return jsonify({"error": "Simulation files are missing."}), 400

        temp_dir = make_upload_tmpdir("biosimdb_extract_")
        try:
            topo_path = os.path.join(temp_dir, topology.filename)
            topology.save(topo_path)
            traj_files = []

            for traj in trajectories:
                traj_path = os.path.join(temp_dir, traj.filename)
                traj.save(traj_path)
                traj_files.append(traj_path)

            result, validation_errors = extract_files_validate(topo_path, traj_files)

            # Keep authoritative extracted payload on the server
            # session["extracted_metadata"] = result

            if len(validation_errors) > 0:
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
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
