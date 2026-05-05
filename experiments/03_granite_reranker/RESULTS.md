# Phase 3 — Granite Embedding Reranker R2 (cross-encoder, 149 M)

## Status

**Working end-to-end on the existing 5-PDF corpus, both backends.**

## Model

- **Model:** `ibm-granite/granite-embedding-reranker-english-r2`
- **Type:** cross-encoder reranker (149 M params)
- **License:** Apache-2.0 (verified, HF cardData)
- **Loader:** `sentence_transformers.CrossEncoder` — sidecar pattern,
  no vLLM `--task score` per project decision
- **Library declared:** `sentence-transformers`

## Pipeline

1. **`rerank.py`** — loads the cross-encoder, scores
   `[query, candidate]` pairs, returns ranked top-K.
2. **`run_double_gate.py`** — calls the existing
   `app.rag.retrieve_top_k`-equivalent (with the per-doc dedup
   bypassed), gathers top-20, reranks to top-3, and runs both
   backends' reconciler against the top-1 passage.

## Validation

### Hand-crafted query + 5 candidate paragraphs

Query: *"What are flood risks in Hollis, Queens?"*

The reranker correctly ranked the Hollis-Ida paragraph #1 (score
0.93), Sandy/Brighton #2 (0.77), and Rockaways #3 (0.73). The
Newtown Creek WWTP and Bluebelt operations paragraphs (off-topic for a
Hollis flood-risk query) were correctly demoted out of the top-3.

### Real corpus end-to-end

Query: *"What flood risk does Hollis, Queens face from heavy
rainfall?"*

Retriever (Granite Embedding 278 M) top-3:

| Rank | Retriever score | Doc | Excerpt |
|-----:|----------------:|-----|---------|
| 1 | 0.760 | rag_mta | "Urgent Call for Action 7 Climate Resilience Roadmap…" |
| 2 | 0.749 | rag_comptroller | "Forecast & Emergency Plan Activation Flash flooding…" |
| 3 | 0.749 | rag_comptroller | "Is New York City Ready for Rain? An Investigation…" |

Reranker top-3 (from retriever's top-20):

| Rank | Reranker score | Was retriever rank | Doc | Excerpt |
|-----:|---------------:|-------------------:|-----|---------|
| 1 | 0.886 | 6 | rag_comptroller | "Is New York City Ready for Rain?… (preparedness section)" |
| 2 | 0.869 | 4 | rag_comptroller | "Heavy rains persisted for more than an hour in southern Brooklyn…" |
| 3 | 0.869 | 1 | rag_mta | "Urgent Call for Action 7 Climate Resilience Roadmap…" |

The reranker is **doing its job**: it surfaced a query-specific
preparedness paragraph (originally rank 6 — buried by the retriever)
and demoted a generic MTA boilerplate paragraph (originally rank 1)
to position 3.

### Honesty under uncertainty

Neither selected paragraph specifically mentions Hollis. Both backends
correctly **refused to invent a Hollis-specific answer** and said so
plainly with a citation:

| Backend | Latency | Output |
|---------|--------:|--------|
| Ollama (M-series MPS) | 10.56 s | "The provided document…does not specifically mention Hollis, Queens…I cannot determine the flood risk for Hollis, Queens from heavy rainfall…[rag_comptroller]" |
| vLLM (AMD MI300X)     |  0.68 s | "The provided document does not contain specific information about the flood risk faced by Hollis, Queens from heavy rainfall. [rag_comptroller]" |

This is the desired silence-over-confabulation behavior. The reranker
+ reconciler combination did not surface a false claim despite there
being a temptation (the document discusses a 2024 storm in NYC
generally).

## Latency budget

| Stage | Latency | Notes |
|------:|--------:|-------|
| Retriever (Granite Embedding 278 M) cold load + index | 52.7 s | One-time at app boot; amortized in production |
| Retriever per-query | < 0.1 s | Already in production |
| Reranker cold load (149 M) | 1.8 s | One-time at app boot |
| Reranker score 20 candidates | 0.93 s | M3 Pro CPU, batched |
| Reconcile (Ollama, M-series) | 10.6 s | |
| Reconcile (vLLM, AMD MI300X) | 0.7 s | ~15× faster |

The reranker adds ~1 s to the user-visible path on CPU. Negligible
relative to the existing reconciler latency, well under the brief's
demo budget.

## Findings worth remembering

1. **The retriever's per-doc dedup is in the wrong place.** Currently
   `app/rag.py:retrieve()` keeps "at most 1 chunk per doc" and then
   returns top-K. For the reranker integration, this should be
   inverted: gather top-20 *with duplicates*, rerank, then dedup to
   top-3. Otherwise we're throwing away high-relevance chunks before
   the rerank ever sees them.

2. **Cross-encoder `cache_dir` arg is deprecated** in current
   sentence-transformers; passes through with a warning. Move to
   `model_kwargs={"cache_dir": ...}` when integrating to silence it.

3. **Reranker disagrees with the retriever in interesting ways.** On
   the test query the retriever's rank-1 (a generic MTA roadmap intro)
   was a content-light string that scored high on lexical/embedding
   surface similarity to "flood risk heavy rainfall". The reranker
   correctly surfaced more specific content. This is the canonical
   reason cross-encoder reranking matters.

4. **Sidecar deployment story.** No GPU needed for the reranker; ~600
   MB resident on CPU; loads in ~2 s after first download. Fits
   trivially in the HF Spaces T4 image. The vLLM-served alternative
   was explicitly out-of-scope per the project decision and isn't
   needed for these latencies.

## Files

```
03_granite_reranker/
  rerank.py           CrossEncoder load + predict wrapper
  run_double_gate.py  retriever -> reranker -> reconciler probe
  RESULTS.md          (this file)
  .cache/             reranker weights, double_gate_*.json
```

## Conclusion

Specialist works on both backends with the expected behavior change
(reranker reorders top-3 in a query-relevant way; reconciler refuses to
fabricate when source content doesn't address the query).

**Recommended path forward:** integrate as a one-line addition to
`app/rag.py:retrieve()`: take retriever top-K=20 (drop the existing
per-doc dedup), call the reranker, then dedup to top-3. Load the
cross-encoder once at app boot in `warm()`. Single env var
`RIPRAP_RERANKER_ENABLE=1` to gate the new behavior so the existing
production path is unchanged by default.
