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
from collections.abc import Iterator
from typing import Any

import litellm
from litellm import Router

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

    for alias, (vllm_name, ollama_tag) in _LOGICAL.items():
        if use_vllm:
            model_list.append({
                "model_name": alias,
                "litellm_params": {
                    "model": f"openai/{vllm_name}",
                    "api_base": _VLLM_BASE,
                    "api_key": _VLLM_KEY,
                    "timeout": 240,
                    "stream_timeout": 240,
                },
            })
            if _FALLBACK == "ollama":
                fb_alias = f"{alias}-ollama"
                model_list.append({
                    "model_name": fb_alias,
                    "litellm_params": {
                        "model": f"ollama_chat/{ollama_tag}",
                        "api_base": _OLLAMA_BASE,
                        "timeout": 240,
                        "stream_timeout": 240,
                    },
                })
                fallbacks.append({alias: [fb_alias]})
        else:
            model_list.append({
                "model_name": alias,
                "litellm_params": {
                    "model": f"ollama_chat/{ollama_tag}",
                    "api_base": _OLLAMA_BASE,
                    "timeout": 240,
                    "stream_timeout": 240,
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
        timeout=240,
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


def _stream_to_ollama_shape(stream) -> Iterator[dict]:
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
        yield {"message": {"role": "assistant", "content": content}}


def _default_hardware_label() -> str:
    """Best-guess hardware label for the UI badge.

    Auto-detected from env. Operators can override with
    RIPRAP_HARDWARE_LABEL (e.g. "AMD MI300X" / "NVIDIA T4" / "Apple M3 Pro").
    """
    if _PRIMARY == "vllm" and _VLLM_BASE:
        return "AMD MI300X"
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
    if stream:
        s = _router.completion(model=alias, messages=messages,
                               stream=True, **kwargs)
        return _stream_to_ollama_shape(s)
    resp = _router.completion(model=alias, messages=messages, **kwargs)
    return _to_ollama_shape(resp)
