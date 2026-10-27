#!/usr/bin/env python

from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    request,
    url_for,
)
from werkzeug.exceptions import HTTPException

from ..webform import form_bp
from .errors import ExternalAPIError, WebformError
from .workflows import WorkflowNotFound


@form_bp.errorhandler(WebformError)
def handle_metadata_extraction_error(exc):
    current_app.logger.exception(f"Metadata extraction Error: {exc}")
    return jsonify(exc.to_dict()), exc.status_code


@form_bp.errorhandler(ExternalAPIError)
def handle_external_api_error(exc):
    """Show a friendly message when an external service fails."""
    current_app.logger.error("External API error: %s", exc)
    flash(
        "A remote service is currently unavailable. Please try again later.", "danger"
    )
    return redirect(url_for("webform.webform"))


@form_bp.errorhandler(Exception)
def handle_unexpected_error(exc):
    """Log an unexpected blueprint error and return a JSON error response."""
    if isinstance(exc, HTTPException):
        return exc

    current_app.logger.exception(f"Unexpected error in form blueprint: {exc}")
    message = (
        f"{type(exc).__name__}: {exc}"
        if current_app.debug
        else "An unexpected server error occurred. Please try again."
    )

    # extract_metadata is called via fetch, which expects JSON rather than a redirect
    if request.endpoint == "extract.extract_metadata":
        try:
            current_app.extensions["workflow_store"].delete(
                request.form.get("workflow_id")
            )
        except WorkflowNotFound:
            pass
        return jsonify({"error": f"Extraction failed: {message}"}), 500

    flash(f"{message}", "danger")
    return redirect(url_for("webform.webform"))
