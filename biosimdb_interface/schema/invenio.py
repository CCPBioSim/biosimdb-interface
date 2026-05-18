INVENIO_FORM_EMPTY = {
    "access": {"files": "public", "record": "public"},
    "files": {"enabled": "true"},
    "custom_fields": {"dsmd": []},
    "metadata": {
        "creators": [
            {
                "affiliations": [{"name": ""}],
                "person_or_org": {
                    "family_name": "",
                    "given_name": "",
                    "identifiers": [
                        {
                            "identifier": "",
                        }
                    ],
                    "type": "personal",
                },
            }
        ],
        "description": "",
        "identifiers": [
            {
                "identifier": "",  # add publication DOI here
            }
        ],
        "publication_date": "",  # YYYY-MM-DD
        "publisher": "PSDI",
        "resource_type": {
            # "id": "dataset"
            "id": "model"  # for testing in staging
        },
        "rights": [{"id": "cc-by-4.0"}],
        "subjects": [
            {"subject": "Biomolecular Simulation"},
            {"subject": "Molecular Dynamics"},
        ],
        "title": "",
        "version": "v1",
    },
}


INVENIO_DSMD_TEMPLATE = {
    "software": "GROMACS",
    "software_version": "",
    "molecular_model": "",
    "simulation_method": "",
    "timestep": "2",
    "framestep": "2",
    "length": "",
    "temperature": "298",
    "pressure": "",
    "ensemble": "",
    "box_type": "",
    "trajectories": "",
    "force_fields": "",
    "experimental_structures": "",
    "pH": "7",
    "membrane": "",
    "ligands": "",
    "sequences": "",
    "average_energy": "",
    "box_dimensions": "",
    "long_range_cutoff": "",
    "thermostat": "",
    "barostat": "",
    "atom_count": "100",
    "wall_time": "",
}
