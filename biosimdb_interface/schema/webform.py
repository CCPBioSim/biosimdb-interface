#!/usr/bin/env python3
"""
Webform schema definition for the BioSim metadata submission form.

Loads the simulation metadata schema from ``WEBFORM_SCHEMA_PATH`` (set via
environment variable) and exposes it as part of :data:`WEBFORM_SCHEMA`, which
drives the rendered HTML form fields.

The schema is cached in memory and reloaded automatically when the source file
changes (detected via modification time), so server restarts are not required
after schema updates.
"""

import os

from biosimdb_interface.schema.helpers import SchemaPopulator

# Module-level cache for the simulation metadata schema.
# Reloaded automatically when the source file's modification time changes.
_cache = {"schema": None, "mtime": None}


def get_simulation_metadata():
    """Return the simulation metadata schema, reloading from disk if the file has changed.

    Compares the current modification time of ``WEBFORM_SCHEMA_PATH`` against the
    cached value. If the file has been modified since the last load, the schema is
    re-read before returning.

    Returns:
        dict: Parsed simulation metadata schema.
    """
    path = os.getenv("WEBFORM_SCHEMA_PATH")
    if not path or not os.path.exists(path):
        # Return an empty schema
        return {}

    mtime = os.path.getmtime(path)
    if _cache["mtime"] != mtime:
        _cache["schema"] = SchemaPopulator(schema_path=path).load_schema()
        _cache["mtime"] = mtime
    return _cache["schema"]


# Top-level webform schema object passed to the Jinja2 template.
# ``simulation_metadata`` is loaded fresh on first access via get_simulation_metadata().
WEBFORM_SCHEMA = {
    "data": {
        "title": "BioSim Data Extraction & Submission Form",
        "description": "This form automatically extracts useful data that describes a molecular dynamics simulation. Whenever you share your data, include this metadata with the simulation files to make your data more findable, accessible, interoperable and reuseable (FAIR).",
        "guidance": {
            "label": "Please Note:",
            "options": [
                "To extract simulation metadata, please upload a topology and corresponding trajectory file/s. Optionally, upload the aiida archive file containing the simulation provenance to extract further information about the simulation protocol.",
                "Multiple trajectory files can be uploaded with a single associated topology file, both file types are required.",
                'Various simulation file formats are accepted and read using <a href="https://www.mdanalysis.org/" target="_blank" class="text-reset"> MDAnalysis</a>, please ensure your files are compatible.',
                "This form uses the following schema to define and group BioSim metadata: XXXX. Missing terms or units? Please considering raising an issue or contributing to the schema.",
                'Automatically add metadata associated with each entry using the "Extract metadata" button. Please fill in any missing metadata fields manually where applicable, click on each field name for further information about data field requirements.',
                "Two options are available for your extracted simulation metadata: <ol> <li> Download the simulation metadata as a json file and share alongside simulation files. </li> <li> Submit your simulation files and metadata in one step to BioSimDB, you will be directed to a login page and asked to authorize this application. Please continue and complete the data submission process in BioSimDB. </li> </ol>",
            ],
        },
        "repeatable": True,
        "max": 1,
        "files": {
            "topology": {
                "label": "Upload topology file",
                "multiple": False,
                "required": True,
            },
            "trajectory": {
                "label": "Upload trajectory file/s",
                "multiple": True,
                "required": True,
            },
            "aiida": {
                "label": "Upload AiiDA archive file",
                "multiple": False,
            },
        },
    }
}
