#!/usr/bin/env python
"""Services for converting and validating webform submissions.

Provides helpers to clean and validate submitted metadata, check workflow
readiness, and dispatch save or submit actions.
"""

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
from ..uploads.to_server import (
    extract_uploaded_file_metadata,
    save_pending_submission,
    verify_cached_file_meta,
)
from .conversion import form_to_json


def _handle_save(json_form, tmpdir):
    """Return validated metadata as a JSON response.

    Args:
        json_form (dict): Converted and validated form data.
        tmpdir (str): Workflow directory associated with the form.

    Returns:
        tuple: JSON response with ``success`` and ``data`` fields, and HTTP 200.
    """
    return jsonify({"success": True, "data": json_form})


def _handle_submit(json_form, tmpdir):
    """Persist submission data and start or defer the upload.

    If the user is not logged in, stores a post-login redirect and sends them
    to authentication. Otherwise, renders the upload progress page.

    Args:
        json_form (dict): Converted and validated form data.
        tmpdir (str): Workflow directory for pending submission files.

    Returns:
        Response: Login redirect or rendered upload progress page.
    """
    save_pending_submission(json_form, tmpdir)
    workflow_id = request.form["workflow_id"]
    if not session.get("access_token"):
        session["post_login_redirect"] = url_for(
            "submit.resume_submit", workflow_id=workflow_id
        )
        return redirect(url_for("auth.login"))
    return render_template("form/loading.html", workflow_id=workflow_id)


HANDLERS = {"save": _handle_save, "submit": _handle_submit}


def _remove_empty_fields(d):
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
            v = _remove_empty_fields(v)
            if v:
                cleaned[k] = v
        elif isinstance(v, list):
            v = [_remove_empty_fields(i) for i in v]
            v = [i for i in v if i not in (None, "", {}, [])]
            if v:
                cleaned[k] = v
        elif v not in (None, ""):
            cleaned[k] = v
    return cleaned


def _group(exc):
    """Convert a validation exception into a heading-and-errors mapping.

    Args:
        exc: Exception with ``heading`` and ``errors`` attributes.

    Returns:
        dict: Mapping with ``heading`` and ``errors`` keys.
    """
    return {"heading": exc.heading, "errors": exc.errors}


def build_metadata(form, tmpdir, action):
    """Convert form fields and collect metadata validation errors.

    Removes empty values, converts units, optionally attaches uploaded-file
    metadata for saves, and validates the result against the BioSim schema.

    Three checks of form data:
        1. use the webform fields and expected types to check fields are correctly formatted.
        2. Check fields that are to be converted to standard units are correctly formatted.
        3. Check fields conform to linkml schema.

    Args:
        form: Submitted form mapping.
        tmpdir (str): Workflow directory containing uploaded files.
        action (str): Requested action, such as ``"save"`` or ``"submit"``.

    Returns:
        tuple: ``(metadata, error_groups)``. Metadata is ``None`` when form
        conversion fails; otherwise it is the converted metadata dictionary.
    """
    form_values = form.copy()
    form_values.pop("workflow_id", None)

    try:
        # check fields match typehint formats
        json_form = _remove_empty_fields(form_to_json(form_values))
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
    """Check whether the workflow has the files required for its action.

    Args:
        action (str | None): Requested form action.
        tmpdir (str | None): Workflow directory.
        topo_path (str | None): Saved topology path.
        traj_files (list[str] | None): Saved trajectory paths.

    Returns:
        str | None: Readiness error message, or ``None`` when ready.
    """
    if action in ("save", "submit") and not (tmpdir and topo_path and traj_files):
        return "Please extract metadata before submitting."
    if action == "submit":
        ok, err = verify_cached_file_meta(tmpdir)
        if not ok:
            return err
    return None


def errors_response(errors, status=200):
    """Create a JSON response containing validation errors.

    Args:
        errors (list): Validation messages or error groups for the frontend.
        status (int): HTTP status code for the response.

    Returns:
        tuple: JSON response and HTTP status code.
    """
    return jsonify({"validation_errors": errors}), status
