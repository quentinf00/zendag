# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information


# zendag/docs/conf.py

import os
import sys
from datetime import datetime

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
# This makes sure Sphinx can find your 'zendag' package for autodoc.
sys.path.insert(0, os.path.abspath('../..'))  # Points to the root of the Git repo
sys.path.insert(0, os.path.abspath('..')) # Points to the 'zendag' package directory itself

# -- Project information -----------------------------------------------------

project = 'ZenDag'
copyright = '2025, Quentin Febvre'
author = 'Quentin Febvre'
release = '0.1.0'
copyright = f'{datetime.now().year}, {author}'

# The full version, including alpha/beta/rc tags
# Attempt to get version from the package itself
try:
    from zendag import __version__ as release
except ImportError:
    release = '0.1.0' # Fallback version

version = '.'.join(release.split('.')[:2]) # The short X.Y version

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    'sphinx.ext.autodoc',         # Include documentation from docstrings
    'sphinx.ext.autosummary',     # Generate summary tables for autodoc
    'sphinx.ext.napoleon',        # Support for Google and NumPy style docstrings
    'sphinx.ext.viewcode',        # Add links to CPython source code for Python objects
    'sphinx.ext.intersphinx',     # Link to other projects' documentation
    'sphinx.ext.todo',            # Support for todo items
    'myst_nb',                    # For parsing Jupyter Notebooks and MyST Markdown files
    'sphinx_copybutton',          # Adds a "copy" button to code blocks
    'sphinx_autodoc_typehints',   # Better rendering of type hints in API docs
    # 'sphinx.ext.mathjax',       # For math equations (if needed)
    # 'sphinx_design',            # For more advanced visual elements (cards, grids etc.)
]

# MyST-NB specific configurations for notebooks and markdown
myst_enable_extensions = [
    "amsmath",          # For AMS math environments (if using math)
    "colon_fence",      # For admonitions (note, warning, etc.) and other directives
    "deflist",
    "dollarmath",       # For inline and block math using $ and $$
    "html_image",
    # "linkify",          # Automatically convert URLs to links
    "replacements",
    "smartquotes",
    "substitution",
    "tasklist",
]
myst_heading_anchors = 3  # Auto-generate header anchors up to level 3 for deep linking
myst_footnote_transition = True
# myst_number_code_blocks = ["python"] # Optionally number python code blocks

# MyST-NB Notebook execution settings
# "auto": execute notebooks that are missing outputs
# "force": execute all notebooks
# "cache": execute notebooks missing outputs and cache results
# "off": do not execute notebooks
nb_execution_mode = "cache" # Good for CI speed, "force" for ensuring all run
nb_execution_timeout = 180  # Seconds, increase if notebooks are long-running
nb_execution_allow_errors = False # Fail the build if a notebook cell errors
# nb_kernel_rgx_aliases = {".*python.*": "python3"} # If needed to map kernel names

# Napoleon settings (for Google/NumPy docstrings)
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_warnings = True
napoleon_use_ivar = True # For instance variables
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = True
napoleon_type_aliases = None
napoleon_attr_annotations = True

# Autodoc settings
autodoc_member_order = 'bysource' # Order members by source order
autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__', # Can add other special methods if desired
    'undoc-members': False, # Set to True to include members without docstrings
    'show-inheritance': True,
}
# autosummary_generate = True # Creates .rst files for autosummary
# autosummary_imported_members = True

# sphinx-autodoc-typehints settings
set_type_checking_flag = True # Important for sphinx-autodoc-typehints
always_document_param_types = True # Show type hints for all parameters
typehints_fully_qualified = False # Use short names for types if possible
typehints_formatter = None # Use default formatter

# Intersphinx mapping (example: link to Python documentation)
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'numpy': ('https://numpy.org/doc/stable/', None),
    'pandas': ('https://pandas.pydata.org/pandas-docs/stable/', None),
    # 'hydra': ('https://hydra.cc/docs/next/', None), # Check current URL for Hydra
    # 'dvc': ('https://dvc.org/doc/', None),
    # 'mlflow': ('https://mlflow.org/docs/latest/', None),
    'pytest': ('https://docs.pytest.org/en/stable/', None),
    'intake': ('https://intake.readthedocs.io/en/latest/', None),
    'fsspec': ('https://filesystem-spec.readthedocs.io/en/latest/', None),
    'hydra_zen': ('https://mit-ll-responsible-ai.github.io/hydra-zen/', None),
}

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'myst-nb',
    '.ipynb': 'myst-nb', # If you have .ipynb files directly in docs source
}

# The master toctree document.
master_doc = 'index' # Or 'contents' if you named it that

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', '**.ipynb_checkpoints']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx' # or 'friendly', 'monokai', etc.
# pygments_dark_style = "monokai" # For dark mode if theme supports it

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True # Set to False for public releases


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages. See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme' # A popular choice
# html_theme = 'furo' # Another excellent modern theme
# html_theme = 'pydata_sphinx_theme'

# Theme options are theme-specific and customize the look and feel.
# Example for sphinx_rtd_theme:
html_theme_options = {
    'logo_only': False,
    'display_version': True,
    'prev_next_buttons_location': 'bottom',
    'style_external_links': True,
    # 'style_nav_header_background': 'white',
    # Toc options
    'collapse_navigation': True,
    'sticky_navigation': True,
    'navigation_depth': 4,
    'includehidden': True,
    'titles_only': False
}

# Example for Furo theme:
# html_theme_options = {
#     "light_css_variables": {
#         "color-brand-primary": "#7C4DFF", # Example color
#         "color-brand-content": "#7C4DFF",
#     },
# }


# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# Custom CSS files. Relative to html_static_path.
html_css_files = [
    'css/custom.css', # Create this file in docs/_static/css/ for your custom styles
]

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
html_show_copyright = True

# HTML logo (optional)
# html_logo = "_static/logo.png" # Place your logo in docs/_static/

# HTML Favicon (optional)
# html_favicon = "_static/favicon.ico"

# If false, no module index is generated.
html_domain_indices = True

# If false, no index is generated.
html_use_index = True

# If true, the index is split into individual pages for each letter.
html_split_index = False

# If true, links to the reST sources are added to the pages.
html_show_sourcelink = True # Set to False for public release if you don't want this


# -- Options for LaTeX output ---------------------------------------------
# (Usually not needed for online docs, but good to have placeholders)
latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    # 'papersize': 'letterpaper',
    # The font size ('10pt', '11pt' or '12pt').
    # 'pointsize': '10pt',
    # Additional stuff for the LaTeX preamble.
    # 'preamble': '',
    # Latex figure (float) alignment
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  (master_doc, f'{project}.tex', f'{project} Documentation', author, 'manual'),
]

# -- Make sure JuypterLite files are excluded if you were to use it --
# jupyterlite_dir = "."
# jupyterlite_contents = ["notebooks"] # specify contents to be copied
# jupyterlite_config = "jupyterlite_config.json"
# exclude_patterns.append(jupyterlite_dir + "/_output")
