import pytest
from biosimdb_interface import create_app

@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test",
        "UPLOAD_FOLDER": "/tmp",
        "WEBFORM_SCHEMA_PATH": "path/to/local/schema_webformfields.json",
        "JSONSCHEMA_PATH": "path/to/local/biosim_schema.schema.json",
        # OAuth — values don't matter for most tests
        "CLIENT_ID": "test", "CLIENT_SECRET": "test",
        "AUTH_URL": "http://localhost/auth",
        "TOKEN_URL": "http://localhost/token",
        "API_BASE": "http://localhost/api",
        "BASE_URL": "http://localhost",
        "REDIRECT_URI": "http://localhost/callback",
        "SCOPES": "test",
    })
    yield app

@pytest.fixture
def client(app):
    return app.test_client()
