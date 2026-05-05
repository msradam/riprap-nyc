"""Granite Embedding Reranker R2 (cross-encoder, 149 M).

Sits between the existing Granite Embedding 278 M retriever (top-K=20)
and the reconciler (top-3). Sidecar via sentence-transformers
CrossEncoder — vLLM `--task score` is explicitly out of scope.

License: Apache-2.0 (verified — `ibm-granite/granite-embedding-reranker-
english-r2`).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

CACHE = Path(__file__).parent / ".cache"
CACHE.mkdir(exist_ok=True)
os.environ.setdefault("HF_HOME", str(CACHE / "hf"))

REPO = "ibm-granite/granite-embedding-reranker-english-r2"


@dataclass
class Ranking:
    rank: int
    score: float
    text: str


def load_model():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(REPO, cache_folder=str(CACHE / "hf"))


def rerank(model, query: str, candidates: list[str],
           top_k: int = 3) -> list[Ranking]:
    pairs = [[query, c] for c in candidates]
    scores = model.predict(pairs)
    indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    return [Ranking(rank=i + 1, score=float(s), text=candidates[idx])
            for i, (idx, s) in enumerate(indexed[:top_k])]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--candidates-file", required=True,
                    help="One candidate paragraph per line")
    ap.add_argument("--top-k", type=int, default=3)
    args = ap.parse_args()

    candidates = [ln.strip() for ln in
                  Path(args.candidates_file).read_text().splitlines()
                  if ln.strip()]
    if not candidates:
        print("No candidates provided", file=sys.stderr)
        return 1

    print("Loading reranker (~600 MB)…", file=sys.stderr)
    t0 = time.time()
    model = load_model()
    print(f"reranker load: {time.time() - t0:.2f}s", file=sys.stderr)

    t0 = time.time()
    ranked = rerank(model, args.query, candidates, top_k=args.top_k)
    print(f"rerank {len(candidates)} -> {args.top_k}: "
          f"{time.time() - t0:.3f}s", file=sys.stderr)
    print(json.dumps([asdict(r) for r in ranked], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
