#!/usr/bin/env python

import json
import os
import shutil

import requests
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

from biosimdb_interface.login.community_invite import (
    INVITE_FAILED,
    INVITE_PENDING,
    INVITE_SENT,
    invite_user,
)

from . import form_bp
from .upload import (
    SIM_METADATA_FILENAME,
    is_submission_cancelled,
    mark_submission_cancelled,
    prepare_for_invenio,
)
from .webform import _get_workflow
from .workflows import WorkflowNotFound


def _discard_workflow():
    try:
        current_app.extensions["workflow_store"].delete(request.form.get("workflow_id"))
    except WorkflowNotFound:
        pass


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
        current_app.logger.exception(
            f"No pending submission found: tmpdir {tmpdir}, pending_form_path {pending_form_path}"
        )
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
        current_app.logger.exception(f"No pending submission found: tmpdir {tmpdir}")

        flash("No pending submission found. Please submit again.", "warning")
        return redirect(url_for("form.webform"))

    if is_submission_cancelled(tmpdir):
        _discard_workflow()
        return redirect(url_for("form.webform"))

    sim_metadata_path = os.path.join(tmpdir, SIM_METADATA_FILENAME)
    if not os.path.isfile(sim_metadata_path):
        current_app.logger.exception(
            f"No pending submission found: sim_metadata_path {sim_metadata_path}"
        )
        flash("No pending submission found. Please submit again.", "warning")
        return redirect(url_for("form.webform"))

    with open(sim_metadata_path) as f:
        sim_metadata = json.load(f)

    try:
        token = session.get("access_token")
        invite_status = invite_user("biosimdb", token)

        if is_submission_cancelled(tmpdir):
            _discard_workflow()
            return redirect(url_for("form.webform"))

        draft_id = prepare_for_invenio(sim_metadata, tmpdir)

        if draft_id:
            current_app.logger.debug(
                f"Draft ID {draft_id} created and submitted, tmpdir being deleted"
            )
            shutil.rmtree(tmpdir, ignore_errors=True)

        else:
            _discard_workflow()
            flash("Upload failed. Please try again.", "danger")
            return redirect(url_for("form.webform"))
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        current_app.logger.error(exc)
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
        _discard_workflow()
        flash("Upload failed unexpectedly. Please try again.", "danger")
        return redirect(url_for("form.webform"))

    except requests.exceptions.JSONDecodeError:
        current_app.logger.exception("Invenio returned a non-JSON response")
        _discard_workflow()
        flash(
            "Upload failed: the repository returned an unexpected response. "
            "The file may be too large for the server to accept.",
            "danger",
        )
        return redirect(url_for("form.webform"))

    # success: now clear submission data and logout user.
    _discard_workflow()
    session.pop("access_token", None)
    session.pop("user_email", None)
    session.pop("post_login_redirect", None)

    BASE_URL = current_app.config["BASE_URL"]
    record_url = f"{BASE_URL}/uploads/{draft_id}"
    session["submitted_record_url"] = record_url
    if invite_status == INVITE_SENT:
        flash(
            "You are not yet a member of the BioSimDB community. "
            "Please check your email for an invitation and accept it "
            "to complete your submission.",
            "info",
        )
    if invite_status == INVITE_PENDING:
        flash(
            "You have already been invited to the BioSimDB community. "
            "Please check your email for the invitation and accept it "
            "to complete your submission. If you cannot find your invite, "
            'please check "My dashboard > Requests" in BioSimDB.',
            "info",
        )
    if invite_status == INVITE_FAILED:
        flash(
            "Invitation to the BioSimDB community failed. "
            "Please contact the BioSimDB team for help with your submission.",
            "warning",
        )
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
