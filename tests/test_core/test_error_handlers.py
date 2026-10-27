from types import SimpleNamespace
from unittest.mock import Mock

from werkzeug.exceptions import NotFound

from biosimdb_interface.core import error_handlers
from biosimdb_interface.core.errors import ExternalAPIError, WebformError
from biosimdb_interface.core.workflows import WorkflowNotFound


def test_webform_error_returns_json_and_status(app):
    """Returns a webform error payload with its configured status code."""
    with app.test_request_context("/"):
        response, status = error_handlers.handle_metadata_extraction_error(
            WebformError(
                "Missing files",
                status_code=422,
                payload={"field": "trajectory"},
            )
        )

    assert status == 422
    assert response.get_json() == {
        "field": "trajectory",
        "error": "Missing files",
    }


def test_external_api_error_flashes_and_redirects(app):
    """Flashes a service error and redirects to the webform."""
    from flask import get_flashed_messages

    with app.test_request_context("/"):
        response = error_handlers.handle_external_api_error(
            ExternalAPIError("service unavailable")
        )

        assert response.status_code == 302
        assert response.location.endswith("/webform")
        assert get_flashed_messages(with_categories=True) == [
            (
                "danger",
                "A remote service is currently unavailable. Please try again later.",
            )
        ]


def test_unexpected_http_error_is_returned_unchanged(app):
    """Passes HTTP exceptions through unchanged."""
    error = NotFound()

    with app.test_request_context("/"):
        assert error_handlers.handle_unexpected_error(error) is error


def test_unexpected_extraction_error_returns_json_and_attempts_cleanup(
    app, monkeypatch
):
    """Returns a JSON error and attempts to remove the extraction workflow."""
    delete = Mock(side_effect=WorkflowNotFound("already expired"))
    monkeypatch.setattr(app.extensions["workflow_store"], "delete", delete)
    monkeypatch.setattr(
        error_handlers,
        "request",
        SimpleNamespace(
            endpoint="extract.extract_metadata",
            form={"workflow_id": "workflow-123"},
        ),
    )

    with app.test_request_context("/extract_metadata"):
        response, status = error_handlers.handle_unexpected_error(
            RuntimeError("bad file")
        )

    assert status == 500
    assert response.get_json()["error"].startswith("Extraction failed:")
    delete.assert_called_once_with("workflow-123")


def test_unexpected_non_extraction_error_flashes_and_redirects(app, monkeypatch):
    """Flashes an unexpected error and redirects to the webform."""
    from flask import get_flashed_messages

    monkeypatch.setattr(
        error_handlers,
        "request",
        SimpleNamespace(endpoint="webform.webform"),
    )

    with app.test_request_context("/webform"):
        response = error_handlers.handle_unexpected_error(RuntimeError("failure"))

        assert response.status_code == 302
        assert response.location.endswith("/webform")
        assert get_flashed_messages(with_categories=True)[0][0] == "danger"
