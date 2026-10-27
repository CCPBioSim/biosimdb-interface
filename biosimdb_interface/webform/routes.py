#!/usr/bin/env python
"""Routes for rendering and processing the BioSimDB metadata webform.

The GET route renders the form and schema. The POST route resolves the
workflow, validates extracted files and metadata, then handles the requested
save or submission action.
"""

from flask import (
    render_template,
    request,
    session,
)

from ..core.workflows import WorkflowNotFound, get_workflow
from ..extract.validation import validate_with_mdanalysis
from ..schema.webform import WEBFORM_SCHEMA, get_simulation_metadata
from ..uploads.to_server import load_extracted_files
from . import webform_bp
from .services import (
    HANDLERS,
    build_metadata,
    check_ready,
    errors_response,
)


@webform_bp.route("/webform", methods=["GET"])
def webform():
    """Render the metadata form with the current simulation schema.

    Consumes the ``force_clear_client_state`` session flag when present and
    passes it to the template.

    Returns:
        Response: Rendered webform page.
    """
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


@webform_bp.route("/webform", methods=["POST"])
def webform_post():
    """Validate form data and handle a metadata save or submission request.

    Resolves the workflow ID from the request, checks extracted files and
    metadata, then dispatches to the handler for the ``save`` or ``submit``
    action.

    Returns:
        Response: JSON validation errors, a save response, or the response
        produced by the submission handler. Invalid or missing workflows and
        readiness failures return HTTP 400; validation errors use the default
        response status.
    """
    try:
        workflow = get_workflow()
    except WorkflowNotFound as exc:
        return errors_response([str(exc)], 400)

    tmpdir = workflow.tmpdir
    topo_path, traj_files = load_extracted_files(tmpdir)
    action = next((a for a in ("save", "submit") if a in request.form), None)

    if msg := check_ready(action, tmpdir, topo_path, traj_files):
        return errors_response([msg], 400)

    if msg := validate_with_mdanalysis(topo_path, traj_files):
        return errors_response([msg])

    if action not in ("save", "submit"):
        return errors_response(["Unknown action."], 400)

    json_form, groups = build_metadata(request.form, tmpdir, action)
    if groups:
        return errors_response(groups)

    return HANDLERS[action](json_form, tmpdir)
