#!/usr/bin/env python
"""Exception classes used by the BioSimDB interface.

Defines errors for webform responses, external service failures, and
conversion of submitted form values.
"""


class WebformError(Exception):
    """A webform error with an HTTP status and JSON response payload.

    Args:
        message (str): Error message returned to the client.
        status_code (int | None): HTTP status code; defaults to 400.
        payload (dict | None): Additional fields to include in the response.
    """

    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        super().__init__()
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        """Return the error as a JSON-serializable dictionary.

        The exception message is stored in the ``error`` field and takes
        precedence over any ``error`` value in the optional payload.

        Returns:
            dict: Error message and any additional payload fields.
        """
        rv = dict(self.payload or ())
        rv["error"] = self.message
        return rv


class ExternalAPIError(Exception):
    """An external API call failed or returned an unexpected response."""


class FormConversionError(ValueError):
    """Raised when form values can't be parsed; holds every message in ``errors``."""

    def __init__(self, errors, heading="Form conversion failed:"):
        self.errors = list(errors)
        self.heading = heading
        super().__init__(heading + "\n" + "\n".join(self.errors))
