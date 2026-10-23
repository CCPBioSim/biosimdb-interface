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

from biosimdb_interface.schema.webform import WEBFORM_SCHEMA, get_simulation_metadata

from . import form_bp
from .upload import (
    extract_uploaded_file_metadata,
    load_extracted_files,
    save_pending_submission,
    verify_cached_file_meta,
)
from .utils import FormConversionError, form_to_json, remove_empty_fields
from .validation import validate_with_mdanalysis
from .workflows import WorkflowNotFound


def _get_workflow():
    """Resolve the tab-scoped workflow sent with the current request."""
    workflow_id = request.values.get("workflow_id")
    return current_app.extensions["workflow_store"].get(workflow_id)


def _handle_save(json_form, tmpdir):
    """Return the validated metadata as a JSON download response."""
    return jsonify({"success": True, "data": json_form})


def _handle_submit(json_form, tmpdir):
    """Save metadata and start or defer the submission process."""
    save_pending_submission(json_form, tmpdir)
    workflow_id = request.form["workflow_id"]
    if not session.get("access_token"):
        session["post_login_redirect"] = url_for(
            "form.resume_submit", workflow_id=workflow_id
        )
        return redirect(url_for("login.login"))
    return render_template("form/loading.html", workflow_id=workflow_id)


_HANDLERS = {"save": _handle_save, "submit": _handle_submit}


def _errors_response(errors, status=200):
    """JSON response in the shape the front end expects."""
    return jsonify({"validation_errors": errors}), status


def _group(exc):
    """Convert a validation exception into a heading-and-errors group."""
    return {"heading": exc.heading, "errors": exc.errors}


def _build_metadata(form, tmpdir, action):
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


def _check_ready(action, tmpdir, topo_path, traj_files):
    """Return an error message if the request can't proceed, else None."""
    if action in ("save", "submit") and not (tmpdir and topo_path and traj_files):
        return "Please extract metadata before submitting."
    if action == "submit":
        ok, err = verify_cached_file_meta(tmpdir)
        if not ok:
            return err
    return None


@form_bp.route("/webform", methods=["GET"])
def webform():
    """Render the metadata form."""
    clear_client_state = bool(session.pop("force_clear_client_state", False))
    schema = {
        **WEBFORM_SCHEMA,
        "data": {
            **WEBFORM_SCHEMA["data"],
            "simulation_metadata": get_simulation_metadata(),
        },
    }
    return render_template(
        "form/webform.html",
        schema=schema,
        form_data={},
        errors={},
        clear_client_state=clear_client_state,
    )


@form_bp.route("/webform", methods=["POST"])
def webform_post():
    """Validate and handle a metadata save or submission request."""
    try:
        workflow = _get_workflow()
    except WorkflowNotFound as exc:
        return _errors_response([str(exc)], 400)

    tmpdir = workflow.tmpdir
    topo_path, traj_files = load_extracted_files(tmpdir)
    action = next((a for a in ("save", "submit") if a in request.form), None)

    if msg := _check_ready(action, tmpdir, topo_path, traj_files):
        return _errors_response([msg], 400)

    if msg := validate_with_mdanalysis(topo_path, traj_files):
        return _errors_response([msg])

    if action not in ("save", "submit"):
        return _errors_response(["Unknown action."], 400)

    json_form, groups = _build_metadata(request.form, tmpdir, action)
    if groups:
        return _errors_response(groups)

    return _HANDLERS[action](json_form, tmpdir)
