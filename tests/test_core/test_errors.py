from biosimdb_interface.core.errors import FormConversionError, WebformError


def test_webform_error_defaults_and_serializes_message():
    """Uses the default status and includes the message in its response body."""
    error = WebformError("Missing files")

    assert error.status_code == 400
    assert error.to_dict() == {"error": "Missing files"}


def test_webform_error_custom_status_and_payload():
    """Applies a custom status and merges payload fields with the error message."""
    error = WebformError(
        "Invalid upload",
        status_code=422,
        payload={"field": "trajectory"},
    )

    assert error.status_code == 422
    assert error.to_dict() == {
        "field": "trajectory",
        "error": "Invalid upload",
    }


def test_webform_error_message_overrides_payload_error():
    """Keeps the exception message as the serialized error."""
    error = WebformError("Current message", payload={"error": "Old message"})

    assert error.to_dict()["error"] == "Current message"


def test_form_conversion_error_stores_errors_and_heading():
    """Stores all conversion errors and formats the exception message."""
    messages = ["Invalid date", "Invalid number"]

    error = FormConversionError(messages, heading="Please correct these fields:")

    assert error.errors == messages
    assert error.heading == "Please correct these fields:"
    assert str(error) == "Please correct these fields:\nInvalid date\nInvalid number"


def test_form_conversion_error_uses_default_heading():
    """Uses the default heading when none is provided."""
    error = FormConversionError(["Invalid value"])

    assert error.heading == "Form conversion failed:"
    assert str(error) == "Form conversion failed:\nInvalid value"
