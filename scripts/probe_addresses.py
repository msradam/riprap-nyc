"""Riprap end-to-end address test suite.

Drives `/api/agent/stream` against a curated set of NYC addresses and
asserts that every Stone fires (or fails to fire with a deterministic
reason), the briefing prose contains all four sections, Mellea
grounding passes within attempt budget, and no specialist crashes with
an internal-API error (PreTrainedModel ModuleNotFoundError, etc).

Designed to be runnable both locally (M3 → laptop) and against the
deployed HF Space. The remote ML stack on the AMD MI300X is the same in
both cases when the env is configured, so an address that passes here
is the same address the hackathon judges will see.

Usage:
    .venv/bin/python scripts/probe_addresses.py
    .venv/bin/python scripts/probe_addresses.py --base http://127.0.0.1:7860
    .venv/bin/python scripts/probe_addresses.py \\
        --base https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space \\
        --addresses "PS 188, Lower East Side"
    .venv/bin/python scripts/probe_addresses.py --json outputs/probe_addresses.json

Exit code 0 if every address passes every assertion; 1 otherwise. CSV
goes to outputs/probe_addresses.csv; JSON dump (full payloads, useful
for the UI dev loop) optionally to --json.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

# Curated probe set. Each entry exercises a different surface of the
# system; together they cover every Stone's specialists at least once.
DEFAULT_ADDRESSES: list[dict[str, Any]] = [
    # Anchor each entry on a fully-qualified street address so the
    # geocoder doesn't drift to a same-named landmark in another borough
    # (e.g. there are several "PS 188" schools city-wide).
    {
        "query": "442 East Houston Street, Manhattan",  # PS 188 LES
        "intent": "single_address",
        "expect_sandy": True,        # in the empirical 2012 extent
        "expect_311_ge": 1,
        "borough": "Manhattan",
    },
    {
        "query": "80 Pioneer Street, Brooklyn",
        "intent": "single_address",
        "expect_sandy": True,        # Red Hook — canonical Sandy turf
        "expect_311_ge": 1,
        "expect_terramind_lulc_polygons": True,  # EO map-layer wiring check
        "borough": "Brooklyn",
    },
    {
        "query": "100 Gold Street, Manhattan",
        "intent": "single_address",
        # Outside Sandy 2012; this is the negative-control address.
        "expect_sandy": False,
        "borough": "Manhattan",
    },
    {
        "query": "Hollis, Queens",
        "intent": "neighborhood",
        "borough": "Queens",
    },
    {
        "query": "Coney Island, Brooklyn",
        "intent": "neighborhood",
        # neighborhood intent doesn't surface a per-address sandy field
        # in the final state — the briefing prose names the Sandy
        # exposure narratively from RAG + DEP layers.
        "borough": "Brooklyn",
    },
]


@dataclass
class StoneSummary:
    fired: int = 0
    errored: int = 0
    silent: int = 0
    total_seen: int = 0


@dataclass
class RunResult:
    query: str
    elapsed_s: float = 0.0
    intent: str | None = None
    paragraph: str = ""
    n_steps: int = 0
    steps: list[dict[str, Any]] = field(default_factory=list)
    final: dict[str, Any] = field(default_factory=dict)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    stones: dict[str, StoneSummary] = field(default_factory=lambda: defaultdict(StoneSummary))
    errors: list[str] = field(default_factory=list)
    error_steps: list[str] = field(default_factory=list)


# Mapping mirrors web/sveltekit/src/lib/client/cardAdapter.ts:stoneForStep.
# Recognizes both legacy step names (e.g. "sandy_inundation") and the new
# manifest-driven pebble ids the Burr app emits ("sandy", per
# deployments/nyc/manifests/sandy.yaml). Keep both as the legacy
# intent modules stay reachable via RIPRAP_USE_BURR_APP=0.
def _stone_for_step(step: str) -> str | None:
    n = (step or "").lower()
    if n in {"sandy_inundation", "sandy",
             "dep_stormwater",
             "dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current",
             "ida_hwm_2021", "ida_hwm",
             "prithvi_eo_v2", "prithvi_water",
             "microtopo_lidar", "microtopo"}:
        return "cornerstone"
    if n in {"mta_entrance_exposure", "mta_entrances",
             "nycha_development_exposure", "nycha_developments",
             "doe_school_exposure", "doe_schools",
             "doh_hospital_exposure", "doh_hospitals",
             "terramind_synthesis", "terramind_buildings", "eo_chip_fetch"}:
        return "keystone"
    if n in {"floodnet", "nyc311", "nws_obs", "noaa_tides",
             "prithvi_eo_live", "prithvi_live", "terramind_lulc"}:
        return "touchstone"
    if n in {"nws_alerts", "ttm_forecast", "ttm_311_forecast",
             "floodnet_forecast", "ttm_battery_surge"}:
        return "lodestone"
    if n.startswith("reconcile") or n.startswith("mellea") or \
            n in {"rag_granite_embedding", "gliner_extract",
                  "assemble_legacy_state"}:
        return "capstone"
    return None


def stream_one(query: str, base: str, timeout_s: float) -> RunResult:  # TODO(cleanup): cc-grade-D (21)
    """Drive one SSE run, accumulate every event into a RunResult."""
    url = f"{base}/api/agent/stream?q={quote(query)}"
    res = RunResult(query=query)
    t0 = time.time()
    paragraph = ""

    with httpx.stream("GET", url, timeout=timeout_s) as r:
        r.raise_for_status()
        ev = None
        buf: list[str] = []
        for line in r.iter_lines():
            if line.startswith("event:"):
                ev = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                buf.append(line[5:].lstrip())
            elif line == "":
                if not (ev and buf):
                    ev = None
                    buf = []
                    continue
                data = "\n".join(buf)
                buf = []
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    payload = {"_raw": data}
                if ev == "plan":
                    res.intent = payload.get("intent")
                elif ev == "step":
                    res.n_steps += 1
                    res.steps.append(payload)
                    stone = _stone_for_step(payload.get("step", ""))
                    if stone:
                        s = res.stones[stone]
                        s.total_seen += 1
                        if not payload.get("ok"):
                            s.errored += 1
                            res.error_steps.append(payload.get("step", ""))
                        elif payload.get("result") is None and payload.get("err") is None:
                            s.silent += 1
                        else:
                            s.fired += 1
                elif ev == "token":
                    paragraph += payload.get("delta") or ""
                elif ev == "mellea_attempt":
                    res.attempts.append(payload)
                elif ev == "final":
                    res.final = payload
                    if isinstance(payload.get("paragraph"), str):
                        paragraph = payload["paragraph"]
                elif ev == "error":
                    res.errors.append(str(payload.get("err") or payload))
                ev = None
    res.elapsed_s = round(time.time() - t0, 2)
    res.paragraph = paragraph
    return res


# ---- Assertions ----------------------------------------------------------

# Flag step-result errors that look like the local-fallback ModuleNotFoundError
# we just hardened against. If any address surfaces this string, the
# guard-rail regressed.
_ERROR_REGRESSIONS = (
    "ModuleNotFoundError",
    "Could not import module 'PreTrainedModel'",
)

# Briefing section headings the system prompt teaches Granite to emit.
# Granite's exact rendering varies per attempt — sometimes
# `**Status.**` on its own line, sometimes inline. We treat each section
# as present if its label appears at all (case-insensitive).
#
# The system prompt says "Omit any section whose supporting facts are
# absent from the documents" — so on a query with no RAG hits the
# Policy-context section is correctly skipped. We require Status +
# Empirical evidence + Modeled scenarios always; Policy context is
# best-effort.
_REQUIRED_HEADINGS = (
    "Status",
    "Empirical evidence",
    "Modeled scenarios",
)
_OPTIONAL_HEADINGS = ("Policy context",)


def assert_run(spec: dict[str, Any], r: RunResult) -> list[str]:  # TODO(cleanup): cc-grade-F (42)
    """Return a list of failures (empty list if the run passes)."""
    fails: list[str] = []
    if r.errors:
        fails.append(f"stream errors: {r.errors}")

    # Specialist regressions — the LOD-002/003/004 ModuleNotFoundError
    # category. If any step result string contains those keywords we
    # treat it as a hard regression of the pre-import hardening.
    for step in r.steps:
        err = step.get("err") or ""
        for marker in _ERROR_REGRESSIONS:
            if marker in str(err):
                fails.append(
                    f"{step.get('step')}: {marker} regressed in step error"
                )

    # Intent classification.
    expected_intent = spec.get("intent")
    if expected_intent and r.intent and r.intent != expected_intent:
        fails.append(f"intent={r.intent} expected {expected_intent}")

    # Briefing presence.
    if not r.paragraph or len(r.paragraph) < 200:
        fails.append(f"briefing too short: {len(r.paragraph)} chars")
    else:
        para_lower = r.paragraph.lower()
        for heading in _REQUIRED_HEADINGS:
            if heading.lower() not in para_lower:
                fails.append(f"briefing missing heading {heading!r}")

    # Mellea grounding.
    final = r.final or {}
    m = final.get("mellea") or {}
    passed = m.get("requirements_passed") or []
    total = m.get("requirements_total") or 0
    if total:
        if len(passed) < total:
            failed_names = ",".join(m.get("requirements_failed") or []) or "?"
            fails.append(
                f"mellea: only {len(passed)}/{total} grounding checks passed "
                f"(failed: {failed_names})"
            )
    elif r.attempts:
        last = r.attempts[-1]
        if last.get("failed"):
            fails.append(f"mellea: last attempt failed {last['failed']}")

    # Stones — the per-stone requirement is intent-dependent. The
    # single_address FSM fires every stone's specialists (Cornerstone /
    # Keystone / Touchstone / Lodestone). The neighborhood and
    # development_check intents have a smaller fixed surface that does
    # not exercise the address-level register / live-now stones — they
    # rely on RAG + a smaller set of specialists. So we only enforce
    # the full Stone roster for single_address; for the others we just
    # check Capstone fires (RAG / GLiNER / reconcile are universal).
    intent = (r.intent or expected_intent or "single_address").lower()
    if intent == "single_address":
        for stone in ("cornerstone", "touchstone", "lodestone"):
            s = r.stones.get(stone)
            if not s or s.fired == 0:
                fails.append(
                    f"{stone}: 0 specialists fired "
                    f"(saw {s.total_seen if s else 0})"
                )
        s = r.stones.get("keystone")
        if not s or s.total_seen == 0:
            fails.append("keystone: no specialists attempted")
    s = r.stones.get("capstone")
    if not s or s.fired == 0:
        fails.append(
            f"capstone: 0 fired — reconcile/rag/gliner step events missing "
            f"(saw {s.total_seen if s else 0})"
        )

    # Spec-driven asserts (only meaningful for single_address — the
    # neighborhood / development_check intents have no per-address
    # sandy / 311 fields in the final state).
    if intent == "single_address":
        sandy_state = (final.get("sandy") is True)
        if "expect_sandy" in spec:
            want = spec["expect_sandy"]
            if sandy_state is not want:
                fails.append(f"sandy={sandy_state} expected {want}")
        n311 = (final.get("nyc311") or {}).get("n") or 0
        if "expect_311_ge" in spec and n311 < spec["expect_311_ge"]:
            fails.append(f"nyc311={n311} expected >= {spec['expect_311_ge']}")

        # EO map-layer wiring check: TerraMind LULC must produce polygons
        # when its specialist fires (ok=True). Prithvi and TerraMind
        # Buildings are accepted as silent — no pluvial flood / no
        # building change is a valid result, not a bug. This catches the
        # regression where specialists fire but polygons_geojson is
        # dropped before reaching the final state.
        if spec.get("expect_terramind_lulc_polygons"):
            tm = final.get("terramind") or {}
            if not tm.get("ok"):
                fails.append("terramind_lulc: ok=False — LULC specialist did not fire")
            else:
                n_poly = len((tm.get("polygons_geojson") or {}).get("features") or [])
                if n_poly == 0:
                    fails.append("terramind_lulc: ok=True but 0 polygons in final state")

    return fails


# ---- Entry point ---------------------------------------------------------

def main() -> int:  # TODO(cleanup): cc-grade-D (28)
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:7860",
                    help="Riprap server base URL")
    ap.add_argument("--addresses", default="",
                    help="Pipe-separated subset of queries to run "
                         "(addresses themselves contain commas, so pipe is "
                         "the separator); default runs the full curated set")
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--out", default="outputs/probe_addresses.csv")
    ap.add_argument("--json", default="",
                    help="Optional path to dump full per-address JSON payload")
    args = ap.parse_args()

    if args.addresses:
        wanted = {a.strip() for a in args.addresses.split("|") if a.strip()}
        specs = [s for s in DEFAULT_ADDRESSES if s["query"] in wanted]
        if not specs:
            specs = [{"query": q} for q in wanted]
    else:
        specs = list(DEFAULT_ADDRESSES)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, Any]] = []
    full: list[dict[str, Any]] = []
    all_pass = True

    print(f"Probing {len(specs)} addresses against {args.base}")
    print()

    for i, spec in enumerate(specs, 1):
        q = spec["query"]
        print(f"[{i}/{len(specs)}] {q!r:50s}", end="  ", flush=True)
        try:
            r = stream_one(q, args.base, args.timeout)
        except Exception as e:
            print(f"STREAM ERROR: {type(e).__name__}: {e}")
            summary_rows.append({"query": q, "ok": False,
                                  "fails": f"stream raised: {e}"})
            all_pass = False
            continue
        fails = assert_run(spec, r)
        ok = not fails
        all_pass &= ok
        m = (r.final or {}).get("mellea") or {}
        passed = m.get("requirements_passed") or []
        rerolls = m.get("rerolls") if m.get("rerolls") is not None else \
            (max(0, (m.get("n_attempts") or 1) - 1))
        verdict = "PASS" if ok else "FAIL"
        print(f"{verdict}  {r.elapsed_s:6.1f}s  "
              f"steps={r.n_steps} prose={len(r.paragraph)}c "
              f"mellea={len(passed)}/{m.get('requirements_total') or '?'} "
              f"rerolls={rerolls}")
        for f in fails:
            print(f"        - {f}")

        summary_rows.append({
            "query": q, "ok": ok, "elapsed_s": r.elapsed_s, "intent": r.intent,
            "n_steps": r.n_steps,
            "para_chars": len(r.paragraph),
            "mellea_passed": len(passed),
            "mellea_total": m.get("requirements_total") or 0,
            "rerolls": rerolls,
            "stones_fired": ",".join(
                f"{k}={v.fired}" for k, v in sorted(r.stones.items())),
            "stones_errored": ",".join(
                f"{k}={v.errored}" for k, v in sorted(r.stones.items())
                if v.errored),
            "errored_steps": ",".join(r.error_steps),
            "fails": " | ".join(fails),
        })
        full.append({
            "spec": spec,
            "elapsed_s": r.elapsed_s,
            "intent": r.intent,
            "paragraph": r.paragraph,
            "stones": {k: vars(v) for k, v in r.stones.items()},
            "mellea": m,
            "attempts": r.attempts,
            "errors": r.errors,
            "error_steps": r.error_steps,
            "fails": fails,
        })

    out_path = Path(args.out)
    if summary_rows:
        with out_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
            w.writeheader()
            w.writerows(summary_rows)
        print(f"\nWrote {out_path}")
    if args.json:
        json_path = Path(args.json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(full, indent=2, default=str))
        print(f"Wrote {json_path}")

    print()
    print("=" * 70)
    print(f"  {sum(1 for r in summary_rows if r.get('ok'))}/{len(summary_rows)} addresses passed")
    print("=" * 70)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
