"""Backend client shim for experiments.

Imports `app.llm.chat` (the LiteLLM Router) so experiment code talks to
exactly the same call surface production uses. Adds a tiny helper
`run_against(backend, ...)` that flips env vars per-call so a single
script can paired-diff Ollama vs vLLM without restarting Python.

The production router caches its config at module-import; flipping env
afterwards is a no-op for it. So `run_against` rebuilds the router
when the requested backend differs from the active one. Cheap (~2 ms)
and confined to experiments.
"""

from __future__ import annotations

import os
from typing import Any

# Test addresses used across all experiments. (lat, lon, mechanism)
TEST_ADDRESSES = {
    "brighton_beach": (40.5780, -73.9617, "coastal"),
    "hollis":         (40.7115, -73.7681, "pluvial"),
    "hunts_point":    (40.8155, -73.8830, "mixed"),
}


def _reload_llm() -> None:
    """Re-import app.llm so it re-reads env. Used by run_against."""
    import importlib

    from app import llm as _llm
    importlib.reload(_llm)


def configure(backend: str, base_url: str | None = None,
              api_key: str | None = None) -> None:
    """Set env vars for the LiteLLM router and reload it.

    backend ∈ {"ollama", "vllm"}.
    """
    if backend == "vllm":
        if not base_url:
            raise ValueError("vllm backend requires base_url")
        os.environ["RIPRAP_LLM_PRIMARY"] = "vllm"
        os.environ["RIPRAP_LLM_BASE_URL"] = base_url
        if api_key:
            os.environ["RIPRAP_LLM_API_KEY"] = api_key
    elif backend == "ollama":
        os.environ["RIPRAP_LLM_PRIMARY"] = "ollama"
        # Leaving BASE_URL set is harmless when primary=ollama, but
        # clear it for symmetry so backend_info() reports cleanly.
        os.environ.pop("RIPRAP_LLM_BASE_URL", None)
        os.environ.pop("RIPRAP_LLM_API_KEY", None)
    else:
        raise ValueError(f"unknown backend {backend!r}")
    _reload_llm()


def chat(*args, **kwargs) -> Any:
    """Pass through to app.llm.chat (re-imported on demand)."""
    from app import llm
    return llm.chat(*args, **kwargs)


def backend_info() -> dict:
    from app import llm
    return llm.backend_info()
