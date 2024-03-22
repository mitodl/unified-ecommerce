# Configuration file for the Sphinx documentation builder. For a full
# list of options, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

project = "Unified Ecommerce"
copyright = "2024, OL Engineering" # noqa: A001
author = "OL Engineering"

extensions = [
    "sphinxcontrib.mermaid",
    "myst_parser",
]

templates_path = ["_templates"]

exclude_patterns = []

html_permalinks_icon = "§"
html_theme = "nature"

html_static_path = ["_static"]
