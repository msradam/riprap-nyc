"""Granite Embedding 278M RAG over the NYC flood-resilience policy corpus.

Specialists this powers:
  step_rag — for any query (geo + intent), retrieve top-k relevant
             policy paragraphs from HMP/NPCC4/DEP/MTA/NYCHA/Comptroller
             and emit them as <document id="rag_*"> blocks.

We chunk page-by-page with a soft target of ~600 chars per chunk, embed
once at startup, and store a numpy matrix + FAISS L2 index in memory.
The index is small (~1k chunks across 5 PDFs).
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger("riprap.rag")

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"
EMBED_MODEL_NAME = "ibm-granite/granite-embedding-278m-multilingual"

CORPUS_META = {
    "dep_wastewater_2013.pdf": {
        "doc_id": "rag_dep_2013",
        "title": "NYC DEP Wastewater Resiliency Plan (2013)",
        "citation": "NYC DEP Wastewater Resiliency Plan, 2013",
    },
    "nycha_lessons.pdf": {
        "doc_id": "rag_nycha",
        "title": "Flood Resilience at NYCHA — Lessons Learned",
        "citation": "NYCHA, Flood Resilience: Lessons Learned",
    },
    "coned_22_e_0222.pdf": {
        "doc_id": "rag_coned",
        "title": "Con Edison Climate Change Resilience Plan (2023, Case 22-E-0222)",
        "citation": "Con Edison Climate Change Resilience Plan (2023, NY PSC Case 22-E-0222)",
    },
    "mta_resilience_2025.pdf": {
        "doc_id": "rag_mta",
        "title": "MTA Climate Resilience Roadmap (October 2025 update)",
        "citation": "MTA Climate Resilience Roadmap, October 2025 update",
    },
    "comptroller_rain_2024.pdf": {
        "doc_id": "rag_comptroller",
        "title": "NYC Comptroller — Is NYC Ready for Rain? (2024)",
        "citation": "NYC Comptroller, \"Is New York City Ready for Rain?\" (2024)",
    },
}


@dataclass
class Chunk:
    text: str
    file: str
    page: int
    doc_id: str
    title: str
    citation: str


def _chunks_from_pdf(path: Path, target_chars: int = 700) -> list[Chunk]:
    import pypdf
    meta = CORPUS_META.get(path.name, {
        "doc_id": f"rag_{path.stem}",
        "title": path.stem,
        "citation": path.stem,
    })
    out: list[Chunk] = []
    try:
        reader = pypdf.PdfReader(str(path))
    except Exception as e:
        log.warning("pdf load failed for %s: %s", path.name, e)
        return out
    for i, page in enumerate(reader.pages):
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        txt = re.sub(r"\s+", " ", txt).strip()
        if len(txt) < 80:
            continue
        # split into ~target_chars chunks at sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", txt)
        buf = ""
        for s in sentences:
            if len(buf) + len(s) + 1 <= target_chars or not buf:
                buf = (buf + " " + s).strip() if buf else s
            else:
                out.append(Chunk(text=buf, file=path.name, page=i + 1,
                                 doc_id=meta["doc_id"], title=meta["title"],
                                 citation=meta["citation"]))
                buf = s
        if buf:
            out.append(Chunk(text=buf, file=path.name, page=i + 1,
                             doc_id=meta["doc_id"], title=meta["title"],
                             citation=meta["citation"]))
    return out


_INDEX: dict | None = None
_RERANKER = None  # lazy CrossEncoder

# Reranker switch: when "1", retrieve() over-fetches K*5 candidates without
# the per-doc dedup, scores them via the Granite Embedding Reranker R2
# cross-encoder, then dedups to K. Falls back to the baseline ranker when
# disabled. See experiments/03_granite_reranker/RESULTS.md for the
# reasoning behind inverting dedup vs rerank.
_RERANKER_ENABLE = os.environ.get("RIPRAP_RERANKER_ENABLE", "").lower() in ("1", "true", "yes")
_RERANKER_MODEL_NAME = os.environ.get(
    "RIPRAP_RERANKER_MODEL",
    "ibm-granite/granite-embedding-reranker-english-r2",
)


def _ensure_index():
    global _INDEX
    if _INDEX is not None:
        return _INDEX

    chunks: list[Chunk] = []
    for f in sorted(CORPUS_DIR.glob("*.pdf")):
        log.info("rag: chunking %s", f.name)
        chunks.extend(_chunks_from_pdf(f))
    log.info("rag: %d chunks across %d files",
             len(chunks), len(set(c.file for c in chunks)))
    if not chunks:
        _INDEX = {"chunks": [], "embs": None, "model": None}
        return _INDEX

    texts = [c.text for c in chunks]
    log.info("rag: embedding %d chunks", len(texts))

    # v0.4.5 — try the MI300X service first. Avoids loading
    # sentence-transformers + the granite-embedding weights on a
    # cpu-basic surface (HF Space). Falls back to local on
    # RemoteUnreachable so dev laptops keep working with no env.
    embs = None
    model = None
    try:
        from app import inference as _inf
        if _inf.remote_enabled():
            log.info("rag: encoding via remote MI300X")
            remote = _inf.granite_embed(texts, timeout=120.0)
            if remote.get("ok"):
                embs = np.asarray(remote["vectors"], dtype="float32")
                # Per-query encodes will also route through remote;
                # `model` stays None and `retrieve()` checks for it.
    except _inf.RemoteUnreachable as e:
        log.info("rag: remote unreachable (%s); local fallback", e)
    except Exception:
        log.exception("rag: remote encode failed; local fallback")

    if embs is None:
        from sentence_transformers import SentenceTransformer
        log.info("rag: loading %s (local fallback)", EMBED_MODEL_NAME)
        model = SentenceTransformer(EMBED_MODEL_NAME)
        embs = model.encode(texts, batch_size=32, show_progress_bar=False,
                             convert_to_numpy=True, normalize_embeddings=True)
        embs = embs.astype("float32")

    _INDEX = {"chunks": chunks, "embs": embs, "model": model}
    log.info("rag: index ready (%s)", embs.shape)
    return _INDEX


def _ensure_reranker():
    """Lazy-load the cross-encoder. Returns None if disabled or load fails;
    callers fall back to the baseline ranker silently."""
    global _RERANKER
    if not _RERANKER_ENABLE:
        return None
    if _RERANKER is not None:
        return _RERANKER
    try:
        from sentence_transformers import CrossEncoder
        log.info("rag: loading reranker %s", _RERANKER_MODEL_NAME)
        _RERANKER = CrossEncoder(_RERANKER_MODEL_NAME)
        log.info("rag: reranker ready")
    except Exception:
        log.exception("rag: reranker load failed; falling back to baseline")
        _RERANKER = False  # sentinel: don't retry every call
    return _RERANKER or None


def warm():
    _ensure_index()
    _ensure_reranker()


def retrieve(query: str, k: int = 4, min_score: float = 0.30) -> list[dict]:
    idx = _ensure_index()
    if idx["embs"] is None or not idx["chunks"]:
        return []

    # v0.4.5 — encode query via remote when corpus was embedded remotely.
    # `_ensure_index` leaves `model = None` when it took the remote
    # path, so this branch handles both:
    #   - model present  → local SentenceTransformer.encode (fast, in-mem)
    #   - model is None  → POST to MI300X, fallback to a one-shot local
    #                       SentenceTransformer load if remote is down.
    if idx["model"] is not None:
        qv = idx["model"].encode([query], convert_to_numpy=True,
                                  normalize_embeddings=True).astype("float32")
    else:
        qv = None
        try:
            from app import inference as _inf
            if _inf.remote_enabled():
                remote = _inf.granite_embed([query])
                if remote.get("ok"):
                    qv = np.asarray(remote["vectors"], dtype="float32")
        except _inf.RemoteUnreachable as e:
            log.info("rag: per-query encode remote unreachable (%s)", e)
        if qv is None:
            from sentence_transformers import SentenceTransformer
            log.info("rag: cold-loading %s for per-query encode (remote down)",
                     EMBED_MODEL_NAME)
            local = SentenceTransformer(EMBED_MODEL_NAME)
            qv = local.encode([query], convert_to_numpy=True,
                              normalize_embeddings=True).astype("float32")
            # Cache so subsequent queries don't re-load
            idx["model"] = local
    sims = (idx["embs"] @ qv.T).ravel()

    reranker = _ensure_reranker()
    if reranker is not None:
        # Over-fetch K*5 candidates (no per-doc dedup yet), rerank, then
        # dedup to K. This keeps high-relevance chunks alive long enough
        # for the cross-encoder to see them — the legacy path's
        # dedup-before-rank threw them away.
        cand_n = min(len(idx["chunks"]), max(k * 5, 20))
        top_idx = np.argsort(-sims)[:cand_n]
        candidates = [(int(i), idx["chunks"][int(i)],
                       float(sims[int(i)])) for i in top_idx
                      if float(sims[int(i)]) >= min_score]
        if not candidates:
            return []
        pairs = [[query, c.text] for _, c, _ in candidates]
        scores = reranker.predict(pairs)
        ranked = sorted(zip(candidates, scores, strict=True),
                        key=lambda x: float(x[1]), reverse=True)
        out: list[dict] = []
        seen_per_doc: dict[str, int] = {}
        for (_i, c, retr_score), rerank_score in ranked:
            if seen_per_doc.get(c.doc_id, 0) >= 1:
                continue
            seen_per_doc[c.doc_id] = 1
            out.append({
                "doc_id": c.doc_id,
                "title": c.title,
                "citation": c.citation,
                "file": c.file,
                "page": c.page,
                "text": c.text,
                "score": float(rerank_score),
                "retriever_score": retr_score,
            })
            if len(out) >= k:
                break
        return out

    # Baseline ranker (unchanged behaviour when reranker disabled)
    top = np.argsort(-sims)[:k * 3]
    out2: list[dict] = []
    seen_per_doc2: dict[str, int] = {}
    for i in top:
        if sims[i] < min_score:
            continue
        c = idx["chunks"][i]
        if seen_per_doc2.get(c.doc_id, 0) >= 1:
            continue
        seen_per_doc2[c.doc_id] = 1
        out2.append({
            "doc_id": c.doc_id,
            "title": c.title,
            "citation": c.citation,
            "file": c.file,
            "page": c.page,
            "text": c.text,
            "score": float(sims[i]),
        })
        if len(out2) >= k:
            break
    return out2
