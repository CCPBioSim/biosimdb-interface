#!/usr/bin/env python


class WebformError(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        super().__init__()
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
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
