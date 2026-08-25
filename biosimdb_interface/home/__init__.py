#!/usr/bin/env python
from flask import Blueprint

home_bp = Blueprint("home", __name__)

from . import home  # noqa: E402, F401
