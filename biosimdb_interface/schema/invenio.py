#!/usr/bin/env python3
"""
Minimal metadata template for submitting to Invenio.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

today = datetime.now(ZoneInfo("Europe/London")).date()

INVENIO_FORM_EMPTY = {
    "access": {"files": "public", "record": "public"},
    "files": {"enabled": "true"},
    "custom_fields": {"dsmd": []},
    "metadata": {
        "description": "",
        "identifiers": [
            {
                "identifier": "",  # add publication DOI here
            }
        ],
        "publication_date": today.isoformat(),  # YYYY-MM-DD
        "publisher": "PSDI",
        "resource_type": {"id": "model"},
        "rights": [{"id": "cc-by-4.0"}],
        "subjects": [
            {"subject": "Biomolecular Simulation"},
            {"subject": "Molecular Dynamics"},
        ],
        "title": "",
        "version": "v1",
    },
}
