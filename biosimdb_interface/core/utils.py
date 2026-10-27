#!/usr/bin/env python

import os
import shutil
import tempfile

from flask import current_app


def make_upload_tmpdir(prefix):
    upload_root = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_root, exist_ok=True)
    return tempfile.mkdtemp(prefix=prefix, dir=upload_root)


def cleanup_tmpdir(tmpdir):
    """Remove a temporary submission directory if it exists.

    Args:
    tmpdir (str | None): Directory path to delete.
    """
    if tmpdir and os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir, ignore_errors=True)


def remove_empty_fields(d):
    """Recursively remove empty strings, None, empty dicts, and empty lists from a nested dict.

    Args:
        d: Nested dictionary to clean.

    Returns:
        dict: Cleaned dictionary with empty values removed.
    """
    if not isinstance(d, dict):
        return d
    cleaned = {}
    for k, v in d.items():
        if isinstance(v, dict):
            v = remove_empty_fields(v)
            if v:
                cleaned[k] = v
        elif isinstance(v, list):
            v = [remove_empty_fields(i) for i in v]
            v = [i for i in v if i not in (None, "", {}, [])]
            if v:
                cleaned[k] = v
        elif v not in (None, ""):
            cleaned[k] = v
    return cleaned
