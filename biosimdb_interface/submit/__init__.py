#!/usr/bin/env python
from flask import Blueprint

submit_bp = Blueprint("submit", __name__)

from . import routes  # noqa: E402, F401
