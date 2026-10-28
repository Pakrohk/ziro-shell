# Configuration file for the Sphinx documentation builder.

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

project = "ziro"
copyright = "2026, Pakrohk"
author = "Pakrohk"
release = "1.2.0"

extensions = [
    "cyclopts.ext.sphinx",
]

root_doc = "cli-reference"

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for manual page output ------------------------------------------
man_pages = [
    ("cli-reference", "ziro", "Ziro Shell CLI Manual", ["Pakrohk"], 1),
]
