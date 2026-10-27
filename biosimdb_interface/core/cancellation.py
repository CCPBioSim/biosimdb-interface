#!/usr/bin/env python
"""Cancellation helpers for in-progress submission uploads.

Provides the upload cancellation exceptions and helpers for marking,
checking, and discarding workflow submissions. Cancellation state is stored
in each workflow's temporary directory so upload tasks and Flask requests
can coordinate through the same filesystem.
"""

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
    """Return whether a workflow's cancellation flag exists.

    Args:
        tmpdir (str | None): Workflow temporary directory to check.

    Returns:
        bool: ``True`` if the cancellation flag exists; otherwise ``False``.
    """
    return bool(tmpdir) and os.path.isfile(os.path.join(tmpdir, "CANCELLED"))


def discard_workflow():
    """Delete the workflow associated with the current request.

    Reads the workflow ID from the request query parameters and asks the
    configured workflow store to remove its state and temporary files.
    Does nothing if the workflow has already been removed.

    This helper requires an active Flask application and request context.
    """
    try:
        current_app.extensions["workflow_store"].delete(request.args.get("workflow_id"))
    except WorkflowNotFound:
        pass
