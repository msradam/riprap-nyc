"""GLiNER (urchade/gliner_medium-v2.1) structured extraction.

Runs the typed-NER model over a paragraph of policy text and emits a
list of typed extractions:
  - nyc_location          (e.g. "Coney Island", "Hunts Point")
  - dollar_amount         (e.g. "$5.6 million")
  - date_range            (e.g. "fiscal year 2025-2027")
  - agency                (e.g. "NYC DEP", "NYCHA")
  - infrastructure_project (e.g. "Bluebelt expansion", "Newtown Creek
                            wastewater upgrade")

License: Apache-2.0 (NOT to be confused with `gliner_base`, which is
CC-BY-NC-4.0).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

CACHE = Path(__file__).parent / ".cache"
CACHE.mkdir(exist_ok=True)
os.environ.setdefault("HF_HOME", str(CACHE / "hf"))

ENTITY_LABELS = [
    "nyc_location",
    "dollar_amount",
    "date_range",
    "agency",
    "infrastructure_project",
]

DEFAULT_THRESHOLD = 0.45


@dataclass
class Extraction:
    label: str
    text: str
    score: float
    start: int
    end: int


def load_model():
    from gliner import GLiNER
    return GLiNER.from_pretrained("urchade/gliner_medium-v2.1",
                                  cache_dir=str(CACHE / "hf"))


def extract(model, paragraph: str, threshold: float = DEFAULT_THRESHOLD,
            labels: list[str] = None) -> list[Extraction]:
    labels = labels or ENTITY_LABELS
    raw = model.predict_entities(paragraph, labels, threshold=threshold)
    return [Extraction(label=r["label"], text=r["text"], score=float(r["score"]),
                       start=int(r["start"]), end=int(r["end"]))
            for r in raw]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True, help="Paragraph to extract from")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = ap.parse_args()
    model = load_model()
    out = extract(model, args.text, threshold=args.threshold)
    print(json.dumps([asdict(x) for x in out], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
