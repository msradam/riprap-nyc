"""HTTP fetch + TTL cache shared by URL-capable pebble adapters.

Two functions:
  fetch_url_text(url, *, cache_ttl_s, headers, timeout_s) -> str
  fetch_url_json(url, *, cache_ttl_s, headers, timeout_s) -> Any

Cache is in-memory, keyed by (url, frozenset of headers). Entries expire
after `cache_ttl_s` seconds. A TTL of 0 disables caching for that call.

Header values support `${ENV_VAR}` interpolation so manifests can declare
auth tokens without baking secrets into YAML (the substitution happens
at request time, never written back into the manifest).
"""
from __future__ import annotations

import os
import re
import time
from typing import Any

import httpx

_CACHE: dict[tuple, tuple[float, Any]] = {}

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _interpolate_headers(headers: dict[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    out: dict[str, str] = {}
    for k, v in headers.items():
        out[k] = _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), str(v))
    return out


def _cache_key(url: str, headers: dict[str, str]) -> tuple:
    return (url, frozenset(headers.items()))


def fetch_url_text(url: str, *, cache_ttl_s: int = 300,
                   headers: dict[str, str] | None = None,
                   timeout_s: float = 10.0) -> str:
    h = _interpolate_headers(headers)
    key = _cache_key(url, h)
    now = time.time()
    if cache_ttl_s > 0:
        hit = _CACHE.get(key)
        if hit is not None and (now - hit[0]) < cache_ttl_s:
            return hit[1]
    with httpx.Client(timeout=timeout_s, follow_redirects=True) as c:
        r = c.get(url, headers=h)
        r.raise_for_status()
        text = r.text
    if cache_ttl_s > 0:
        _CACHE[key] = (now, text)
    return text


def fetch_url_json(url: str, *, cache_ttl_s: int = 300,
                   headers: dict[str, str] | None = None,
                   timeout_s: float = 10.0) -> Any:
    h = _interpolate_headers(headers)
    key = _cache_key(url, h) + ("__json__",)
    now = time.time()
    if cache_ttl_s > 0:
        hit = _CACHE.get(key)
        if hit is not None and (now - hit[0]) < cache_ttl_s:
            return hit[1]
    with httpx.Client(timeout=timeout_s, follow_redirects=True) as c:
        r = c.get(url, headers=h)
        r.raise_for_status()
        data = r.json()
    if cache_ttl_s > 0:
        _CACHE[key] = (now, data)
    return data


def clear_cache() -> None:
    """For tests."""
    _CACHE.clear()
