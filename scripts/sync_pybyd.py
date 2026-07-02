"""Sync the vendored ``pybyd`` package from a local pyBYD checkout.

Usage (from the repo root)::

    python scripts/sync_pybyd.py [PATH_TO_PYBYD_REPO]

If no path is given it defaults to ``../pyBYD`` relative to this repository.
The script copies ``src/pybyd`` into
``custom_components/byd/_vendor/pybyd`` and strips ``__pycache__`` dirs.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO_ROOT / "custom_components" / "byd" / "_vendor" / "pybyd"


def main() -> int:
    pybyd_repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else (REPO_ROOT.parent / "pyBYD")
    src = pybyd_repo / "src" / "pybyd"
    if not src.is_dir():
        print(f"error: {src} not found (is the pyBYD repo path correct?)", file=sys.stderr)
        return 1

    if VENDOR_DIR.exists():
        shutil.rmtree(VENDOR_DIR)
    shutil.copytree(src, VENDOR_DIR)

    removed = 0
    for cache in VENDOR_DIR.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
        removed += 1

    print(f"Vendored pybyd from {src}")
    print(f"  -> {VENDOR_DIR}")
    print(f"  removed {removed} __pycache__ dir(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
