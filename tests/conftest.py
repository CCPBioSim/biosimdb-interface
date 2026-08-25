import os
import uuid

import pytest

from biosimdb_interface import create_app
from biosimdb_interface.form.upload import cache_extracted_files


@pytest.fixture
def workflow(app):
    """Create and clean up one server-side tab workflow."""
    workflow_id = str(uuid.uuid4())

    with app.app_context():
        item = app.extensions["workflow_store"].reset(workflow_id)

    yield item

    with app.app_context():
        app.extensions["workflow_store"].delete(workflow_id)


@pytest.fixture
def extracted_workflow(app, workflow):
    """Create a workflow containing cached topology and trajectory files."""
    topology = os.path.join(workflow.tmpdir, "topol.gro")
    trajectory = os.path.join(workflow.tmpdir, "traj.xtc")

    with open(topology, "wb") as f:
        f.write(b"topology")
    with open(trajectory, "wb") as f:
        f.write(b"trajectory")

    with app.app_context():
        cache_extracted_files(
            workflow.tmpdir,
            {"topology": [topology], "trajectory": [trajectory]},
        )

    return workflow


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "UPLOAD_FOLDER": "/tmp",
            "WEBFORM_SCHEMA_PATH": "path/to/local/schema_webformfields.json",
            "JSONSCHEMA_PATH": "path/to/local/biosim_schema.schema.json",
            # OAuth — values don't matter for most tests
            "CLIENT_ID": "test",
            "CLIENT_SECRET": "test",
            "AUTH_URL": "http://localhost/auth",
            "TOKEN_URL": "http://localhost/token",
            "API_BASE": "http://localhost/api",
            "BASE_URL": "http://localhost",
            "REDIRECT_URI": "http://localhost/callback",
            "SCOPES": "test",
            "APPLICATION_BASE": "",
        }
    )
    yield app


@pytest.fixture
def client(app):
    return app.test_client()
