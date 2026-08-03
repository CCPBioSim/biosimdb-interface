#!/usr/bin/env python
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
    prepare_for_invenio,
    save_pending_submission,
)
from .utils import form_to_json, remove_empty_fields
from .validation import validate_with_mdanalysis


@form_bp.route("/webform", methods=["GET", "POST"])
def webform():
    """Render the metadata form and handle save/submit actions.

    On POST, validates uploaded files, converts submitted metadata to standard
    units, removes empty fields, and validates the result against the BioSim
    schema. ``save`` returns the validated JSON to the browser. ``submit`` saves
    uploaded files plus the validated JSON for deferred Invenio upload, then
    starts login if needed.
    """
    token = session.get("access_token")

    if request.method == "POST":
        # are errors being handled correctly?
        # check files can be read with mda
        mda_error = validate_with_mdanalysis()
        if mda_error:
            return jsonify({"validation_errors": [mda_error]})

        action = (
            "save"
            if "save" in request.form
            else "submit"
            if "submit" in request.form
            else None
        )

        if action in ["save", "submit"]:
            # include file info in output, ro-crate?
            json_form = form_to_json(request.form)
            json_form = remove_empty_fields(json_form)

            # convert to standard units
            json_form = convert_populated_metadata_units(json_form)

            if action == "save":
                json_form["files"] = extract_uploaded_file_metadata()

            # NOTE: note used yet, could be used to validate extracted fields are matching what is returned from json_form
            # extracted = session.get("extracted_metadata")

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
                save_pending_submission(json_form)
                if not token:
                    session["post_login_redirect"] = url_for("form.resume_submit")
                    return redirect(url_for("login.login"))
                return render_template("form/loading.html")

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
    )


@form_bp.route("/resume_submit")
def resume_submit():
    """Resume a pending submission after successful login.

    Redirects to login if unauthenticated, or to the webform if no pending
    submission is found in the session.
    """
    if not session.get("access_token"):
        return redirect(url_for("login.login"))
    if not session.get("pending_form_data") or not session.get("pending_files_dir"):
        flash("No pending submission found.", "warning")
        return redirect(url_for("form.webform"))
    return render_template("form/loading.html")


@form_bp.route("/do_submit", methods=["POST"])
def do_submit():
    """Execute the deferred Invenio upload using session-stored form data.
    Called automatically by the loading page after login.
    Automatically invite user to Invenio instance community, then submit.
    Clears pending session data after upload and renders the success page
    with the record URL.
    """
    form_data = session.pop("pending_form_data", None)
    tmpdir = session.pop("pending_files_dir", None)

    if not form_data or not tmpdir:
        flash("No pending submission found. Please submit again.", "warning")
        return redirect(url_for("form.webform"))

    flat_form = ImmutableMultiDict(
        [(k, v) for k, vals in form_data.items() for v in vals]
    )

    try:
        token = session.get("access_token")
        invite_user("biosimdb", token)
        draft_id = prepare_for_invenio(flat_form, tmpdir)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None

        if status in (401, 403):
            session.pop("access_token", None)  # force fresh login
            session["post_login_redirect"] = url_for("form.resume_submit")
            flash(
                "Your login session is no longer valid for upload. "
                "Please sign in again and the submission will resume automatically.",
                "warning",
            )
            return redirect(url_for("login.login"))
        else:
            session.pop("access_token", None)  # force fresh login
            flash("Upload failed unexpectedly. Please try again.", "danger")

        # keep pending_form_data and pending_files_dir for retry
        return redirect(url_for("form.webform"))

    # success: now clear pending state
    session.pop("pending_form_data", None)
    session.pop("pending_files_dir", None)

    BASE_URL = current_app.config["BASE_URL"]
    record_url = f"{BASE_URL}/uploads/{draft_id}"
    return render_template("form/submit_success.html", record_url=record_url)
