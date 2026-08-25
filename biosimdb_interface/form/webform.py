#!/usr/bin/env python
import json
import os

import requests
from biosim_extractor.metadata.convertpopulated import convert_populated_metadata_units
from biosim_extractor.metadata.validatemetadata import validate_metadata
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
from werkzeug.datastructures import ImmutableMultiDict

from biosimdb_interface.login.community_invite import invite_user
from biosimdb_interface.schema.webform import WEBFORM_SCHEMA, get_simulation_metadata

from . import form_bp
from .upload import (
    extract_uploaded_file_metadata,
    is_submission_cancelled,
    load_extracted_files,
    mark_submission_cancelled,
    prepare_for_invenio,
    save_pending_submission,
    verify_cached_file_meta,
)
from .utils import form_to_json, remove_empty_fields
from .validation import validate_with_mdanalysis
from .workflows import WorkflowNotFound


def _get_workflow():
    """Resolve the tab-scoped workflow sent with the current request."""
    workflow_id = request.values.get("workflow_id")
    return current_app.extensions["workflow_store"].get(workflow_id)


@form_bp.route("/webform", methods=["GET", "POST"])
def webform():
    """Render the metadata form and handle save/submit actions.

    On POST, validates uploaded files, converts submitted metadata to standard
    units, removes empty fields, and validates the result against the BioSim
    schema. ``save`` returns the validated JSON to the browser. ``submit`` saves
    uploaded files plus the validated JSON for deferred Invenio upload, then
    starts login if needed.
    """
    clear_client_state = False
    token = session.get("access_token")

    # an abandoned/failed login leaves a pending submit; discard it on return
    if request.method == "GET" and session.pop("force_clear_client_state", False):
        clear_client_state = True

    if request.method == "POST":
        try:
            workflow = _get_workflow()
        except WorkflowNotFound as exc:
            return jsonify({"validation_errors": [str(exc)]}), 400

        tmpdir = workflow.tmpdir
        topo_path, traj_files = load_extracted_files(tmpdir)

        action = (
            "save"
            if "save" in request.form
            else "submit"
            if "submit" in request.form
            else None
        )

        if action == "submit":
            if not tmpdir or not topo_path or not traj_files:
                return jsonify(
                    {
                        "validation_errors": [
                            "Please extract metadata before submitting."
                        ]
                    }
                ), 400

            ok, err = verify_cached_file_meta(tmpdir)
            if not ok:
                return jsonify({"validation_errors": [err]}), 400

        if action in ["save", "submit"]:
            if not tmpdir or not topo_path or not traj_files:
                return jsonify(
                    {
                        "validation_errors": [
                            "Please extract metadata before submitting."
                        ]
                    }
                ), 400

        # check files can be read with mda
        mda_error = validate_with_mdanalysis(topo_path, traj_files)

        if mda_error:
            return jsonify({"validation_errors": [mda_error]})
        if action in ["save", "submit"]:
            # include file info in output, ro-crate?
            form_values = request.form.copy()
            # remove workflow_id from form
            form_values.pop("workflow_id", None)
            json_form = form_to_json(form_values)
            json_form = remove_empty_fields(json_form)

            # convert to standard units
            json_form = convert_populated_metadata_units(json_form)

            if action == "save":
                json_form["files"] = extract_uploaded_file_metadata(tmpdir)

            biosimschema_path = os.getenv("BIOSIM_SCHEMA_PATH", "")

            validation_errors = []
            try:
                validate_metadata(json_form, biosimschema_path, strict=True)
            except ValueError as e:
                validation_errors = str(e).splitlines()

            if validation_errors:
                return jsonify(
                    {
                        "validation_errors": validation_errors,
                    }
                )

            if action == "submit":
                save_pending_submission(json_form, tmpdir)
                if not token:
                    session["post_login_redirect"] = url_for(
                        "form.resume_submit",
                        workflow_id=request.form["workflow_id"],
                    )
                    return redirect(url_for("login.login"))

                return render_template(
                    "form/loading.html",
                    workflow_id=request.form["workflow_id"],
                )

            if action == "save":
                return jsonify({"success": True, "data": json_form})

    schema = {**WEBFORM_SCHEMA}
    schema["data"] = {
        **WEBFORM_SCHEMA["data"],
        "simulation_metadata": get_simulation_metadata(),
    }
    return render_template(
        "form/webform.html",
        schema=schema,
        form_data={},
        errors={},
        clear_client_state=clear_client_state,
    )


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

    pending_form_path = os.path.join(tmpdir, "pending_form_data.json")
    if not os.path.isfile(pending_form_path):
        flash("No pending submission found. Please submit again.", "warning")
        return redirect(url_for("form.webform"))

    with open(pending_form_path) as f:
        form_data = json.load(f)

    flat_form = ImmutableMultiDict(
        [(k, v) for k, vals in form_data.items() for v in vals]
    )

    try:
        token = session.get("access_token")
        invite_user("biosimdb", token)

        if is_submission_cancelled(tmpdir):
            current_app.extensions["workflow_store"].delete(
                request.values.get("workflow_id")
            )
            return redirect(url_for("form.webform"))

        draft_id = prepare_for_invenio(flat_form, tmpdir)

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
