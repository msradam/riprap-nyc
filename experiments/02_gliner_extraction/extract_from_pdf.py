"""Pull text from one of the corpus PDFs and run GLiNER over the
top-K paragraphs whose density of typed entities looks highest.

Phase 2 scope: prove the specialist plumbing works end-to-end on real
corpus content. We don't yet rank paragraphs by query relevance — that
job belongs to the existing Granite Embedding 278M retriever
(specialist 13 in the FSM). In production this specialist would
consume retriever output, not raw PDFs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CORPUS = Path(__file__).resolve().parents[2] / "corpus"

from extract import extract, load_model  # noqa: E402


def read_pdf_paragraphs(path: Path, min_chars: int = 200) -> list[str]:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    # Naive paragraph split; the PDFs are scanned/extracted text so
    # paragraphs are separated by blank lines or end-of-line patterns
    # that look like sentence-final punctuation followed by a newline.
    paras = re.split(r"\n\s*\n", text)
    paras = [re.sub(r"\s+", " ", p).strip() for p in paras]
    return [p for p in paras if len(p) >= min_chars]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True,
                    help="Path under corpus/, e.g. mta_resilience_2025.pdf")
    ap.add_argument("--top", type=int, default=3,
                    help="Run GLiNER on the top-N paragraphs by length")
    ap.add_argument("--threshold", type=float, default=0.45)
    args = ap.parse_args()

    pdf_path = CORPUS / args.pdf if not Path(args.pdf).is_absolute() else Path(args.pdf)
    paras = read_pdf_paragraphs(pdf_path)
    if not paras:
        print(f"No paragraphs ≥200 chars found in {pdf_path}", file=sys.stderr)
        return 1

    # "Top-N by length" is a placeholder ranker — see module docstring.
    top = sorted(paras, key=len, reverse=True)[:args.top]

    print("Loading GLiNER (~150 MB)…", file=sys.stderr)
    model = load_model()

    out = []
    for p in top:
        ents = extract(model, p, threshold=args.threshold)
        out.append({"paragraph": p[:400] + ("…" if len(p) > 400 else ""),
                    "n_entities": len(ents),
                    "entities": [
                        {"label": e.label, "text": e.text,
                         "score": round(e.score, 3)}
                        for e in ents
                    ]})
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
