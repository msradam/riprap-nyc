"""Pre-compute the NYC public schools flood-exposure register.
Run: python scripts/build_schools_register.py

Resume-safe: re-running picks up after a network blip.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.assets import schools  # noqa: E402
from app.register_builder import build_register  # noqa: E402

if __name__ == "__main__":
    build_register("schools", schools.load,
                   meta_keys=("name", "address", "borough", "bbl", "bin"))
