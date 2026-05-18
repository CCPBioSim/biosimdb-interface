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

Tests use ``pytest`` and are located in the ``tests/`` directory::

   pytest

To see a coverage report::

   pytest --cov=biosimdb_interface --cov-report=term-missing

Linting and formatting
----------------------

The project uses ``ruff`` for linting and formatting::

   ruff check .
   ruff format .

Pre-commit hooks
----------------

Pre-commit hooks run ``ruff``, ``pyupgrade``, and several file-hygiene checks
automatically before each commit. To install them::

   pre-commit install

To run all hooks manually across the whole codebase::

   pre-commit run --all-files

Hook versions are pinned in ``.pre-commit-config.yaml`` at the repository root.

Continuous integration
----------------------

CI runs automatically on every push to ``main`` via GitHub Actions
(``.github/workflows/ci.yaml``). The following jobs must pass before merging:

- **Lint** — ``ruff check`` and ``ruff format --check``
- **Tests** — ``pytest`` on Python 3.12 and 3.13
- **Docs** — Sphinx HTML build with warnings treated as errors
- **Pre-commit** — all pre-commit hooks across all files

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
3. Ensure all CI jobs pass locally: ``pytest``, ``ruff check .``, and ``pre-commit run --all-files``.
4. Open a pull request against ``main`` with a clear description of the change.
