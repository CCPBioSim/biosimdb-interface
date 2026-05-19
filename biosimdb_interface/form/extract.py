#!/usr/bin/env python
"""
Metadata extraction endpoint.

Receives uploaded topology and trajectory files, extracts simulation metadata
using :class:`biosim_extractor.schema.populatemetadata.MetadataPopulator`, and
optionally validates the result against the BioSim schema.
"""

import os
import tempfile

from biosim_extractor.schema.populatemetadata import MetadataPopulator
from flask import jsonify, request

from . import form_bp


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

        with (
            tempfile.NamedTemporaryFile(
                suffix=os.path.splitext(topology.filename)[1]
            ) as topo_file,
            tempfile.TemporaryDirectory() as temp_dir,
        ):
            topology.save(topo_file.name)
            traj_files = []

            for traj in trajectories:
                traj_path = os.path.join(temp_dir, traj.filename)
                traj.save(traj_path)
                traj_files.append(traj_path)

            populator = MetadataPopulator(
                schema_path=os.getenv("ENGINE_MAPPING_SCHEMA_PATH", ""),
                top_file=topo_file.name,
                traj_file=traj_files,
            )

            result = populator.populate()
            biosimschema_path = os.getenv("BIOSIM_SCHEMA_PATH", "")
            validation_errors = []
            try:
                populator.validate(result, biosimschema_path, strict=True)
            except ValueError as e:
                validation_errors = str(e).splitlines()

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

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
