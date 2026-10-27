#!/usr/bin/env python

from flask import (
    render_template,
    request,
    session,
)

from ..core.workflows import WorkflowNotFound
from ..extract.validation import validate_with_mdanalysis
from ..schema.webform import WEBFORM_SCHEMA, get_simulation_metadata
from ..uploads.to_server import load_extracted_files
from . import webform_bp
from .services import (
    HANDLERS,
    build_metadata,
    check_ready,
    errors_response,
    get_workflow,
)


@webform_bp.route("/webform", methods=["GET"])
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


@webform_bp.route("/webform", methods=["POST"])
def webform_post():
    """Validate and handle a metadata save or submission request."""
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
