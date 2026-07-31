2. Submit Data to BioSimDB
==========================

The ``biosimdb-interface`` is hosted as a webform, which automatically extracts useful data that describes a molecular dynamics simulation. Whenever you share your data, include this metadata with the simulation files to make your data more findable, accessible, interoperable and reuseable (`FAIR <https://www.go-fair.org/fair-principles/>`_).

To submit data to BioSimDB via our self-hosted webform, users are encouraged to first create an account with PSDI and join the BioSimDB community.

Once you have successfully joined the `BioSimDB <https://data-collections.psdi.ac.uk/communities/biosimdb/>`_ community on PSDI community data collections, you are ready to submit your data!

.. note::
    Users can still extract and save simulation metadata without logging into PSDI data collections. You just won't be able to submit your data to BioSimDB. We encourage you to share your data to an open data repository of your choosing.

Steps to Extract Simulation Metadata
------------------------------------

1. To extract simulation metadata, upload a topology and corresponding trajectory files to the "BioSim Data Extraction & Submission Form".

    - Optionally, upload an `aiida archive file <https://aiida-gromacs.readthedocs.io/>`_ containing the simulation provenance to extract further information about the simulation protocol.
    - Multiple trajectory files can be uploaded with a single associated topology file, both file types are required.
    - Various simulation file formats are accepted, provided they can be read using `MDAnalysis <https://www.mdanalysis.org/>`_, please ensure your files are compatible.
    - This form uses the `biosim-schema <https://biosim-schema.readthedocs.io/>`_ to define and group BioSim metadata. Missing terms or units? Please considering raising an issue or contributing to the `schema <https://github.com/CCPBioSim/biosim-schema/>`_.

2. Click "Extract Metadata", this will automatically populate applicable files in the webform.

3. Once you have extracted metadata, the webform fields are enabled, allowing you to manually populate any missing terms you wish to fill.

    - Click on each field name for further information about data field requirements.
    - Each field is validated against the schema, each time a user clicks to download or submit data. If there are any deviations from accepted terms, the errors will be displayed at the top of the webform.

4. Two options are available for your extracted simulation metadata:

    4a). Download the simulation metadata as a json file and share alongside simulation files.

    4b). Submit your simulation files and metadata in one step to BioSimDB, you will be directed to a login page and asked to authorize this application, once you are logged in.

    .. image:: ../_static/interface/authorise.png
        :width: 400
        :align: center


    Please click on "View Record" to continue and complete the data submission process in BioSimDB.

    .. image:: ../_static/interface/record_success.png
        :width: 400
        :align: center
