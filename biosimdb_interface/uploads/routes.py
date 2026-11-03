"""HTTP endpoints for resumable chunked uploads into a workflow directory."""

import os

from flask import Blueprint, current_app, jsonify, request

from ..core.workflows import WorkflowNotFound
from .chunked import ChunkedUpload, UploadError

chunked_bp = Blueprint("chunked_uploads", __name__)


def _workflow_dir(create=False):
    """Resolve the caller's workflow directory from the validated workflow ID."""
    store = current_app.extensions["workflow_store"]
    body = request.get_json(silent=True) or {}
    workflow_id = request.args.get("workflow_id") or body.get("workflow_id")
    try:
        return store.get(workflow_id).tmpdir
    except WorkflowNotFound:
        if not create:
            raise
        return store.reset(workflow_id).tmpdir


def _upload(upload_id):
    """Load an existing upload belonging to the caller's workflow."""
    return ChunkedUpload(_workflow_dir(), upload_id).load()


@chunked_bp.errorhandler(UploadError)
def _upload_error(exc):
    return jsonify({"error": str(exc)}), exc.status_code


@chunked_bp.errorhandler(WorkflowNotFound)
def _workflow_error(exc):
    return jsonify({"error": str(exc)}), 400


@chunked_bp.post("/init")
def init():
    """Start or resume an upload; returns chunk size and stored chunks."""
    body = request.get_json(silent=True) or {}
    upload = ChunkedUpload.start(
        _workflow_dir(create=True),
        body.get("filename"),
        body.get("size"),
        max_bytes=current_app.config["MAX_UPLOAD_BYTES"],
        chunk_size=current_app.config["UPLOAD_CHUNK_SIZE"],
    )
    return jsonify(upload.describe())


@chunked_bp.put("/<upload_id>/chunks/<int:index>")
def put_chunk(upload_id, index):
    """Store one raw-bytes chunk."""
    _upload(upload_id).write_chunk(index, request.stream, request.content_length)
    return jsonify({"ok": True})


@chunked_bp.post("/<upload_id>/complete")
def complete(upload_id):
    """Finalise the upload, optionally verifying a client-supplied SHA-256."""
    body = request.get_json(silent=True) or {}
    path = _upload(upload_id).complete(body.get("sha256"))
    return jsonify({"filename": os.path.basename(path)})


@chunked_bp.delete("/<upload_id>")
def abort(upload_id):
    """Discard a partial upload."""
    _upload(upload_id).abort()
    return jsonify({"ok": True})
