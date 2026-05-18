#!/usr/bin/env python

from flask import request
import tempfile
from werkzeug.utils import secure_filename
import os
from MDAnalysis import Universe
import shutil

def validate_with_mdanalysis():
    """Validate uploaded topology and trajectory files using MDAnalysis.

    Saves uploaded files to a temporary directory, attempts to load them
    with MDAnalysis, then resets file streams for downstream processing.
    Skips validation if no topology file is uploaded.

    Returns:
        None if the files are valid or no files were uploaded.
        str: Error message if MDAnalysis cannot read the files.
    """
    topology = request.files.get("topology")
    trajectories = [f for f in request.files.getlist("trajectory[]") if f.filename]
    if not topology or not topology.filename or len(trajectories) == 0:
        return "Please upload a topology and trajectory files before saving or submitting."
        # return None  # no files uploaded, skip validation
    tmpdir = tempfile.mkdtemp()
    try:
        top_path = os.path.join(tmpdir, secure_filename(topology.filename))
        topology.save(top_path)
        traj_paths = []
        for traj in trajectories:
            p = os.path.join(tmpdir, secure_filename(traj.filename))
            traj.save(p)
            traj_paths.append(p)
        Universe(top_path, *traj_paths)
        return None
    except Exception as e:
        return str(e)
    finally:
        topology.stream.seek(0)
        for traj in trajectories:
            traj.stream.seek(0)
        shutil.rmtree(tmpdir, ignore_errors=True)