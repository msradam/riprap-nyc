"""Pre-compute the NYCHA developments flood-exposure register.
Run: python scripts/build_nycha_register.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.assets import nycha  # noqa: E402
from app.register_builder import build_register  # noqa: E402

if __name__ == "__main__":
    build_register("nycha", nycha.load,
                   meta_keys=("name", "address", "borough", "tds_num"))
