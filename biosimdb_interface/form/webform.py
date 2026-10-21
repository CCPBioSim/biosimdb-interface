#!/usr/bin/env python
import json
import os

import requests
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
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.exceptions import HTTPException

from biosimdb_interface.login.community_invite import invite_user
from biosimdb_interface.schema.webform import WEBFORM_SCHEMA, get_simulation_metadata

from . import form_bp
from .upload import (
    SIM_METADATA_FILENAME,
    extract_uploaded_file_metadata,
    is_submission_cancelled,
    load_extracted_files,
    mark_submission_cancelled,
    prepare_for_invenio,
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


@form_bp.errorhandler(Exception)
def handle_unexpected_error(exc):
    """Log an unexpected blueprint error and return a JSON error response."""
    if isinstance(exc, HTTPException):
        return exc

    current_app.logger.exception("Unhandled error in form blueprint")
    message = (
        f"{type(exc).__name__}: {exc}"
        if current_app.debug
        else "An unexpected server error occurred. Please try again."
    )
    return jsonify({"validation_errors": [message]}), 500


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
        validate_metadata(json_form, os.getenv("BIOSIM_SCHEMA_PATH", ""), strict=True)
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


@form_bp.route("/resume_submit")
def resume_submit():
    """Resume a pending submission after successful login.

    Redirects to login if unauthenticated, or to the webform if no pending
    submission is found in the session.
    """
    if not session.get("access_token"):
        return redirect(url_for("login.login"))

    try:
        workflow = _get_workflow()
    except WorkflowNotFound as exc:
        return jsonify({"validation_errors": [str(exc)]}), 400

    tmpdir = workflow.tmpdir

    pending_form_path = (
        os.path.join(tmpdir, "pending_form_data.json") if tmpdir else None
    )
    if not tmpdir or not pending_form_path or not os.path.isfile(pending_form_path):
        flash("No pending submission found.", "warning")
        return redirect(url_for("form.webform"))

    return render_template(
        "form/loading.html",
        workflow_id=request.args["workflow_id"],
    )


@form_bp.route("/do_submit", methods=["POST"])
def do_submit():
    """Execute the deferred Invenio upload using session-stored form data.
    Called automatically by the loading page after login.
    Automatically invite user to Invenio instance community, then submit.
    Clears pending session data after upload and renders the success page
    with the record URL.
    """
    try:
        workflow = current_app.extensions["workflow_store"].get(
            request.args.get("workflow_id")
        )
    except WorkflowNotFound as exc:
        return jsonify({"validation_errors": [str(exc)]}), 400

    tmpdir = workflow.tmpdir

    if not tmpdir:
        flash("No pending submission found. Please submit again.", "warning")
        return redirect(url_for("form.webform"))

    if is_submission_cancelled(tmpdir):
        current_app.extensions["workflow_store"].delete(
            request.values.get("workflow_id")
        )
        return redirect(url_for("form.webform"))

    sim_metadata_path = os.path.join(tmpdir, SIM_METADATA_FILENAME)
    if not os.path.isfile(sim_metadata_path):
        flash("No pending submission found. Please submit again.", "warning")
        return redirect(url_for("form.webform"))

    with open(sim_metadata_path) as f:
        sim_metadata = json.load(f)

    try:
        token = session.get("access_token")
        invite_user("biosimdb", token)

        if is_submission_cancelled(tmpdir):
            current_app.extensions["workflow_store"].delete(
                request.values.get("workflow_id")
            )
            return redirect(url_for("form.webform"))

        draft_id = prepare_for_invenio(sim_metadata, tmpdir)

        if not draft_id:
            current_app.extensions["workflow_store"].delete(
                request.values.get("workflow_id")
            )
            flash("Upload failed. Please try again.", "danger")
            return redirect(url_for("form.webform"))

    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None

        if status in (401, 403):
            session.pop("access_token", None)  # force fresh login
            session["post_login_redirect"] = url_for(
                "form.resume_submit",
                workflow_id=request.form["workflow_id"],
            )
            flash(
                "Your login session is no longer valid for upload. "
                "Please sign in again and the submission will resume automatically.",
                "warning",
            )
            return redirect(url_for("login.login"))

        session.pop("access_token", None)  # force fresh login
        current_app.extensions["workflow_store"].delete(
            request.values.get("workflow_id")
        )
        flash("Upload failed unexpectedly. Please try again.", "danger")
        return redirect(url_for("form.webform"))

    except requests.exceptions.JSONDecodeError:
        current_app.logger.exception("Invenio returned a non-JSON response")
        current_app.extensions["workflow_store"].delete(
            request.values.get("workflow_id")
        )
        flash(
            "Upload failed: the repository returned an unexpected response. "
            "The file may be too large for the server to accept.",
            "danger",
        )
        return redirect(url_for("form.webform"))

    # success: now clear submission data and logout user.
    current_app.extensions["workflow_store"].delete(request.values.get("workflow_id"))
    session.pop("access_token", None)
    session.pop("user_email", None)
    session.pop("post_login_redirect", None)

    BASE_URL = current_app.config["BASE_URL"]
    record_url = f"{BASE_URL}/uploads/{draft_id}"
    session["submitted_record_url"] = record_url
    return redirect(url_for("form.submit_success"))


@form_bp.route("/cancel_submit", methods=["POST"])
def cancel_submit():
    """Signal an in-progress submission to stop and reset client-facing session state.

    Does not delete the tmpdir directly, since the in-flight do_submit request
    still owns those files; do_submit checks the cancellation flag itself and
    performs its own cleanup once it is safe to do so.
    """
    try:
        workflow = current_app.extensions["workflow_store"].get(
            request.args.get("workflow_id")
        )
    except WorkflowNotFound as exc:
        return jsonify({"validation_errors": [str(exc)]}), 400

    tmpdir = workflow.tmpdir
    mark_submission_cancelled(tmpdir)

    for key in (
        "post_login_redirect",
        "access_token",
        "user_email",
    ):
        session.pop(key, None)
    session["force_clear_client_state"] = True
    return jsonify({"success": True})


@form_bp.route("/submit_success")
def submit_success():
    """Render the successful Invenio submission page."""
    record_url = session.get("submitted_record_url")
    if not record_url:
        flash("No completed submission found.", "warning")
        return redirect(url_for("form.webform"))
    return render_template("form/submit_success.html", record_url=record_url)
