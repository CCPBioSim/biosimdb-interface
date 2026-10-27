#!/usr/bin/env python

from MDAnalysis import Universe


def validate_with_mdanalysis(topology_path, trajectory_paths):
    """Validate saved simulation files using MDAnalysis.

    Args:
        topology_path (str): Path to the topology file.
        trajectory_paths (list[str]): Paths to one or more trajectory files.

    Returns:
        None: If the topology and trajectories are valid.
        str: An error message if the files cannot be read by MDAnalysis or
            if required paths are missing.
    """
    if not topology_path or not trajectory_paths:
        return (
            "Please upload a topology and trajectory files before saving or submitting."
        )

    try:
        Universe(topology_path, *trajectory_paths)
    except Exception as exc:
        return str(exc)

    return None
