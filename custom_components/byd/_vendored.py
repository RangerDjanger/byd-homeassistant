"""Make the vendored ``pybyd`` package importable.

The integration vendors the ``pybyd`` library under ``_vendor/`` instead of
declaring it as a PyPI ``manifest.json`` requirement. The vendored source uses
absolute ``import pybyd`` statements, so the ``_vendor`` directory is added to
``sys.path`` here. Importing this module (which happens from both ``__init__``
and ``config_flow`` before any ``pybyd`` import) guarantees the path is set up.
"""

from __future__ import annotations

import os
import sys

_VENDOR_DIR = os.path.join(os.path.dirname(__file__), "_vendor")

if _VENDOR_DIR not in sys.path:
    sys.path.insert(0, _VENDOR_DIR)
