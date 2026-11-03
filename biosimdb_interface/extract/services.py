#!/usr/bin/env python
"""
Metadata extraction services
"""

from biosim_extractor.metadata.populatemetadata import MetadataPopulator
from flask import current_app


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
    current_app.logger.debug("Metadata populator created")

    result = populator.populate()
    current_app.logger.debug("Metadata extracted")
    biosimschema_path = current_app.config["BIOSIM_SCHEMA_PATH"]
    populator.validate(result, biosimschema_path, strict=True)
    current_app.logger.debug("Metadata validated")

    return result
