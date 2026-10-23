#!/usr/bin/env python
from flask import Blueprint

form_bp = Blueprint("form", __name__)

from . import errors, extract, submission, webform  # noqa: E402, F401
