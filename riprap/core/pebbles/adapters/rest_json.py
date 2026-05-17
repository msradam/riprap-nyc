"""rest_json — a pebble that fetches its value from a REST JSON endpoint.

The BYOD path for any HTTP API that returns JSON. The manifest declares
a URL template with {lat}/{lon} placeholders, optional auth headers
(with `${ENV_VAR}` interpolation so secrets stay out of YAML), and an
optional dotted path into the response.

Manifest config shape:

  adapter: rest_json
  config:
    url: https://api.example.com/heat/{lat},{lon}
    method: GET                       # currently GET only
    headers:
      Authorization: "Bearer ${HEAT_API_KEY}"
      Accept: application/json
    response_path: data.score         # optional; dotted path. Use [N] for list index.
    cache_ttl_s: 600
    timeout_s: 10

The pebble value is whatever JSON sits at `response_path` (or the full
response if not declared). When the request fails, the pebble respects
`fallback.on_offline: skip` and surfaces a clean error.

Power users with weird auth / pagination / response shapes should drop
to the `python_call` adapter instead.
"""
from __future__ import annotations

import os
import re
from typing import Any

import httpx

from riprap.core.pebbles._http import fetch_url_json
from riprap.core.pebbles.base import BasePebble, PebbleResult, SpatialQuery

_PATH_INDEX_RE = re.compile(r"^(.*?)\[(\d+)\]$")
_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _walk_response_path(data: Any, path: str) -> Any:
    """Resolve a dotted path with optional [N] list indexing. Returns None
    if any segment is missing (rather than raising) so manifest authors
    can use response_path defensively."""
    if not path:
        return data
    cur = data
    for raw_seg in path.split("."):
        seg = raw_seg.strip()
        index: int | None = None
        m = _PATH_INDEX_RE.match(seg)
        if m:
            seg = m.group(1)
            index = int(m.group(2))
        if seg:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(seg)
            if cur is None:
                return None
        if index is not None:
            if not isinstance(cur, list) or index >= len(cur):
                return None
            cur = cur[index]
    return cur


def _format_url(template: str, query: SpatialQuery) -> str:
    """Substitute env vars (`${VAR}`) and query placeholders
    (`{lat}` / `{lon}` / `{radius_m}`) in that order. Env-var
    substitution runs first so an unset key fails cleanly rather than
    polluting the URL with a literal `${VAR}` that the server rejects.

    Missing query placeholders pass through (a URL with no `{…}` is
    fine). Missing env vars resolve to empty string — same as the
    shared header interpolation in `_http.py`.
    """
    after_env = _ENV_VAR_RE.sub(
        lambda m: os.environ.get(m.group(1), ""),
        template,
    )
    return after_env.format(
        lat=query.lat if query.lat is not None else "",
        lon=query.lon if query.lon is not None else "",
        radius_m=query.radius_m if query.radius_m is not None else "",
    )


class RestJSONPebble(BasePebble):
    def _fetch_raw(self, query: SpatialQuery) -> PebbleResult:
        cfg = self.manifest.config
        url_template = cfg.get("url")
        if not url_template:
            return PebbleResult(
                pebble_id=self.id, value=None,
                error="rest_json: manifest.config.url is required",
            )
        method = (cfg.get("method") or "GET").upper()
        if method != "GET":
            return PebbleResult(
                pebble_id=self.id, value=None,
                error=f"rest_json: unsupported method {method!r} (GET only for now)",
            )

        try:
            url = _format_url(url_template, query)
        except KeyError as e:
            return PebbleResult(
                pebble_id=self.id, value=None,
                error=f"rest_json: missing placeholder in URL template: {e}",
            )

        try:
            data = fetch_url_json(
                url,
                cache_ttl_s=int(cfg.get("cache_ttl_s", 300)),
                headers=cfg.get("headers"),
                timeout_s=float(cfg.get("timeout_s", 10.0)),
            )
        except httpx.HTTPError as e:
            return PebbleResult(
                pebble_id=self.id, value=None, offline=True,
                error=f"rest_json: HTTP error: {e}",
            )

        value = _walk_response_path(data, cfg.get("response_path", "") or "")
        return PebbleResult(pebble_id=self.id, value=value)
