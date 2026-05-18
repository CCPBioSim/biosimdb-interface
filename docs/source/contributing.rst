Contributing
============

We welcome contributions. This page covers how to set up a development
environment, run tests, lint code, and build the documentation.

Setting up for development
--------------------------

Clone the repository and install in editable mode with all optional
dependency groups::

   git clone https://github.com/CCPBioSim/biosimdb-interface.git
   cd biosimdb-interface
   conda create -n biosimdb-interface-dev python=3.12
   conda activate biosimdb-interface-dev
   pip install -e ".[testing,docs,pre-commit]"

Running the tests
-----------------

Tests use `pytest` and are located in the ``tests/`` directory::

   pytest

To see a coverage report::

   pytest --cov=biosimdb_interface --cov-report=term-missing

Linting and formatting
----------------------

The project uses `ruff` for linting and formatting::

   ruff check .
   ruff format .

To run checks automatically on each commit, install the pre-commit hooks::

   pre-commit install

Building the documentation
--------------------------

Build the HTML docs locally from the ``docs/`` directory::

   cd docs
   make html

The built docs will be in ``docs/build/html/``. Open
``docs/build/html/index.html`` in a browser to preview them.

To clean the build and rebuild from scratch::

   make clean html

The documentation is hosted on ReadTheDocs and is rebuilt automatically
on each push to ``main``. The ReadTheDocs configuration is in
``.readthedocs.yaml`` at the repository root.

Submitting changes
------------------

1. Create a branch from ``main`` for your change.
2. Make your changes and add tests where appropriate.
3. Ensure ``pytest`` and ``ruff check .`` both pass.
4. Open a pull request against ``main`` with a clear description of the change.