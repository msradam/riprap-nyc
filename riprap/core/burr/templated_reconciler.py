"""Templated reconciler — the no-AI Capstone.

When `RIPRAP_RECONCILER_TIER=templated` (env), the top-level Burr app
swaps the Granite-streaming `step_reconcile` for `reconcile_templated`.
The result is a deterministic briefing built from each pebble's
`narration.template` (or `narration.short` as a fallback) interpolated
with that pebble's value dict.

Why this exists:
  * NGO / Pi-class deployments without a GPU or even a CPU LLM
  * Civic-tech audit: every claim is traceable to a manifest entry by
    construction — no hallucination surface
  * Latency: sub-second briefing prose. The whole `/api/agent` round
    trip lands in under 30 s end-to-end, dominated by live HTTP probes
  * A baseline that the LLM tier can be compared against

The output shape matches the LLM-tier `step_reconcile` exactly
(paragraph, audit, mellea, citations) so the SvelteKit frontend
renders identically regardless of tier.

Briefing structure mirrors the four-section format Granite produces:
  Status. — Sandy / DEP / Prithvi water proximity (Cornerstone gist)
  Empirical evidence. — Ida HWM + FloodNet + NYC 311 + microtopo
  Modeled scenarios. — DEP extreme/moderate scenarios + NPCC4 SLR
  Live signals. — NOAA tides + NWS obs/alerts + TTM forecasts
"""
from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any

from burr.core import State, action

from riprap.core.pebbles import load_registry
from riprap.core.pebbles.registry import Registry


def _registry() -> Registry:
    """Same registry the rest of the app uses; cached after first call
    through the bridge's module-level singleton."""
    import os
    from pathlib import Path
    deployment = os.environ.get("RIPRAP_DEPLOYMENT", "deployments/nyc")
    p = Path(deployment)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent.parent.parent / deployment
    return load_registry(p)


class _MissingTemplateField(KeyError):
    """Raised when a `narration.template` references a field that's not
    in the pebble's value dict, or the field is None. Caller falls back
    to `narration.short` rather than emitting `{field?}` placeholders
    into the briefing."""


def _format_template(template: str, value: dict[str, Any]) -> str:
    """Strict {field} substitution. Raises `_MissingTemplateField` when
    any referenced field is missing or None — callers handle the
    fallback (use `narration.short`, or skip the sentence entirely)."""
    if value is None:
        raise _MissingTemplateField("value is None")
    # Detect None-valued fields up-front; format() coerces None to "None"
    # which would silently produce garbage prose ("highest score was None").
    class _StrictMap(dict):
        def __missing__(self, key):
            raise _MissingTemplateField(key)

        def __getitem__(self, key):
            v = super().__getitem__(key)
            if v is None:
                raise _MissingTemplateField(key)
            return v
    return template.format_map(_StrictMap(value))


def _sentence_for(pebble_id: str, value: Any, manifest) -> str | None:
    """Build one citation-grounded sentence for a pebble.

    Priority:
      1. `narration.template` formatted with the pebble's dict value
      2. `narration.short` as a generic fallback
    Returns None if neither is set or the pebble had no value.
    """
    if value is None:
        return None
    short = manifest.narration.short
    template = manifest.narration.template
    doc = manifest.provenance.doc_id or pebble_id
    body: str | None = None
    if template and isinstance(value, dict):
        try:
            body = _format_template(template, value).strip()
        except _MissingTemplateField:
            # Template has a field the pebble didn't populate this run
            # (offline / partial). Fall back to the generic `short`.
            body = None
    if not body and short:
        body = short.strip()
    if not body:
        return None
    # Ensure the sentence ends with the citation marker the LLM tier
    # produces — so downstream code (cardAdapter citations, audit) is
    # tier-agnostic.
    if f"[{doc}]" not in body:
        body = body.rstrip(".") + f" [{doc}]."
    elif not body.rstrip().endswith("."):
        body += "."
    return body


def _section(heading: str, sentences: Iterable[str]) -> str:
    body = " ".join(s for s in sentences if s)
    if not body:
        return ""
    return f"**{heading}**\n{body}\n"


def _scope_header() -> str:
    """Hazard-agnostic scope declaration. Riprap-flood ships with the
    canonical flood phrasing; other deployments can override the wording
    by setting RIPRAP_BRIEFING_SCOPE (e.g. "automated heat-exposure
    briefing"). Defaults to the safe generic "hazard-exposure briefing."
    """
    import os
    scope_kind = os.environ.get("RIPRAP_BRIEFING_SCOPE", "hazard-exposure")
    return (
        f"This is an automated {scope_kind} briefing produced by Riprap from "
        "live and baked data sources. It is informational only and not a "
        "substitute for a professional risk assessment."
    )


_NON_SCOPE_FOOTER = (
    "**Out of scope.** This briefing does not assess title, structural "
    "condition, or compliance with specific zoning rules. Where a probe "
    "was offline at run time, the relevant section omits that signal."
)


def _stone_heading(stone) -> str:
    """Format a Stone's tagline as a briefing section heading.

      "the hazard reader" → "**Hazard reader.**"
    """
    tag = (stone.tagline or stone.name).strip()
    if tag.lower().startswith("the "):
        tag = tag[4:]
    return f"{tag[0].upper()}{tag[1:]}."


def _compose_briefing(state: State, registry: Registry) -> tuple[str, list[dict]]:
    """Hazard-agnostic briefing — one section per Stone, in stone-order
    from stones.yaml. Pebbles within each section are ordered by their
    `display.order`. Citations are collected from each pebble's
    provenance.

    Works for any deployment that ships a `stones.yaml` and pebbles
    tagged with `stone: <id>`. Flood, heat, air, future hazards.
    """
    import os
    from pathlib import Path

    from riprap.core.stones import load_stones

    deployment = os.environ.get("RIPRAP_DEPLOYMENT", "deployments/nyc")
    dep_root = Path(deployment)
    if not dep_root.is_absolute():
        dep_root = (Path(__file__).resolve().parent.parent.parent.parent
                    / deployment)
    stones = load_stones(dep_root)

    citations: list[dict] = []
    seen_docs: set[str] = set()

    def _ordered_pebble_ids(stone_id: str) -> list[str]:
        with_order: list[tuple[int, str]] = []
        for pid in registry.ids():
            p = registry.get(pid)
            if p.stone != stone_id:
                continue
            order = (p.manifest.display.order
                     if p.manifest.display.order is not None else 999)
            with_order.append((order, pid))
        return [pid for _, pid in sorted(with_order)]

    def _section_sentences_for_stone(stone_id: str) -> list[str]:
        out: list[str] = []
        for pid in _ordered_pebble_ids(stone_id):
            pebble = registry.get(pid)
            value = state.get(pid)
            sentence = _sentence_for(pid, value, pebble.manifest)
            if not sentence:
                continue
            out.append(sentence)
            doc_id = pebble.manifest.provenance.doc_id or pid
            if doc_id not in seen_docs:
                seen_docs.add(doc_id)
                citations.append({
                    "id": doc_id,
                    "label": pebble.manifest.provenance.source_name,
                    "href": pebble.manifest.provenance.source_url,
                    "citation": pebble.manifest.provenance.citation,
                })
        return out

    sections: list[str] = [_scope_header() + "\n"]          # ASTM 4.1/4.5/4.6
    for stone in stones.all():
        if stone.id == "capstone":
            continue   # Capstone is the synthesis output, not a data stone
        sentences = _section_sentences_for_stone(stone.id)
        if sentences:
            sections.append(_section(_stone_heading(stone), sentences))
    sections.append(_NON_SCOPE_FOOTER + "\n")                # ASTM 4.3

    paragraph = "\n".join(s for s in sections if s).strip()
    if not paragraph:
        paragraph = "No grounded data available for this address."
    return paragraph, citations


@action(
    reads=[
        "geocode", "intent",
        # Cornerstone
        "sandy", "dep", "ida_hwm", "prithvi_water", "microtopo",
        "dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current",
        # Touchstone
        "floodnet", "nyc311", "nws_obs", "noaa_tides", "prithvi_live",
        # Lodestone
        "nws_alerts", "ttm_forecast", "ttm_311_forecast", "floodnet_forecast",
        "ttm_battery_surge", "npcc4_slr",
        # Keystone
        "mta_entrances", "nycha_developments", "doe_schools", "doh_hospitals",
        # Optional chip-cluster outputs
        "terramind", "terramind_lulc", "terramind_buildings",
    ],
    writes=["paragraph", "audit", "mellea", "citations", "trace"],
)
def reconcile_templated(state: State) -> State:
    """Burr action: synthesize a briefing from manifest templates only.

    No LLM call. Output shape mirrors `step_reconcile` (paragraph,
    audit, mellea, citations) so the rest of the pipeline doesn't
    care which tier produced it.
    """
    trace = list(state.get("trace", []))
    rec = {
        "step": "reconcile_templated",
        "started_at": time.time(),
        "ok": True,
        "result": None,
        "err": None,
        "elapsed_s": 0.0,
    }
    try:
        registry = _registry()
        paragraph, citations = _compose_briefing(state, registry)
        rec["result"] = {
            "n_chars": len(paragraph),
            "n_citations": len(citations),
            "tier": "templated",
        }
        trace.append(rec)
        return state.update(
            paragraph=paragraph,
            audit={"raw": paragraph, "dropped": [], "tier": "templated"},
            # Mellea metadata: there's no rejection sampling in this tier;
            # we report 0 attempts so the UI can distinguish "no LLM ran"
            # from "LLM ran and passed".
            mellea={
                "rerolls": 0,
                "n_attempts": 0,
                "requirements_passed": [],
                "requirements_failed": [],
                "requirements_total": 0,
                "tier": "templated",
            },
            citations={c["id"]: c for c in citations},
            trace=trace,
        )
    except Exception as e:  # noqa: BLE001 — surfaced via trace
        rec["ok"] = False
        rec["err"] = str(e)
        trace.append(rec)
        return state.update(
            paragraph="Templated reconciler failed: " + str(e),
            audit={"raw": "", "dropped": [], "tier": "templated", "err": str(e)},
            mellea={"rerolls": 0, "n_attempts": 0,
                    "requirements_passed": [], "requirements_failed": [],
                    "requirements_total": 0, "tier": "templated"},
            citations={},
            trace=trace,
        )
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 4)
