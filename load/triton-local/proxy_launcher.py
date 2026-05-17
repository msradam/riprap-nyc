"""Run riprap-triton's proxy.py locally on macOS, patched to talk to our
local Triton on :8000 (the riprap-triton repo's proxy assumes :8001
because in the RunPod stack vLLM owns :8000).

Two patches applied at import time:

1. `TRITON_URL` → http://127.0.0.1:8000  (our local Triton)
2. `_make_embed_triton_request` → prepend the batch dim (the upstream
   `[len(texts)]` shape breaks against `max_batch_size=32` configs;
   Triton requires [B, D]). We send [N, 1] which the model's
   `.flatten()` handles identically.

vLLM endpoints (/v1/chat/completions, /v1/completions, /v1/models)
will 502 because no vLLM is running — that's fine for the riprap-app
UI smoke, which uses RIPRAP_LLM_PRIMARY=ollama and never hits the
proxy for the LLM tier.

Run with:
    RIPRAP_PROXY_TOKEN=<token> \\
    .venv/bin/python load/triton-local/proxy_launcher.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRITON_REPO = REPO.parent / "riprap-triton"
sys.path.insert(0, str(TRITON_REPO / "proxy"))

# Import the upstream proxy module
import proxy as upstream_proxy  # noqa: E402

# Patch 1: re-point Triton URL
upstream_proxy.TRITON_URL = os.environ.get(
    "TRITON_URL", "http://127.0.0.1:8000"
)
upstream_proxy.VLLM_URL = os.environ.get(
    "VLLM_URL", "http://127.0.0.1:18000"  # unused locally; bogus port keeps health honest
)


# Patch 2: fix the embed request shape (the upstream sends `[N]` which fails
# against max_batch_size=32 configs; Triton requires the batch dim).
def _make_embed_triton_request_fixed(body_bytes: bytes) -> dict:
    payload = json.loads(body_bytes)
    texts = payload.get("texts", [])
    return {
        "inputs": [
            {
                "name": "texts",
                "shape": [len(texts), 1],
                "datatype": "BYTES",
                "data": texts,
            }
        ],
        "outputs": [{"name": "vectors"}, {"name": "meta"}],
    }


upstream_proxy._make_embed_triton_request = _make_embed_triton_request_fixed


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PROXY_PORT", "7860"))
    print(f"[proxy_launcher] TRITON_URL = {upstream_proxy.TRITON_URL}")
    print(f"[proxy_launcher] VLLM_URL   = {upstream_proxy.VLLM_URL}")
    print(f"[proxy_launcher] listening on :{port}")
    uvicorn.run(upstream_proxy.app, host="127.0.0.1", port=port, log_level="info")
