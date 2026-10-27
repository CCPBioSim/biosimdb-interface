#!/usr/bin/env python

from biosim_extractor.metadata.convertpopulated import (
    UnitConversionError,
    convert_populated_metadata_units,
)
from biosim_extractor.metadata.validatemetadata import (
    MetadataValidationError,
    validate_metadata,
)
from flask import (
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ..core.errors import FormConversionError
from ..core.utils import remove_empty_fields
from ..uploads.to_server import (
    extract_uploaded_file_metadata,
    save_pending_submission,
    verify_cached_file_meta,
)
from .conversion import form_to_json


def _handle_save(json_form, tmpdir):
    """Return the validated metadata as a JSON download response."""
    return jsonify({"success": True, "data": json_form})


def _handle_submit(json_form, tmpdir):
    """Save metadata and start or defer the submission process."""
    save_pending_submission(json_form, tmpdir)
    workflow_id = request.form["workflow_id"]
    if not session.get("access_token"):
        session["post_login_redirect"] = url_for(
            "submit.resume_submit", workflow_id=workflow_id
        )
        return redirect(url_for("auth.login"))
    return render_template("form/loading.html", workflow_id=workflow_id)


HANDLERS = {"save": _handle_save, "submit": _handle_submit}


def _group(exc):
    """Convert a validation exception into a heading-and-errors group."""
    return {"heading": exc.heading, "errors": exc.errors}


def build_metadata(form, tmpdir, action):
    """Form -> validated metadata dict. Returns (json_form, error_groups).

    Three checks of form data:
    1. use the webform fields and expected types to check fields are correctly formatted.
    2. Check fields that are to be converted to standard units are correctly formatted.
    3. Check fields conform to linkml schema.

    """
    form_values = form.copy()
    form_values.pop("workflow_id", None)

    try:
        # check fields match typehint formats
        json_form = remove_empty_fields(form_to_json(form_values))
    except FormConversionError as e:
        return None, [_group(e)]  # nothing usable to convert/validate

    groups = []
    try:
        # convert to standard units via extractor
        json_form = convert_populated_metadata_units(json_form)
    except UnitConversionError as e:
        groups.append(_group(e))

    if action == "save":
        json_form["files"] = extract_uploaded_file_metadata(tmpdir)

    try:
        # validate metadata against linkml schema
        BIOSIM_SCHEMA_PATH = current_app.config["BIOSIM_SCHEMA_PATH"]
        validate_metadata(json_form, BIOSIM_SCHEMA_PATH, strict=True)
    except MetadataValidationError as e:
        groups.append(_group(e))
    return json_form, groups


def check_ready(action, tmpdir, topo_path, traj_files):
    """Return an error message if the request can't proceed, else None."""
    if action in ("save", "submit") and not (tmpdir and topo_path and traj_files):
        return "Please extract metadata before submitting."
    if action == "submit":
        ok, err = verify_cached_file_meta(tmpdir)
        if not ok:
            return err
    return None


def get_workflow():
    """Resolve the tab-scoped workflow sent with the current request."""
    workflow_id = request.values.get("workflow_id")
    return current_app.extensions["workflow_store"].get(workflow_id)


def errors_response(errors, status=200):
    """JSON response in the shape the front end expects."""
    return jsonify({"validation_errors": errors}), status
