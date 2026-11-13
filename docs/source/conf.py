# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

#import importlib.metadata
import warnings

project = "biosimdb-interface"
copyright = "2026, CCPBioSim"
release = "2.2.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.mathjax",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.extlinks",
    "autoapi.extension",
]

# Napoleon: Google-style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_use_param = True
napoleon_use_ivar = True

# API reference generated from the source by sphinx-autoapi
autoapi_dirs = ["../../biosimdb_interface"]
autoapi_root = "reference"
autoapi_add_toctree_entry = False
autoapi_member_order = "groupwise"
# Include the __init__ docstring, where the constructor arguments are documented
autoapi_python_class_content = "both"
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
]

# Show type hints in the parameter list rather than the signature
autodoc_typehints = "description"
add_module_names = False
python_maximum_signature_line_length = 88

templates_path = ["_templates"]
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "ccpbiosim_sphinx_theme"
html_context = {"github_repo": "biosimdb-interface"}
html_static_path = ["_static"]
html_css_files = [
    "styles.css",
]

warnings.filterwarnings("ignore", message="netCDF4 is not available")
