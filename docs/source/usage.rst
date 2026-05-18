Usage
=====

Starting the application
------------------------

Run the Flask development server::

   flask --app biosimdb_interface run --debug -p 5002

Then visit http://127.0.0.1:5002/ in a browser.

Workflow
--------

1. **Upload files** — provide a topology file and one or more trajectory files.
2. **Extract metadata** — click *Extract Metadata from Files* to populate the form automatically using MDAnalysis and biosim-extractor.
3. **Review and edit** — inspect the extracted fields and fill in any missing information.
4. **Save or submit**:

   - *Save Metadata* downloads the metadata as a ``simulation_metadata.json`` file.
   - *Submit to BioSimDB* validates the metadata against the BioSim schema and uploads it to BioSimDB, redirecting you to the created record.

Authentication
--------------

Submitting to BioSimDB requires OAuth login. If you are not logged in, you
will be redirected to the BioSimDB login page, asked to verify the biosimdb-interface application and returned to the form
after a draft record has been submitted to BioSimDB.