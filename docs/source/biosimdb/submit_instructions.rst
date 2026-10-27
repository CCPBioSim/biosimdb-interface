2. Submit Data to BioSimDB
==========================

The ``biosimdb-interface`` is hosted as a deposition webform, which automatically extracts useful data that describes a molecular dynamics simulation. Whenever you share your data, include this metadata with the simulation files to make your data more findable, accessible, interoperable and reuseable (`FAIR <https://www.go-fair.org/fair-principles/>`_).

To submit data to BioSimDB via our self-hosted webform, users are encouraged to first create an account on PSDI.

You will be prompted to join the `BioSimDB <https://data-collections.psdi.ac.uk/communities/biosimdb/>`_ community on PSDI community data collections, when you submit your data via the ``biosimdb-interface``.

Steps to Extract & Submit Simulation Data
-----------------------------------------

1. To extract simulation metadata, head over to the "BioSim Deposition" form.

    .. image:: ../_static/interface/interface.png
        :width: 400
        :align: center

2. Please login to your data-collections account and authorise the web application to submit data.

    .. image:: ../_static/interface/authorise.png
        :width: 400
        :align: center

3. Upload a topology, and trajectory files, then click "Extract Metadata", this will automatically populate applicable fields in the webform.

    .. image:: ../_static/interface/file_upload.png
        :width: 400
        :align: center

    - Multiple trajectory files can be uploaded with a single associated topology file, both file types are required.
    - Various simulation file formats are accepted, provided they can be read using `MDAnalysis <https://www.mdanalysis.org/>`_, please ensure your files are compatible.
    - This form uses the `biosim-schema <https://biosim-schema.readthedocs.io/>`_ to define and group BioSim metadata. Missing terms or units? Please consider raising an issue or contributing to the `schema <https://github.com/CCPBioSim/biosim-schema/>`_.

4. Once you have extracted metadata, the webform fields are enabled, allowing you to manually populate any missing terms you wish to fill.

    .. image:: ../_static/interface/metadata_fields.png
        :width: 400
        :align: center

    - Click on each field name for further information about data field requirements.
    - Each field is validated against the schema, each time a user clicks to download or submit data. If there are any deviations from accepted terms, the errors will be displayed at the top of the webform.

5. Two options are available for your extracted simulation metadata:

    .. image:: ../_static/interface/save_submit.png
        :width: 400
        :align: center

    5a). Download the simulation metadata as a json file and share alongside simulation files.

    5b). Submit your simulation files and metadata directly to BioSimDB.

6. If you submit to BioSimDB and your submission is successful, you will see a page similar to the image below. Please click on "View Record" to continue and complete the submission process in BioSimDB.

    .. image:: ../_static/interface/submitted.png
        :width: 600
        :align: center

7. If this is your first submission to BioSimDB, you will be sent an invite via email to join the BioSimDB community or you can accept directly at `data-collections <https://data-collections.psdi.ac.uk>`_, please accept this invitation in order to continue your submission to BioSimDB.

    .. image:: ../_static/interface/invite.png
        :width: 400
        :align: center

8. Please see the next instructions for filling in further information about yourself, your collaborators and your scientific research.
