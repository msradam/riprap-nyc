"""Phase 2 end-to-end: pull a paragraph from a corpus PDF, run GLiNER,
build a `gliner_<source>` document, ask Granite 4.1 8B to write a
single cited claim against it. Run on both backends.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from emit_doc import SYSTEM_PROMPT_FRAGMENT, make_doc, render_for_trace  # noqa: E402
from extract import extract, load_model  # noqa: E402
from extract_from_pdf import read_pdf_paragraphs  # noqa: E402

from experiments.shared import backends, trace_render  # noqa: E402

USER_PROMPT = (
    "Write a single sentence summarizing one funded action from the "
    "extractions, citing the source with [gliner_<source>]. "
    "Do not invent any value not present in the extractions list."
)


def run_for_backend(backend_name, doc, system_extra):
    t0 = time.time()
    messages = [
        doc,
        {"role": "system", "content": system_extra},
        {"role": "user", "content": USER_PROMPT},
    ]
    resp = backends.chat(model="granite4.1:8b", messages=messages,
                         options={"temperature": 0, "num_predict": 200,
                                  "num_ctx": 4096})
    return {
        "backend": backend_name,
        "info": backends.backend_info(),
        "elapsed_s": round(time.time() - t0, 2),
        "content": resp["message"]["content"].strip(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--source-id", required=True,
                    help="Short slug for doc_id, e.g. 'comptroller'")
    ap.add_argument("--vllm-base-url", required=True)
    ap.add_argument("--vllm-api-key", required=True)
    args = ap.parse_args()

    print(trace_render.banner(f"Phase 2 double-gate · GLiNER · {args.source_id}"))

    corpus = Path(__file__).resolve().parents[2] / "corpus"
    pdf_path = corpus / args.pdf
    paras = read_pdf_paragraphs(pdf_path)
    if not paras:
        print(f"No paragraphs found in {pdf_path}", file=sys.stderr)
        return 1
    para = sorted(paras, key=len, reverse=True)[0]

    print("Loading GLiNER…")
    t0 = time.time()
    model = load_model()
    print(f"GLiNER load: {time.time() - t0:.2f}s")

    t0 = time.time()
    extractions = extract(model, para)
    print(f"GLiNER extract: {time.time() - t0:.2f}s "
          f"({len(extractions)} entities)")
    print(trace_render.render_step(**render_for_trace(args.source_id, extractions),
                                   elapsed_s=time.time() - t0))

    doc = make_doc(args.source_id, para, extractions)
    print(f"\ndoc body (truncated):\n{doc['content'][:400]}\n")

    results = []
    for backend_name, kwargs in [
        ("ollama", dict(backend="ollama")),
        ("vllm",   dict(backend="vllm",
                        base_url=args.vllm_base_url,
                        api_key=args.vllm_api_key)),
    ]:
        backends.configure(**kwargs)
        try:
            r = run_for_backend(backend_name, doc, SYSTEM_PROMPT_FRAGMENT)
        except Exception as e:
            r = {"backend": backend_name, "error": f"{type(e).__name__}: {e}"}
        results.append(r)
        print(trace_render.banner(
            f"{backend_name}  ({r.get('elapsed_s', '-')}s)  "
            f"hw={r.get('info', {}).get('hardware', '?')}"))
        print(r.get("content", r.get("error")))

    out = Path(__file__).parent / ".cache" / f"double_gate_{args.source_id}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "source_id": args.source_id,
        "doc": doc,
        "extractions": [asdict(e) for e in extractions],
        "results": results,
    }, indent=2, default=str))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
