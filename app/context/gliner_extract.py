"""GLiNER (urchade/gliner_medium-v2.1) typed-entity extraction over the
RAG retriever's top paragraphs.

Adds structured fields to the reconciler's grounding context. For each
RAG chunk the specialist emits, GLiNER produces a list of typed spans
with one of five labels:

    nyc_location          (e.g. "Coney Island")
    dollar_amount         (e.g. "$5.6 million")
    date_range            (e.g. "fiscal year 2025-2027")
    agency                (e.g. "NYC DEP")
    infrastructure_project (e.g. "Bluebelt expansion")

The doc_id for emission is `gliner_<source>` where `<source>` is the
RAG chunk's doc_id stripped of its `rag_` prefix. So `rag_comptroller`
becomes `gliner_comptroller`. The reconciler can then cite typed
fields with `[gliner_comptroller]`.

License: Apache-2.0 — `urchade/gliner_medium-v2.1` (NOT the
`gliner_base` variant, which is CC-BY-NC-4.0). See
experiments/shared/licenses.md.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

log = logging.getLogger("riprap.gliner")

ENTITY_LABELS = [
    "nyc_location",
    "dollar_amount",
    "date_range",
    "agency",
    "infrastructure_project",
]

DEFAULT_THRESHOLD = float(os.environ.get("RIPRAP_GLINER_THRESHOLD", "0.45"))
MODEL_NAME = os.environ.get("RIPRAP_GLINER_MODEL", "urchade/gliner_medium-v2.1")
ENABLE = os.environ.get("RIPRAP_GLINER_ENABLE", "1").lower() in ("1", "true", "yes")

_MODEL = None  # lazy


@dataclass
class Extraction:
    label: str
    text: str
    score: float


def _ensure_model():
    """Lazy GLiNER load. Returns None if disabled or load fails so
    callers can silently fall back to no-op."""
    global _MODEL
    if not ENABLE:
        return None
    if _MODEL is not None:
        return _MODEL
    try:
        from gliner import GLiNER
        log.info("gliner: loading %s", MODEL_NAME)
        _MODEL = GLiNER.from_pretrained(MODEL_NAME)
    except Exception:
        log.exception("gliner: load failed; specialist will no-op")
        _MODEL = False  # sentinel
    return _MODEL or None


def warm():
    _ensure_model()


def _source_short(rag_doc_id: str) -> str:
    """`rag_comptroller` -> `comptroller`. Anything not prefixed `rag_`
    passes through unchanged."""
    return rag_doc_id[4:] if rag_doc_id.startswith("rag_") else rag_doc_id


def extract_for_chunk(text: str, threshold: float = DEFAULT_THRESHOLD) -> list[Extraction]:
    model = _ensure_model()
    if model is None or not text:
        return []
    raw = model.predict_entities(text, ENTITY_LABELS, threshold=threshold)
    return [Extraction(label=r["label"], text=r["text"],
                       score=float(r["score"])) for r in raw]


def extract_for_rag_hits(hits: list[dict],
                         threshold: float = DEFAULT_THRESHOLD,
                         max_hits: int = 3) -> dict[str, dict]:
    """Run GLiNER on the top-`max_hits` RAG hits. Returns a dict keyed by
    short source id (e.g. "comptroller") with the structured payload
    that the FSM stores into state["gliner"] and that
    reconcile.build_documents() consumes."""
    out: dict[str, dict] = {}
    if not hits:
        return out
    for h in hits[:max_hits]:
        source = _source_short(h.get("doc_id", "rag_unknown"))
        ents = extract_for_chunk(h.get("text", ""), threshold=threshold)
        if not ents:
            continue
        # Dedup verbatim repeats (common in agency PDFs that repeat
        # "DEP" 13 times in a methodology section).
        seen = set()
        deduped: list[Extraction] = []
        for e in ents:
            key = (e.label, e.text.lower())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(e)
        out[source] = {
            "rag_doc_id": h.get("doc_id"),
            "title": h.get("title"),
            "paragraph_excerpt": h.get("text", "")[:240]
            + ("…" if len(h.get("text", "")) > 240 else ""),
            "n_entities": len(deduped),
            "entities": [{"label": e.label, "text": e.text,
                          "score": round(e.score, 3)} for e in deduped],
        }
    return out
