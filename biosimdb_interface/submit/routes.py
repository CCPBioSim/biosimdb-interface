#!/usr/bin/env python
"""Routes for resuming, executing, cancelling, and displaying submissions.

Submission state is associated with a workflow ID. Routes use that workflow
to access pending metadata and files, and Flask session state for login and
post-submission messages.
"""

import json
import os

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

from biosimdb_interface.auth.community_invite import (
    INVITE_FAILED,
    INVITE_PENDING,
    INVITE_SENT,
    invite_user,
)

from ..core.cancellation import (
    UploadCancelled,
    discard_workflow,
    is_submission_cancelled,
    mark_submission_cancelled,
)
from ..core.workflows import WorkflowNotFound, get_workflow
from ..uploads.to_invenio import prepare_for_invenio
from ..uploads.utils import SIM_METADATA_FILENAME
from . import submit_bp


@submit_bp.route("/resume_submit")
def resume_submit():
    """Resume a pending submission after login.

    Resolves the workflow ID from the request and verifies that pending form
    data exists before rendering the upload progress page.

    Returns:
        Response: Progress page, login/webform redirect, or JSON 400 response
        if the workflow ID is missing, invalid, or expired.
    """
    if not session.get("access_token"):
        return redirect(url_for("auth.login"))

    try:
        workflow = get_workflow()
    except WorkflowNotFound as exc:
        return jsonify({"validation_errors": [str(exc)]}), 400

    tmpdir = workflow.tmpdir

    pending_form_path = (
        os.path.join(tmpdir, "pending_form_data.json") if tmpdir else None
    )
    if not tmpdir or not pending_form_path or not os.path.isfile(pending_form_path):
        current_app.logger.exception(
            f"No pending submission found: tmpdir {tmpdir}, "
            f"pending_form_path {pending_form_path}"
        )
        flash("No pending submission found.", "warning")
        return redirect(url_for("webform.webform"))

    return render_template(
        "form/loading.html",
        workflow_id=request.args["workflow_id"],
    )


@submit_bp.route("/do_submit", methods=["POST"])
def do_submit():
    """Upload the pending submission to InvenioRDM.

    Checks cancellation and saved metadata, invites the user to the target
    community, and uploads the record. On success, clears workflow and login
    state and redirects to the success page.

    Returns:
        Response: Redirect to the success page, login page, or webform; or a
        JSON 400 response if the workflow cannot be resolved.
    """
    try:
        workflow = get_workflow()
    except WorkflowNotFound as exc:
        return jsonify({"validation_errors": [str(exc)]}), 400

    tmpdir = workflow.tmpdir

    if not tmpdir:
        current_app.logger.exception(f"No pending submission found: tmpdir {tmpdir}")

        flash("No pending submission found. Please submit again.", "warning")
        return redirect(url_for("webform.webform"))

    if is_submission_cancelled(tmpdir):
        discard_workflow()
        return redirect(url_for("webform.webform"))

    sim_metadata_path = os.path.join(tmpdir, SIM_METADATA_FILENAME)
    if not os.path.isfile(sim_metadata_path):
        current_app.logger.exception(
            f"No pending submission found: sim_metadata_path {sim_metadata_path}"
        )
        flash("No pending submission found. Please submit again.", "warning")
        return redirect(url_for("webform.webform"))

    with open(sim_metadata_path) as f:
        sim_metadata = json.load(f)

    try:
        token = session.get("access_token")
        invite_status = invite_user("biosimdb", token)
        draft_id = prepare_for_invenio(sim_metadata, tmpdir)

        if not draft_id:
            current_app.logger.error("No draft ID was created, upload failed")
            flash("Upload failed. Please try again.", "danger")
            return redirect(url_for("webform.webform"))
    except UploadCancelled:
        current_app.logger.info("Upload cancelled by user; draft deleted")
        discard_workflow()  # safe now: the draft is already gone
        return redirect(url_for("webform.webform"))
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        current_app.logger.error(exc)
        current_app.logger.error("Invenio returned a HTTPError response")
        if status in (401, 403):
            session.pop("access_token", None)  # force fresh login
            session["post_login_redirect"] = url_for(
                "submit.resume_submit",
                workflow_id=request.form["workflow_id"],
            )
            flash(
                "Your login session is no longer valid for upload. "
                "Please sign in again and the submission will resume automatically.",
                "warning",
            )
            return redirect(url_for("auth.login"))

        session.pop("access_token", None)  # force fresh login
        discard_workflow()
        flash("Upload failed unexpectedly. Please try again.", "danger")
        return redirect(url_for("webform.webform"))

    except requests.exceptions.JSONDecodeError as exc:
        current_app.logger.error(exc)
        current_app.logger.exception("Invenio returned a non-JSON response")
        flash(
            "Upload failed: the repository returned an unexpected response. "
            "The file may be too large for the server to accept.",
            "danger",
        )
        session.pop("access_token", None)  # force fresh login
        discard_workflow()
        return redirect(url_for("webform.webform"))

    # success: now clear submission data and logout user.
    current_app.logger.debug(
        f"Draft ID {draft_id} created and submitted, tmpdir being deleted"
    )
    discard_workflow()
    session.pop("access_token", None)  # force fresh login
    session.pop("user_email", None)
    session.pop("post_login_redirect", None)

    BASE_URL = current_app.config["BASE_URL"]
    record_url = f"{BASE_URL}/uploads/{draft_id}"
    session["submitted_record_url"] = record_url
    current_app.logger.debug(f"User invite status: {invite_status}")
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
    return redirect(url_for("submit.submit_success"))


@submit_bp.route("/cancel_submit", methods=["POST"])
def cancel_submit():
    """Signal cancellation of the current submission.

    Marks the workflow's cancellation flag and clears authentication and
    client-facing session state. The in-progress upload is responsible for
    cleaning up its workflow files.

    Returns:
        Response: JSON success response, or JSON 400 response if the workflow
        ID cannot be resolved.
    """
    try:
        workflow = get_workflow()
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
    current_app.logger.info(
        f"Workflow ID {request.args.get('workflow_id')} for submission to BioSimDB "
        "cancelled by user."
    )
    flash(
        "Submission to BioSimDB successfully cancelled. All data marked for "
        "clearance from server.",
        "info",
    )
    return jsonify({"success": True})


@submit_bp.route("/submit_success")
def submit_success():
    """Display the completed submission link.

    Returns:
        Response: Success page when a submitted record URL is in the session;
        otherwise redirects to the webform.
    """
    record_url = session.get("submitted_record_url")
    if not record_url:
        flash("No completed submission found.", "warning")
        return redirect(url_for("webform.webform"))
    return render_template("form/submit_success.html", record_url=record_url)
