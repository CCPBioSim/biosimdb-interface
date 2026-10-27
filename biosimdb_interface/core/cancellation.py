#!/usr/bin/env python

import os

from flask import current_app, request

from .workflows import WorkflowNotFound


class UploadCancelled(Exception):
    """Raised when the user cancels an in-progress upload."""


class MultipartTooSlow(Exception):
    """Raised when a multipart upload exceeds its time budget."""


def mark_submission_cancelled(tmpdir):
    """Signal an in-flight do_submit to stop, without touching its files."""
    if tmpdir and os.path.isdir(tmpdir):
        open(os.path.join(tmpdir, "CANCELLED"), "w").close()


def is_submission_cancelled(tmpdir):
    return bool(tmpdir) and os.path.isfile(os.path.join(tmpdir, "CANCELLED"))


def discard_workflow():
    try:
        current_app.extensions["workflow_store"].delete(request.args.get("workflow_id"))
    except WorkflowNotFound:
        pass
