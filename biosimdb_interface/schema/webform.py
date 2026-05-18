#!/usr/bin/env python3
"""
Read in schema for webform fields and save to python object.
"""

import os

from biosimdb_interface.schema.helpers import SchemaPopulator

schema_path = os.getenv("WEBFORM_SCHEMA_PATH", "")
populator = SchemaPopulator(schema_path=schema_path)
simulation_metadata = populator.load_schema()


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
        "simulation_metadata": simulation_metadata,
    }
}
