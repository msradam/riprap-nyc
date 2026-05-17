"""local_corpus_with_ner — a text-pebble that owns both retrieval and NER.

Wraps the existing static-PDF retrieval (`app.rag.retrieve`) and Flair/
OntoNotes NER (`app.context.entity_extract.extract_for_rag_hits`) into
one pebble. Replaces the old `step_rag` + `step_gliner` pair in the
Burr graph.

The pebble's value carries both shapes downstream consumers used to
read directly from `state["rag"]` and `state["gliner"]`:

    {
      "query":     "...search string actually used...",
      "rag_hits":  [{doc_id, citation, page, text, score}, ...],
      "entities":  {"<source_short>": {entities: [...], paragraph_excerpt, ...}, ...},
      "n_hits":    int,
      "n_entities": int,
    }

The calling Burr action also mirrors `rag_hits` to `state["rag"]` and
`entities` to `state["gliner"]` so the legacy reconciler prompt
(`app.reconcile.build_documents`) doesn't need to change. Future
follow-up: migrate `build_documents` to read `state["policy_corpus"]`
directly and drop the backward-compat mirrors.

Manifest config:

    adapter: local_corpus_with_ner
    config:
      k: 3                        # top-k chunks to retrieve
      min_score: 0.45             # similarity threshold
      ner_threshold: 0.55         # NER score floor
      query_template: "..."       # falls back to extras['query']
"""
from __future__ import annotations

from typing import Any

from riprap.core.pebbles.base import BasePebble, PebbleResult, SpatialQuery


class LocalCorpusWithNERPebble(BasePebble):
    """Combined retrieval + NER over a local PDF corpus.

    The corpus path is configured in `app.rag` (i.e. `corpus/`) and
    embedded once at startup. This adapter is the pebble-shaped seam
    over the existing rag + entity_extract modules so the Burr graph
    can compose text-pebbles uniformly with data-pebbles.
    """

    def _fetch_raw(self, query: SpatialQuery) -> PebbleResult:
        cfg = self.manifest.config or {}
        k = int(cfg.get("k", 3))
        min_score = float(cfg.get("min_score", 0.45))
        ner_threshold = float(cfg.get("ner_threshold", 0.55))

        # Query string priority:
        #   1. extras["query"] — supplied by the calling action,
        #      typically built from geocode + hazard signals
        #   2. extras["query_template"].format(**extras) — declarative
        #   3. manifest.config["query_template"] — static deployment-default
        q = (query.extras or {}).get("query")
        if not q:
            tmpl = ((query.extras or {}).get("query_template")
                    or cfg.get("query_template"))
            if tmpl:
                try:
                    q = tmpl.format(**(query.extras or {}))
                except (KeyError, IndexError, ValueError):
                    q = tmpl
        if not q:
            return PebbleResult(
                pebble_id=self.id, value=None,
                error="local_corpus_with_ner: no query (extras['query'] or config.query_template)",
            )

        # The retrieval + NER modules live in app/ — they own model
        # loading, remote/local fallback, sentence-transformer + Flair
        # warm-up. Import lazily so the adapter module loads fast.
        try:
            from app.rag import retrieve as rag_retrieve
            hits = rag_retrieve(q, k=k, min_score=min_score)
        except Exception as e:  # noqa: BLE001 — surface as offline
            return PebbleResult(
                pebble_id=self.id, value=None, offline=True,
                error=f"rag retrieve failed: {type(e).__name__}: {e}",
            )

        # NER over the retrieved hits. extract_for_rag_hits returns
        # the legacy gliner-shaped dict keyed by source short name.
        try:
            from app.context.entity_extract import extract_for_rag_hits
            entities = extract_for_rag_hits(hits, threshold=ner_threshold)
        except Exception as e:  # noqa: BLE001
            entities = {}
            ner_err = f"{type(e).__name__}: {e}"
        else:
            ner_err = None

        n_entities = sum(len((v or {}).get("entities") or []) for v in entities.values())
        value: dict[str, Any] = {
            "query": q,
            "rag_hits": list(hits),
            "entities": entities,
            "n_hits": len(hits),
            "n_entities": n_entities,
        }
        if ner_err:
            value["ner_err"] = ner_err

        return PebbleResult(pebble_id=self.id, value=value)
