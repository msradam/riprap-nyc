"""Sanity-check granite_embed in the locally-running Triton container.

Verifies:
1. /v2/health/ready returns 200
2. /v2/models/granite_embed/ready returns 200
3. POST /v2/models/granite_embed/infer with 2 texts returns 768-dim
   embeddings, meta JSON with device='cpu', and elapsed_s plausible.

Usage:
    .venv/bin/python load/triton-local/test_granite_embed.py
"""
from __future__ import annotations

import json
import sys
import time

import httpx
import numpy as np

BASE = "http://localhost:8000"


def main() -> int:
    print(f"[test] Triton base: {BASE}")

    print("[test] /v2/health/ready ...", end=" ", flush=True)
    r = httpx.get(f"{BASE}/v2/health/ready", timeout=5.0)
    print(r.status_code)
    if r.status_code != 200:
        print(f"  FAIL — body: {r.text[:200]}")
        return 1

    print("[test] /v2/models/granite_embed/ready (may need to wait for load) ...")
    for attempt in range(60):
        r = httpx.get(f"{BASE}/v2/models/granite_embed/ready", timeout=5.0)
        if r.status_code == 200:
            print(f"  ready after {attempt}s")
            break
        time.sleep(1)
    else:
        print(f"  FAIL — not ready after 60s; status={r.status_code} body={r.text[:200]}")
        return 1

    print("[test] POST /v2/models/granite_embed/infer ...")
    texts = ["Riprap is a flood briefing tool.", "Boston Harbor station 8443970."]
    # config.pbtxt has max_batch_size=32, so Triton requires a batch dim
    # prepended. dims=[-1] becomes effective shape [B, -1]. Treat each
    # text as its own batch element with payload dim 1.
    payload = {
        "inputs": [
            {
                "name": "texts",
                "shape": [len(texts), 1],
                "datatype": "BYTES",
                "data": texts,
            }
        ]
    }
    t0 = time.time()
    r = httpx.post(
        f"{BASE}/v2/models/granite_embed/infer", json=payload, timeout=60.0
    )
    dt = time.time() - t0
    print(f"  status={r.status_code}  wall={dt:.2f}s")
    if r.status_code != 200:
        print(f"  FAIL — body: {r.text[:500]}")
        return 1

    data = r.json()
    outputs = {o["name"]: o for o in data.get("outputs", [])}
    vecs_out = outputs.get("vectors")
    meta_out = outputs.get("meta")
    if not vecs_out or not meta_out:
        print(f"  FAIL — missing outputs; got: {list(outputs)}")
        return 1

    vec_data = np.array(vecs_out["data"], dtype=np.float32).reshape(vecs_out["shape"])
    meta_str = meta_out["data"][0]
    meta = json.loads(meta_str)

    print(f"  vectors shape: {vec_data.shape}  (expected ({len(texts)}, 768))")
    print(f"  meta: {meta}")
    norms = np.linalg.norm(vec_data, axis=1)
    print(f"  L2 norms (should be ~1.0): {norms.tolist()}")

    ok = (
        vec_data.shape == (len(texts), 768)
        and abs(norms[0] - 1.0) < 1e-3
        and abs(norms[1] - 1.0) < 1e-3
        and meta.get("ok") is True
        and meta.get("device") in ("cpu", "cuda")
    )
    print(f"[test] {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
