#!/usr/bin/env python
import os

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

from biosimdb_interface.schema.webform import WEBFORM_SCHEMA, get_simulation_metadata

from . import form_bp
from .upload import prepare_for_invenio, save_pending_submission
from .utils import form_to_json, remove_empty_fields
from .validation import validate_with_mdanalysis


@form_bp.route("/webform", methods=["GET", "POST"])
def webform():
    """Render the metadata submission form and handle save/submit actions.

    On GET, renders the empty form. On POST, validates uploaded files with
    MDAnalysis, then either downloads form data as JSON (save) or initiates
    submission to BioSimDB (submit).
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
    Called automatically by the loading page after login. Clears pending
    session data after upload and renders the success page with the record URL.
    """
    from werkzeug.datastructures import ImmutableMultiDict

    form_data = session.pop("pending_form_data", None)
    tmpdir = session.pop("pending_files_dir", None)
    flat_form = ImmutableMultiDict(
        [(k, v) for k, vals in form_data.items() for v in vals]
    )
    draft_id = prepare_for_invenio(flat_form, tmpdir)
    BASE_URL = current_app.config["BASE_URL"]
    record_url = f"{BASE_URL}/uploads/{draft_id}"
    return render_template("form/submit_success.html", record_url=record_url)
