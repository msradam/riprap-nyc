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

    from sentence_transformers import SentenceTransformer
    log.info("rag: loading %s", EMBED_MODEL_NAME)
    model = SentenceTransformer(EMBED_MODEL_NAME)

    texts = [c.text for c in chunks]
    log.info("rag: embedding %d chunks", len(texts))
    embs = model.encode(texts, batch_size=32, show_progress_bar=False,
                        convert_to_numpy=True, normalize_embeddings=True)
    _INDEX = {"chunks": chunks, "embs": embs.astype("float32"), "model": model}
    log.info("rag: index ready (%s)", embs.shape)
    return _INDEX


def warm():
    _ensure_index()


def retrieve(query: str, k: int = 4, min_score: float = 0.30) -> list[dict]:
    idx = _ensure_index()
    if idx["embs"] is None or not idx["chunks"]:
        return []
    qv = idx["model"].encode([query], convert_to_numpy=True,
                             normalize_embeddings=True).astype("float32")
    # cosine similarity (vectors are L2-normalized)
    sims = (idx["embs"] @ qv.T).ravel()
    top = np.argsort(-sims)[:k * 3]  # over-fetch then de-dupe per doc
    out: list[dict] = []
    seen_per_doc: dict[str, int] = {}
    for i in top:
        if sims[i] < min_score:
            continue
        c = idx["chunks"][i]
        if seen_per_doc.get(c.doc_id, 0) >= 1:  # at most 1 chunk per doc
            continue
        seen_per_doc[c.doc_id] = seen_per_doc.get(c.doc_id, 0) + 1
        out.append({
            "doc_id": c.doc_id,
            "title": c.title,
            "citation": c.citation,
            "file": c.file,
            "page": c.page,
            "text": c.text,
            "score": float(sims[i]),
        })
        if len(out) >= k:
            break
    return out
