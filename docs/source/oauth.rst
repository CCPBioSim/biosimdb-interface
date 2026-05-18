OAuth Credentials
=================

Submitting metadata to BioSimDB requires OAuth2 credentials registered with
the BioSimDB instance you are targeting. BioSimDB is built on
`Invenio RDM <https://inveniordm.docs.cern.ch/>`_, which provides a developer
applications interface for managing OAuth clients.

Creating a developer application
---------------------------------

1. Log in to the BioSimDB instance (e.g.
   ``https://data-collections.psdi.ac.uk``).
2. Click your user avatar in the top-right corner and select
   **Applications** from the dropdown.
3. Under **Developer Applications**, click **New application**.
4. Fill in the form:

   - **Name** — a descriptive name, e.g. ``biosimdb-interface``.
   - **Description** — a short description of the app, e.g. ``App for BioSimDB custom webform for uploading to Invenio via API``.
   - **Website URL** — the website URL your app will be running on,
     e.g. ``http://127.0.0.1:5002`` for local development.
   - **Redirect URIs** — the callback URL your app will be running on,
     e.g. ``http://127.0.0.1:5002/callback`` for local development.
   - **Client type** — select **Confidential**.

5. Click **Save**. The ``Client ID`` and ``Client Secret`` will be displayed.

Setting the credentials
-----------------------

Add the values to your ``biosimdb_interface/.env`` file::

   CLIENT_ID=your_client_id
   CLIENT_SECRET=your_client_secret
   BASE_URL=https://data-collections-staging.psdi.ac.uk
   REDIRECT_URI=http://127.0.0.1:5002/callback

.. warning::

   Never commit ``.env`` to version control. Ensure it is listed in
   ``.gitignore``.

For production deployments, set these as environment variables directly
rather than using a ``.env`` file.

Targeting a different instance
-------------------------------

To connect to a different BioSimDB deployment (dev, staging, or production),
change ``BASE_URL`` and register a separate application on that instance.
The ``AUTH_URL``, ``TOKEN_URL``, and ``API_BASE`` values are derived
automatically from ``BASE_URL`` in the ``.env``.