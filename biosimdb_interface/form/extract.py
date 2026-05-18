#!/usr/bin/env python
import os
from . import form_bp
from flask import jsonify, request
import tempfile

from biosim_extractor.schema.populateschema import SchemaPopulator

@form_bp.route("/extract_metadata", methods=["POST"])
def extract_metadata():
    try:
        print("=== DEBUG: Starting extract_metadata ===")

        topology = request.files.get(f"topology")
        trajectories = request.files.getlist(f"trajectory[]")
        
        print(f"Topology: {topology}")
        print(f"Trajectories: {trajectories}")
        
        if not topology or not trajectories:
            return jsonify({"error": "Simulation files are missing."}), 400
        
        print("Creating temp files...")
        
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(topology.filename)[1]) as topo_file, \
             tempfile.TemporaryDirectory() as temp_dir:
            
            topology.save(topo_file.name)
            traj_files = []
            
            for traj in trajectories:
                traj_path = os.path.join(temp_dir, traj.filename)
                traj.save(traj_path)
                traj_files.append(traj_path)

            print(f"Saved files - Topology: {topo_file.name}, Trajectories: {traj_files}")

            print("Creating SchemaPopulator...")
            populator = SchemaPopulator(
                schema_path=os.getenv("ENGINE_MAPPING_SCHEMA_PATH", ""),
                top_file=topo_file.name,
                traj_file=traj_files,
            )
            
            print("Calling populate()...")
            result = populator.populate()
            biosimschema_path = os.getenv("BIOSIM_SCHEMA_PATH", "")
            # result["topology"]["system_charge"]["value"] = "XXX"
            print("Validating metadata against schema...")
            validation_errors = []
            try:
                populator.validate(result, biosimschema_path, strict=True)
            except ValueError as e:
                validation_errors = str(e).splitlines()

            print(f"Result: {result}")

            if len(validation_errors) > 0:
                return jsonify({
                    "simulation_metadata": result,
                    "validation_errors": validation_errors,
                })
            else:
                return jsonify({
                    "simulation_metadata": result,
                    "message": "Metadata extracted successfully.",
                })   
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500