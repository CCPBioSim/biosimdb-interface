#!/usr/bin/env python
from flask import Blueprint

extract_bp = Blueprint("extract", __name__)

from . import routes  # noqa: E402, F401
