"""Phase 3 end-to-end: existing app.rag retriever -> Granite reranker
-> top-3, then double-gate via reconciler call.

Demonstrates the rerank changing the top-3 order vs retriever-only on
a query that's known to be ambiguous (the corpus has paragraphs about
multiple flood mechanisms; the query specifically asks about pluvial
flooding in Queens).

Caveat: the existing `retrieve()` does at-most-1 chunk per doc. We
bypass that for the experiment by fetching with k=20 and only using
the retriever's similarity ranking, not its dedup. In production
integration the dedup would happen *after* the reranker, not before,
so we'd get the reranker-improved top-3 with at most 1 paragraph per
PDF.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Make app/ importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rerank import load_model as load_reranker  # noqa: E402
from rerank import rerank

from experiments.shared import backends, trace_render  # noqa: E402

USER_PROMPT = (
    "Write a single sentence answering the user's query, citing the "
    "ranked source with [{cite}]. Use only the text in the provided "
    "document; if it doesn't address the query, say so."
)


def retriever_top_k(query: str, k: int = 20) -> list[dict]:
    """Return top-K retriever chunks WITHOUT the per-doc dedup."""
    import numpy as np

    from app.rag import _ensure_index
    idx = _ensure_index()
    if idx["embs"] is None:
        return []
    qv = idx["model"].encode([query], convert_to_numpy=True,
                             normalize_embeddings=True).astype("float32")
    sims = (idx["embs"] @ qv.T).ravel()
    order = np.argsort(-sims)[:k]
    return [
        {"doc_id": idx["chunks"][i].doc_id,
         "text": idx["chunks"][i].text,
         "retriever_score": float(sims[i]),
         "rank": rk + 1}
        for rk, i in enumerate(order)
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--top-k-retriever", type=int, default=20)
    ap.add_argument("--top-k-reranker",  type=int, default=3)
    ap.add_argument("--vllm-base-url", required=True)
    ap.add_argument("--vllm-api-key", required=True)
    args = ap.parse_args()

    print(trace_render.banner(f"Phase 3 double-gate · reranker · {args.query}"))

    print("Warming retriever (Granite Embedding 278M)…")
    t0 = time.time()
    retr_top = retriever_top_k(args.query, k=args.top_k_retriever)
    print(f"retriever: {time.time() - t0:.2f}s "
          f"({len(retr_top)} candidates)")

    print("\nRetriever top-3 (BEFORE rerank):")
    for r in retr_top[:3]:
        print(f"  rank {r['rank']:>2} score={r['retriever_score']:.3f}  "
              f"doc={r['doc_id']}  text={r['text'][:80]}…")

    print("\nLoading reranker…")
    t0 = time.time()
    reranker = load_reranker()
    print(f"reranker load: {time.time() - t0:.2f}s")

    t0 = time.time()
    candidates = [r["text"] for r in retr_top]
    ranked = rerank(reranker, args.query, candidates,
                    top_k=args.top_k_reranker)
    print(f"rerank ({len(retr_top)} -> {args.top_k_reranker}): "
          f"{time.time() - t0:.3f}s")

    print("\nReranker top-3 (AFTER rerank):")
    for r in ranked:
        # Find the original retriever info to compare ranks
        orig = next((x for x in retr_top if x["text"] == r.text), None)
        orig_rank = orig["rank"] if orig else "?"
        print(f"  rank {r.rank}  score={r.score:.3f}  "
              f"(was retriever rank {orig_rank})  "
              f"doc={orig['doc_id'] if orig else '?'}  "
              f"text={r.text[:80]}…")

    # Build a single-doc citation for the top-1 reranker hit and run
    # the reconciler. doc_id slug = the source PDF's doc_id.
    top1 = ranked[0]
    top1_orig = next((x for x in retr_top if x["text"] == top1.text), None)
    cite_id = (top1_orig or {}).get("doc_id", "rag_top")
    doc = {"role": f"document {cite_id}", "content": top1.text}

    results = []
    for backend_name, kwargs in [
        ("ollama", dict(backend="ollama")),
        ("vllm",   dict(backend="vllm",
                        base_url=args.vllm_base_url,
                        api_key=args.vllm_api_key)),
    ]:
        backends.configure(**kwargs)
        t0 = time.time()
        try:
            messages = [
                doc,
                {"role": "system", "content": USER_PROMPT.format(cite=cite_id)},
                {"role": "user", "content": args.query},
            ]
            resp = backends.chat(model="granite4.1:8b", messages=messages,
                                 options={"temperature": 0,
                                          "num_predict": 200,
                                          "num_ctx": 4096})
            r = {"backend": backend_name,
                 "info": backends.backend_info(),
                 "elapsed_s": round(time.time() - t0, 2),
                 "content": resp["message"]["content"].strip()}
        except Exception as e:
            r = {"backend": backend_name,
                 "error": f"{type(e).__name__}: {e}"}
        results.append(r)
        print(trace_render.banner(
            f"{backend_name}  ({r.get('elapsed_s', '-')}s)  "
            f"hw={r.get('info', {}).get('hardware', '?')}"))
        print(r.get("content", r.get("error")))

    out = Path(__file__).parent / ".cache" / "double_gate_rerank.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "query": args.query,
        "retriever_top": retr_top,
        "reranker_top": [{"rank": r.rank, "score": r.score, "text": r.text}
                         for r in ranked],
        "results": results,
    }, indent=2, default=str))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
