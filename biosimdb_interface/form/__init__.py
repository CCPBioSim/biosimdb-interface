#!/usr/bin/env python
from flask import Blueprint

form_bp = Blueprint("form", __name__)

from . import extract, home, webform  # noqa: E402, F401
