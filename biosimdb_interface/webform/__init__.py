#!/usr/bin/env python
from flask import Blueprint

webform_bp = Blueprint("webform", __name__)

from . import routes  # noqa: E402, F401
