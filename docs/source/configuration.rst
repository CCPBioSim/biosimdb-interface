Configuration
=============

The application is configured via a ``.env`` file located at
``biosimdb_interface/.env``. Copy the example below and fill in your values.

.. code-block:: ini

   # OAuth credentials (from your BioSimDB instance)
   CLIENT_ID=your_client_id
   CLIENT_SECRET=your_client_secret
   BASE_URL=https://data-collections.psdi.ac.uk

   # Flask
   SECRET_KEY=your_secret_key
   REDIRECT_URI=http://127.0.0.1:5002/callback

   # Schema paths
   WEBFORM_SCHEMA_PATH=/path/to/schema_webformfields.json
   ENGINE_MAPPING_PATH=/path/to/schema_enginemappings.json
   BIOSIM_SCHEMA_PATH=/path/to/biosim_schema/schema/biosim_schema.yaml

Generate a ``SECRET_KEY`` with::

   python3 -c "import secrets; print(secrets.token_hex(32))"
