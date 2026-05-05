# Phase 2 — GLiNER (gliner_medium-v2.1) structured extraction

## Status

**Working end-to-end on a real corpus PDF, both backends.**

## Model

- **Model:** `urchade/gliner_medium-v2.1` (151 M params)
- **License:** Apache-2.0 (verified — model card frontmatter; **NOT
  the `gliner_base` variant which is CC-BY-NC-4.0**).
- **Loader:** `gliner.GLiNER.from_pretrained(...)` — pure HF, no
  third-party fine-tune framework.

## Pipeline

1. **`extract.py`** — loads GLiNER, runs `predict_entities()` on a
   paragraph with the 5 typed labels:
   `nyc_location`, `dollar_amount`, `date_range`, `agency`,
   `infrastructure_project`. Threshold 0.45 (tuned by inspection).
2. **`extract_from_pdf.py`** — pulls paragraph text from a corpus PDF
   via `pypdf`, runs GLiNER on the longest paragraphs.
3. **`emit_doc.py`** — packages the typed list into a
   `role: "document gliner_<source>"` chat message. doc_id format:
   `gliner_comptroller`, `gliner_dep`, etc.
4. **`run_double_gate.py`** — end-to-end on a corpus PDF + paired
   Ollama/vLLM probe.

## Validation

### Hand-crafted paragraph (sanity)

> "The NYC Department of Environmental Protection allocated $5.6 million
> for the Bluebelt expansion in Hollis, Queens for fiscal year
> 2025-2027. The Newtown Creek wastewater treatment plant in
> Brooklyn will receive an additional $12 million from NYCHA's
> resilience fund."

GLiNER extracted 9/9 expected entities at score ≥ 0.59:
`[agency] NYC Department of Environmental Protection`,
`[dollar_amount] $5.6 million`,
`[infrastructure_project] Bluebelt expansion`,
`[nyc_location] Hollis, Queens`,
`[date_range] fiscal year 2025-2027`,
`[infrastructure_project] Newtown Creek wastewater treatment plant`,
`[nyc_location] Brooklyn`,
`[dollar_amount] $12 million`,
`[agency] NYCHA`.

### Real corpus PDF — `comptroller_rain_2024.pdf`

Running on the longest paragraph (~3 KB of text, methodology section):
- 15 entities extracted
- 13× `agency` (mostly `DEP` repeated, `New York City Comptroller`,
  `Comptroller's Office`)
- 1× `date_range`
- 1× `nyc_location`
- Two `dollar_amount` hits (`$15,000`, `$22.5 million`, `$ 875 million`)
  on a different paragraph in the same PDF (`top --top 2`)

Citation discipline is preserved: cited `[gliner_comptroller]` resolves
to a real input doc_id, agency tags align to actual surface text, no
hallucinated dollar amounts in either backend's output.

## Double-gating

`run_double_gate.py --pdf comptroller_rain_2024.pdf --source-id comptroller`:

| Backend | Latency | Cited content |
|---------|--------:|---------------|
| Ollama (M-series MPS) | 11.94 s | "The NYC Department of Environmental Protection (DEP) has committed to implementing flood mitigation measures as part of the city's preparedness for flash flooding, as detailed in the report by the Office of the NYC Comptroller Brad Lander **[gliner_comptroller]**." |
| vLLM (AMD MI300X)     |  0.58 s | "The NYC Department of Environmental Protection (DEP) has committed to implementing flood mitigation measures as part of the City's preparedness outlined in New Normal, Rainfall Ready, and Ida, as documented by the NYC Comptroller's Office in the source **[gliner_comptroller]**." |

Both citations resolve correctly. vLLM is again ~20× faster than
Ollama on this prompt size.

### Findings worth remembering

1. **Threshold tuning matters.** Default GLiNER `threshold=0.5` misses
   `agency = "Comptroller's Office"` (it scored 0.45). 0.45 catches it
   without producing many false positives in the policy corpus. Worth
   re-tuning per source PDF if integrated.

2. **GLiNER is fast even on CPU.** Per-paragraph extract is ~0.3 s on
   M3 Pro. The model load itself is the dominant cost (~6 s); in
   production it stays loaded, so per-call latency is sub-second.

3. **No comparative reasoning over the extractions.** GLiNER returns
   typed spans, not relations. The reconciler infers the relation
   ("DEP allocated $X for Y in Z") from co-occurrence in the
   paragraph. That's fine for our briefings since they are paragraph-
   scoped, but stronger relational extraction (REBEL, etc.) would
   need a different model.

4. **The current ranker is a placeholder.** `extract_from_pdf.py` ranks
   paragraphs by length, not query relevance. In production this
   specialist consumes the existing Granite Embedding 278M retriever's
   top-K rather than picking longest paragraphs.

## Files

```
02_gliner_extraction/
  extract.py             GLiNER load + predict_entities wrapper
  extract_from_pdf.py    pypdf paragraph splitter + GLiNER pass
  emit_doc.py            build gliner_<source> doc message
  run_double_gate.py     end-to-end + Ollama/vLLM probe
  RESULTS.md             (this file)
  .cache/                GLiNER weights, double_gate_*.json
```

## Conclusion

Specialist works on both backends. **Recommended path forward:**
integrate as a wrapper over the existing `app/rag.py` retriever output
— GLiNER runs on the top-3 retrieved paragraphs and emits one
`gliner_<source_pdf>` doc per paragraph, with the source_id derived
from the PDF filename slug. The wrapper does not replace `rag.py`; it
adds typed structure to its output for the reconciler.
