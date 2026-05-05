"""End-to-end Phase 1 validation: take a chip, run Prithvi, build the
structured doc, ask Granite 4.1 8B to write a one-sentence cited claim
against it. Run the same query on both backends (local Ollama and AMD
vLLM) and emit a paired diff.

Usage:
  python run_double_gate.py \\
      --chip .cache/chip_40.5780_-73.9617_2024-09-01_2024-09-30.tif \\
      --label "Brighton Beach" \\
      --vllm-base-url http://165.245.134.44:8000/v1 \\
      --vllm-api-key $RIPRAP_LLM_API_KEY

Output: a small report with both backends' citations side-by-side and a
diff summary. Writes RESULTS-style entries that the experiment's
RESULTS.md aggregates.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

# Make app/ importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from emit_doc import SYSTEM_PROMPT_FRAGMENT, make_doc, render_for_trace  # noqa: E402
from infer_water import infer  # noqa: E402

from experiments.shared import backends, trace_render  # noqa: E402

USER_PROMPT = (
    "Write a single sentence about live observed water near the address, "
    "citing at least one number with [prithvi_live]. "
    "Do not write a comparative claim if nta_baseline_pct is null."
)


def run_for_backend(backend_name: str, doc, system_extra: str) -> dict:
    t0 = time.time()
    messages = [
        doc,
        {"role": "system", "content": system_extra},
        {"role": "user", "content": USER_PROMPT},
    ]
    resp = backends.chat(
        model="granite4.1:8b", messages=messages,
        options={"temperature": 0, "num_predict": 200, "num_ctx": 4096},
    )
    return {
        "backend": backend_name,
        "info": backends.backend_info(),
        "elapsed_s": round(time.time() - t0, 2),
        "content": resp["message"]["content"].strip(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chip", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--vllm-base-url", required=True)
    ap.add_argument("--vllm-api-key", required=True)
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()

    print(trace_render.banner(f"Phase 1 double-gate · {args.label}"))

    # 1. Run the model
    t0 = time.time()
    water = infer(args.chip, args.label, device=args.device)
    print(f"prithvi inference: {time.time() - t0:.2f}s")
    print(trace_render.render_step(**render_for_trace(water),
                                   elapsed_s=time.time() - t0))

    # 2. Build the doc + system fragment
    doc = make_doc(water, nta_baseline_pct=None)
    print(f"\ndoc body:\n{doc['content']}\n")

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
        print(r.get("content", r.get("error", "<no content>")))

    # 3. Emit a JSON summary the RESULTS.md aggregator can pick up
    out_path = Path(__file__).parent / ".cache" / f"double_gate_{args.label.lower().replace(' ', '_')}.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps({
        "label": args.label,
        "water": asdict(water),
        "doc": doc,
        "results": results,
    }, indent=2, default=str))
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
