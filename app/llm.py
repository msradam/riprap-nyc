"""LiteLLM-backed shim around the ollama.chat call surface.

Single function `chat(model, messages, options, stream)` that returns the
same dict / iterator-of-dicts shape `ollama.chat` returns, so existing
call sites swap `import ollama` -> `from app import llm` with no other
changes.

Backend selection (env):
  RIPRAP_LLM_PRIMARY   = "vllm" | "ollama"   (default: ollama)
  RIPRAP_LLM_BASE_URL  = http://amd:8000/v1  (vllm only)
  RIPRAP_LLM_API_KEY   = <token>             (vllm only)
  RIPRAP_LLM_FALLBACK  = "ollama" | ""       (default: "ollama" when
                                              primary=vllm, else "")
  OLLAMA_BASE_URL      = http://host:11434   (ollama backend only)

Model routing: callers may pass either Ollama tags ("granite4.1:8b") or
logical aliases ("granite-8b"). Mapped to:
  vllm   -> openai/granite-4.1-{3b,8b} on RIPRAP_LLM_BASE_URL
  ollama -> ollama_chat/granite4.1:{3b,8b} on OLLAMA_BASE_URL

When primary=vllm with fallback=ollama, the LiteLLM Router auto-fails
over to the local Ollama deployment if the AMD endpoint errors (timeout,
connection refused, 5xx). Existing call sites are unaware of the swap.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from typing import Any

import litellm
from litellm import Router

from app import emissions

log = logging.getLogger(__name__)

litellm.suppress_debug_info = True
litellm.drop_params = True  # silently drop unsupported params instead of erroring

_VLLM_BASE = os.environ.get("RIPRAP_LLM_BASE_URL", "").rstrip("/")
_VLLM_KEY = os.environ.get("RIPRAP_LLM_API_KEY", "") or "EMPTY"
_PRIMARY = os.environ.get("RIPRAP_LLM_PRIMARY", "ollama").lower()
_FALLBACK = os.environ.get(
    "RIPRAP_LLM_FALLBACK",
    "ollama" if _PRIMARY == "vllm" else "",
).lower()

_OLLAMA_BASE = os.environ.get(
    "OLLAMA_BASE_URL",
    os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
)
if not _OLLAMA_BASE.startswith("http"):
    _OLLAMA_BASE = "http://" + _OLLAMA_BASE

# alias -> (vllm-served-name, ollama-tag)
# In our hackathon vLLM deployment only the 8B is served (one served-name
# per vLLM process and we don't want a second container). Override the
# 3B served-name with RIPRAP_LLM_VLLM_3B_NAME if you stand up a second
# vLLM serving the 3B and want the planner to hit it specifically.
_VLLM_8B = os.environ.get("RIPRAP_LLM_VLLM_8B_NAME", "granite-4.1-8b")
_VLLM_3B = os.environ.get("RIPRAP_LLM_VLLM_3B_NAME", _VLLM_8B)
# Ollama tag overrides: HF Spaces' build disk fills past the threshold
# when both granite4.1:3b and granite4.1:8b are pulled alongside the
# Phase 1 / Phase 4 EO toolchain. Set RIPRAP_OLLAMA_3B_TAG=granite4.1:8b
# on disk-constrained deployments — the planner output is short, so
# the 8B-vs-3B difference is latency, not correctness.
#
# RIPRAP_OLLAMA_8B_TAG is also the cheapest knob for swapping quants
# without touching code: e.g. "granite4.1:8b-q3_K_M" gives ~1 GB of
# memory back vs the default Q4_K_M, at minor grounding-discipline cost
# (re-run the Hollis probe before committing — see CLAUDE.md).
_OLLAMA_3B_TAG = os.environ.get("RIPRAP_OLLAMA_3B_TAG", "granite4.1:3b")
_OLLAMA_8B_TAG = os.environ.get("RIPRAP_OLLAMA_8B_TAG", "granite4.1:8b")
_LOGICAL: dict[str, tuple[str, str]] = {
    "granite-3b": (_VLLM_3B, _OLLAMA_3B_TAG),
    "granite-8b": (_VLLM_8B, _OLLAMA_8B_TAG),
}
_OLLAMA_TO_LOGICAL = {v[1]: k for k, v in _LOGICAL.items()}
# Also accept the canonical hardcoded tag names so callers passing
# `granite4.1:3b` resolve to the alias even when the env override
# remapped that alias to `granite4.1:8b`.
_OLLAMA_TO_LOGICAL.setdefault("granite4.1:3b", "granite-3b")
_OLLAMA_TO_LOGICAL.setdefault("granite4.1:8b", "granite-8b")


def _build_router() -> Router:
    model_list: list[dict[str, Any]] = []
    fallbacks: list[dict[str, list[str]]] = []
    use_vllm = _PRIMARY == "vllm" and bool(_VLLM_BASE)

    # vLLM on RunPod can take 250+ seconds to cold-start (container boot +
    # model load into GPU VRAM). The first-token timeout must exceed that.
    # stream_timeout (per-chunk) stays tight since subsequent tokens are fast.
    _vllm_first_token_timeout = int(
        os.environ.get("RIPRAP_LITELLM_TIMEOUT_S", "360"))
    _ollama_timeout = 240

    for alias, (vllm_name, ollama_tag) in _LOGICAL.items():
        if use_vllm:
            model_list.append({
                "model_name": alias,
                "litellm_params": {
                    "model": f"openai/{vllm_name}",
                    "api_base": _VLLM_BASE,
                    "api_key": _VLLM_KEY,
                    "timeout": _vllm_first_token_timeout,
                    "stream_timeout": 60,
                },
            })
            if _FALLBACK == "ollama":
                fb_alias = f"{alias}-ollama"
                model_list.append({
                    "model_name": fb_alias,
                    "litellm_params": {
                        "model": f"ollama_chat/{ollama_tag}",
                        "api_base": _OLLAMA_BASE,
                        "timeout": _ollama_timeout,
                        "stream_timeout": _ollama_timeout,
                    },
                })
                fallbacks.append({alias: [fb_alias]})
        else:
            model_list.append({
                "model_name": alias,
                "litellm_params": {
                    "model": f"ollama_chat/{ollama_tag}",
                    "api_base": _OLLAMA_BASE,
                    "timeout": _ollama_timeout,
                    "stream_timeout": _ollama_timeout,
                },
            })

    log.info("llm router primary=%s fallback=%s vllm_base=%s ollama_base=%s",
             _PRIMARY, _FALLBACK or "<none>",
             _VLLM_BASE or "<unset>", _OLLAMA_BASE)
    return Router(
        model_list=model_list,
        fallbacks=fallbacks,
        num_retries=0,  # Router fallback handles the failover; no point
                        # burning seconds re-hitting a dead endpoint.
        timeout=_vllm_first_token_timeout if use_vllm else _ollama_timeout,
    )


_router = _build_router()


def _resolve_alias(model: str) -> str:
    if model in _LOGICAL:
        return model
    if model in _OLLAMA_TO_LOGICAL:
        return _OLLAMA_TO_LOGICAL[model]
    return model  # pass through; let the router report unknowns


def _opts_to_kwargs(options: dict | None) -> dict:
    """Translate ollama-style options dict to LiteLLM kwargs.

    Ollama-only knobs (num_ctx) are forwarded via extra_body so that the
    ollama_chat backend still receives them; OpenAI/vLLM ignores them
    (litellm.drop_params=True).
    """
    kw: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    if options:
        if "temperature" in options:
            kw["temperature"] = options["temperature"]
        if "top_p" in options:
            kw["top_p"] = options["top_p"]
        if "num_predict" in options:
            kw["max_tokens"] = options["num_predict"]
        for k in ("num_ctx",):
            if k in options:
                extra[k] = options[k]
    if extra:
        kw["extra_body"] = extra
    return kw


def _extract_documents(messages: list[dict]) -> list[dict]:
    """Pull document-role messages into Granite's HF chat-template format.

    Ollama's Modelfile template recognizes `role: "document <id>"` and
    bundles the message into a <documents> block automatically. The HF
    tokenizer chat template (used by vLLM) does *not* — it silently
    drops non-standard roles. To make vLLM honor the same grounding
    contract, we extract the documents into the chat-template kwarg
    `documents=[{"doc_id": ..., "text": ...}]` while leaving the
    original document-role messages in place so the Ollama backend
    keeps working unchanged on the fallback path.
    """
    docs: list[dict] = []
    for m in messages:
        role = m.get("role", "")
        if role.startswith("document "):
            docs.append({
                "doc_id": role.split(" ", 1)[1],
                "text": m.get("content", ""),
            })
    return docs


# vLLM's Granite chat template emits citations as `[doc_id=foo]`; the rest
# of Riprap (Mellea checks, frontend chip rendering, citations regex) all
# expect the bare `[foo]` form that Ollama's Modelfile template produces.
# Normalize transparently so the two backends are interchangeable.
_CITE_NORMALIZE_RE = __import__("re").compile(r"\[doc_id=([A-Za-z0-9_]+)\]")


def _normalize_citations(text: str) -> str:
    return _CITE_NORMALIZE_RE.sub(r"[\1]", text)


def _to_ollama_shape(resp) -> dict:
    msg = resp.choices[0].message
    content = _normalize_citations(msg.content or "")
    return {"message": {"role": "assistant", "content": content}}


def _stream_to_ollama_shape(stream, *, on_done=None) -> Iterator[dict]:
    accum: list[str] = []
    for chunk in stream:
        try:
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None) or ""
        except (IndexError, AttributeError):
            content = ""
        # Per-chunk normalize is safe: `[doc_id=X]` arrives as a single
        # token sequence inside one chunk in practice, and the regex is
        # idempotent / no-op on partial matches.
        if content:
            content = _normalize_citations(content)
            accum.append(content)
        yield {"message": {"role": "assistant", "content": content}}
    if on_done is not None:
        on_done("".join(accum))


def _hardware_for(engine: str) -> str:
    """Map the active LLM engine to an emissions.HARDWARE key.

    Operator override via RIPRAP_HARDWARE_LABEL is honored where it
    matches a known key (mi300x / l4 / t4 / apple / cpu); otherwise:
      - Remote vLLM/Ollama (RIPRAP_LLM_BASE_URL set) → NVIDIA L4. Both
        Riprap inference Spaces (msradam/riprap-vllm + msradam/
        riprap-inference) run on L4. The MI300X droplet was retired
        2026-05-06.
      - On a CPU/T4-tier HF Space (UI Space with no remote backend) →
        T4.
      - Otherwise local dev → Apple M-series."""
    override = (os.environ.get("RIPRAP_HARDWARE_LABEL") or "").lower()
    if "mi300x" in override or "amd" in override:
        return "amd_mi300x"
    if "l4" in override:
        return "nvidia_l4"
    if "t4" in override:
        return "nvidia_t4"
    if "nvidia" in override:
        return "nvidia_l4"
    if "apple" in override or "m3" in override or "m4" in override:
        return "apple_m"
    if _VLLM_BASE:
        # Any remote vLLM/Ollama backend currently lives on an L4 Space.
        return "nvidia_l4"
    if os.environ.get("SPACE_ID") or os.environ.get("HF_SPACE_ID"):
        return "nvidia_t4"
    return "apple_m"


def _extract_usage(resp) -> tuple[int | None, int | None]:
    """Pull (prompt_tokens, completion_tokens) from a LiteLLM response.
    Returns (None, None) when usage isn't surfaced (some Ollama paths)."""
    try:
        u = getattr(resp, "usage", None)
        if u is None and isinstance(resp, dict):
            u = resp.get("usage")
        if u is None:
            return (None, None)
        # LiteLLM's Usage is dict-like / pydantic — accept either shape.
        get = (u.get if hasattr(u, "get") else lambda k, d=None: getattr(u, k, d))
        return (get("prompt_tokens"), get("completion_tokens"))
    except Exception:  # noqa: BLE001 — instrumentation must never throw
        return (None, None)


def _power_url() -> str | None:
    """Build the proxy's /v1/power URL from RIPRAP_LLM_BASE_URL.
    Returns None if remote isn't configured."""
    if not _VLLM_BASE:
        return None
    base = _VLLM_BASE
    # _VLLM_BASE looks like https://msradam-riprap-vllm.hf.space/v1
    # The proxy's /v1/power lives at the same /v1 prefix.
    if base.endswith("/v1"):
        return base + "/power"
    return base.rstrip("/") + "/v1/power"


def _sample_gpu_power_w() -> float | None:
    """Single GET to the proxy's /v1/power endpoint. Returns the
    instantaneous reading in watts, or None if unreachable / NVML off."""
    url = _power_url()
    if not url:
        return None
    try:
        import httpx as _httpx
        with _httpx.Client(timeout=2.0) as c:
            r = c.get(url, headers={"Authorization": f"Bearer {_VLLM_KEY}"})
        if r.status_code != 200:
            return None
        data = r.json()
        # Prefer the 1 s rolling average — smooths over the 100 ms sampler
        # so a single mid-idle tick doesn't poison the bracket.
        for k in ("power_w_avg_1s", "power_w", "power_w_avg_5s"):
            v = data.get(k)
            if isinstance(v, (int, float)) and v > 0:
                return float(v)
    except Exception:
        return None
    return None


def _record_llm(*, alias: str, messages: list[dict], duration_s: float,
                resp=None, completion_text: str | None = None,
                stream: bool = False,
                avg_power_w: float | None = None) -> None:
    """Record one llm.chat call into the active emissions tracker.

    For non-stream calls, we read prompt/completion tokens off the
    LiteLLM response. For stream calls, the response is a generator —
    we estimate tokens from concatenated assistant text and from a
    char/4 estimate of the input messages.

    `avg_power_w`, when provided, comes from a real NVML read on the
    inference proxy (bracketed before / after the call). The tracker
    converts that to joules via `power × duration` and flags the row
    `measured=True`. Estimates fall through to the data-sheet figure.
    """
    info = backend_info()
    hardware = _hardware_for(info["engine"])
    backend = info["engine"]
    prompt_tokens, completion_tokens = _extract_usage(resp) if resp is not None else (None, None)
    if prompt_tokens is None:
        prompt_chars = sum(len(m.get("content") or "") for m in messages)
        prompt_tokens = emissions.estimate_completion_tokens(
            " " * prompt_chars) if prompt_chars else None
    if completion_tokens is None and completion_text is not None:
        completion_tokens = emissions.estimate_completion_tokens(completion_text)
    joules_real = (avg_power_w * duration_s
                   if avg_power_w is not None and duration_s > 0 else None)
    emissions.active().record_llm(
        model=alias,
        backend=backend,
        hardware=hardware,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        duration_s=duration_s,
        stream=stream,
        joules_real=joules_real,
        power_w_real=avg_power_w,
    )


def _default_hardware_label() -> str:
    """Best-guess hardware label for the UI badge.

    Auto-detected from env. Operators can override with
    RIPRAP_HARDWARE_LABEL (e.g. "NVIDIA L4" / "AMD MI300X" /
    "NVIDIA T4" / "Apple M3 Pro").

    Default when a remote vLLM/Ollama backend is configured is "NVIDIA
    L4" — both Riprap inference Spaces (msradam/riprap-vllm,
    msradam/riprap-inference) run on L4. The MI300X droplet was
    decommissioned 2026-05-06; set RIPRAP_HARDWARE_LABEL=AMD MI300X
    explicitly if redeploying to that hardware.
    """
    if _PRIMARY == "vllm" and _VLLM_BASE:
        return "NVIDIA L4"
    if os.environ.get("SPACE_ID") or os.environ.get("HF_SPACE_ID"):
        return "NVIDIA T4"
    return "Local"


def backend_info() -> dict[str, Any]:
    """Static description of the active LLM routing for the /api/backend
    endpoint and the UI badge. Does not perform a network call; the
    /api/backend handler does its own reachability ping."""
    primary_engine = "vLLM" if _PRIMARY == "vllm" and _VLLM_BASE else "Ollama"
    fallback_engine = (
        "Ollama" if (_PRIMARY == "vllm" and _FALLBACK == "ollama")
        else None
    )
    return {
        "primary": _PRIMARY if _VLLM_BASE or _PRIMARY != "vllm" else "ollama",
        "engine": os.environ.get("RIPRAP_ENGINE_LABEL", primary_engine),
        "hardware": os.environ.get("RIPRAP_HARDWARE_LABEL",
                                   _default_hardware_label()),
        "model": os.environ.get("RIPRAP_RECONCILER_MODEL", _OLLAMA_8B_TAG),
        "vllm_base_url": _VLLM_BASE or None,
        "ollama_base_url": _OLLAMA_BASE,
        "fallback_engine": fallback_engine,
    }


def chat(model: str, messages: list[dict], options: dict | None = None,
         stream: bool = False, format: str | None = None):
    """Drop-in replacement for ollama.chat with router-managed failover.

    Returns:
      - stream=False: dict shaped like ollama's response
        ({"message": {"role": "assistant", "content": "..."}}).
      - stream=True: iterator yielding chunk dicts of the same shape.

    `format="json"` mirrors Ollama's JSON-mode forcing — translated to
    OpenAI's response_format for vLLM, and passed through unchanged for
    the Ollama backend.
    """
    alias = _resolve_alias(model)
    kwargs = _opts_to_kwargs(options)
    docs = _extract_documents(messages)
    if docs:
        # Merge into extra_body so Granite's HF chat template (vLLM)
        # picks them up. Ollama backend ignores extra_body and keeps
        # using the role="document <id>" messages already in `messages`.
        eb = kwargs.setdefault("extra_body", {})
        eb["documents"] = docs
        eb.setdefault("chat_template_kwargs", {})["documents"] = docs
    if format == "json":
        # OpenAI/vLLM path
        kwargs["response_format"] = {"type": "json_object"}
        # Ollama path (LiteLLM forwards this via extra_body for ollama_chat)
        kwargs.setdefault("extra_body", {})["format"] = "json"
    # Bracket the call with /v1/power samples so we get a real
    # NVML-derived energy reading, not a data-sheet estimate. Each
    # sample is a sub-100 ms GET; the proxy returns a 1 s rolling avg
    # so a single tick of idleness doesn't poison the bracket.
    p0 = _sample_gpu_power_w()
    t0 = time.monotonic()
    if stream:
        s = _router.completion(model=alias, messages=messages,
                               stream=True, **kwargs)

        def _on_stream_done(full_text: str) -> None:
            duration_s = time.monotonic() - t0
            p1 = _sample_gpu_power_w()
            avg = _avg_w(p0, p1)
            _record_llm(alias=alias, messages=messages,
                        duration_s=duration_s,
                        completion_text=full_text, stream=True,
                        avg_power_w=avg)

        return _stream_to_ollama_shape(s, on_done=_on_stream_done)
    resp = _router.completion(model=alias, messages=messages, **kwargs)
    duration_s = time.monotonic() - t0
    p1 = _sample_gpu_power_w()
    avg = _avg_w(p0, p1)
    _record_llm(alias=alias, messages=messages,
                duration_s=duration_s, resp=resp, stream=False,
                avg_power_w=avg)
    return _to_ollama_shape(resp)


def _avg_w(p0: float | None, p1: float | None) -> float | None:
    """Mean of two power samples; falls back to whichever single sample
    is available, or None if both failed."""
    pair = [p for p in (p0, p1) if p is not None]
    if not pair:
        return None
    return sum(pair) / len(pair)
