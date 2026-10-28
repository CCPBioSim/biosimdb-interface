#!/usr/bin/env python
"""Flask error handlers for the webform blueprint.

Converts known form and external-service errors into user-facing responses.
Unexpected extraction errors return JSON for the fetch-based extraction
request, while other unexpected errors are logged and redirect to the webform.
"""

from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    request,
    url_for,
)
from werkzeug.exceptions import HTTPException

from ..auth import auth_bp
from ..extract import extract_bp
from .errors import ExternalAPIError, WebformError
from .workflows import WorkflowNotFound


@extract_bp.errorhandler(WebformError)
def handle_metadata_extraction_error(exc):
    """Return a JSON response for a known webform error.

    Args:
        exc (WebformError): Error containing a message, status code, and
            optional response payload.

    Returns:
        tuple: JSON error response and the exception's HTTP status code.
    """
    current_app.logger.exception(f"Metadata extraction Error: {exc}")
    return jsonify(exc.to_dict()), exc.status_code


@auth_bp.errorhandler(ExternalAPIError)
def handle_external_api_error(exc):
    """Flash a friendly message and redirect after an external API failure.

    Args:
        exc (ExternalAPIError): The external-service error that was raised.

    Returns:
        Response: Redirect to the webform.
    """
    current_app.logger.error("External API error: %s", exc)
    flash(
        "A remote service is currently unavailable. Please try again later.", "danger"
    )
    return redirect(url_for("webform.webform"))


# include this app-wide
def handle_unexpected_error(exc):
    """Log an unexpected error and return an endpoint-appropriate response.

    HTTP exceptions are passed through. Unexpected errors from the metadata
    extraction endpoint return a JSON 500 response and discard its workflow.
    Other unexpected errors flash a message and redirect to the webform.

    Args:
        exc (Exception): The error raised while handling the request.

    Returns:
        Response: The original HTTP exception, a JSON error response, or a
        redirect to the webform.
    """
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
