#!/usr/bin/env python
"""
Home page for biosimdb-interface
"""

from flask import (
    current_app,
    render_template,
    url_for,
)

from ..home import home_bp


@home_bp.route("/", methods=["GET"])
def home():
    """Landing page with BioSimDB overview and quick links."""
    return render_template(
        "home/home.html",
        links={
            "deposit": url_for("form.webform"),
            "biosimdb": f"{current_app.config.get('BASE_URL', '').rstrip('/')}/communities/biosimdb",
            "docs": "https://biosimdb-interface.readthedocs.io/",
            "github": "https://github.com/CCPBioSim/biosimdb-interface",
            "extract": "https://biosim-extractor.readthedocs.io/en/latest/",
            "schema": "https://biosim-schema.readthedocs.io/en/latest/",
            "aiida_gromacs": "https://aiida-gromacs.readthedocs.io/en/latest/",
            "roadmap": "https://example.com/",
            "zulip": "https://example.com/",
            "policy": "https://data-collections.psdi.ac.uk/communities/biosimdb/curation-policy",
            "instructions": "https://biosimdb-interface.readthedocs.io/en/latest/biosimdb_intro.html",
            "tutorials": "https://biosimdb-interface.readthedocs.io/en/latest/biosimdb_intro.html",
        },
    )
