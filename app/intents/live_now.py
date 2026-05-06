"""live_now intent — only fire live specialists. No geocode, no static
historic/modeled layers. Reconciler emits a "right now" status note.

Targets are usually `{"type": "nyc"}` for the whole city; if the user
named a specific borough we still query at the same gauges (NOAA only
has 3 NYC stations) and the same NWS forecast zones (the API takes a
lat/lon point — we use a borough centroid).
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app import llm
from app.context import noaa_tides, nws_alerts, nws_obs
from app.live import ttm_forecast

log = logging.getLogger("riprap.intent.live_now")

import os as _os  # noqa: E402

# live_now stays on the smaller model: short outputs, speed matters more.
OLLAMA_MODEL = _os.environ.get("RIPRAP_LIVE_MODEL",
                                _os.environ.get("RIPRAP_OLLAMA_MODEL", "granite4.1:3b"))

# NWS API requires a lat/lon point; pick a representative one per borough.
BOROUGH_POINTS = {
    "Manhattan":     (40.7831, -73.9712),  # Central Park
    "Brooklyn":      (40.6500, -73.9500),  # Park Slope-ish
    "Queens":        (40.7282, -73.7949),  # Forest Hills
    "Bronx":         (40.8448, -73.8648),  # Fordham
    "Staten Island": (40.5795, -74.1502),  # central SI
    "NYC":           (40.7128, -74.0060),  # Lower Manhattan default
}


EXTRA_SYSTEM_PROMPT = """Write a current-conditions flood briefing for NYC. Use ONLY the facts in the provided documents.

Output this markdown skeleton verbatim, filling each `<...>` with content drawn only from the documents. After every numerical claim, append the document id in square brackets — e.g. `<value> [noaa_tides]`. Bold at most one phrase per section using `**...**`. Omit any section whose supporting facts are absent from the documents.

```
**Status.**
<one sentence on whether flood-relevant conditions are active right now, citing the strongest live signal>.

**Live signals.**
<1-3 sentences citing each live signal that fired: NWS alerts from [nws_alerts], tide observation and residual from [noaa_tides], recent precipitation from [nws_obs], any TTM forecast peak from [ttm_forecast]>.
```

Constraints:
- Be brief — current-conditions reports are read in seconds.
- Copy numerical values verbatim from documents. Do not round.
- Do not invoke historic events (Sandy, Ida) — this is a now-only report.
- If every live document indicates calm, write only: `**Status.** No active flood-relevant signals at this time [live_target].`
"""


def run(plan, query: str, progress_q=None) -> dict[str, Any]:  # TODO(cleanup): cc-grade-E (32)
    t0 = time.time()
    trace: list[dict] = []

    def _emit(r: dict):
        if progress_q is not None:
            progress_q.put({"kind": "step", **r})

    boro = next((t.get("text") for t in plan.targets if t.get("type") == "borough"), None)
    if boro and boro in BOROUGH_POINTS:
        lat, lon = BOROUGH_POINTS[boro]
        place = boro
    else:
        lat, lon = BOROUGH_POINTS["NYC"]
        place = "NYC"

    docs: list[dict] = []
    tides_out = alerts_out = obs_out = ttm_out = None

    if "noaa_tides" in plan.specialists:
        tides_out = _run_step(trace, "noaa_tides", lambda: noaa_tides.summary_for_point(lat, lon), progress_q)
    if "nws_alerts" in plan.specialists:
        alerts_out = _run_step(trace, "nws_alerts", lambda: nws_alerts.summary_for_point(lat, lon), progress_q)
    if "nws_obs" in plan.specialists:
        obs_out = _run_step(trace, "nws_obs", lambda: nws_obs.summary_for_point(lat, lon), progress_q)
    if "ttm_forecast" in plan.specialists:
        ttm_out = _run_step(trace, "ttm_forecast", lambda: ttm_forecast.summary_for_point(lat, lon), progress_q)

    # ---- documents ----
    docs.append({"role": "document live_target", "content":
        f"Source: planner. Live-conditions report for {place}. "
        f"Coordinates used for NWS lookups: {lat:.4f}, {lon:.4f}."})

    if tides_out and tides_out.get("observed_ft_mllw") is not None:
        body = [
            f"Source: NOAA CO-OPS Tides & Currents. Station: {tides_out['station_name']} "
            f"(NOAA {tides_out['station_id']}, {tides_out['distance_km']} km from {place}).",
            f"Observation time: {tides_out.get('obs_time') or 'unknown'}.",
            f"Observed water level: {tides_out['observed_ft_mllw']} ft above MLLW.",
        ]
        if tides_out.get("predicted_ft_mllw") is not None:
            body.append(f"Astronomical tide prediction at the same instant: "
                        f"{tides_out['predicted_ft_mllw']} ft.")
        if tides_out.get("residual_ft") is not None:
            body.append(f"Residual (observed - predicted): {tides_out['residual_ft']} ft. "
                        f"Positive = surge component above tide; negative = setdown.")
        docs.append(_doc("noaa_tides", body))

    if alerts_out and alerts_out.get("n_active", 0) > 0:
        body = [f"Source: NWS Public Alerts API. Active flood-relevant alerts: "
                f"{alerts_out['n_active']}."]
        for a in alerts_out["alerts"][:4]:
            body.append(
                f"- {a.get('event','?')} (severity: {a.get('severity','?')}, "
                f"urgency: {a.get('urgency','?')}); expires {a.get('expires','')[:16]}; "
                f"area: {(a.get('areaDesc') or '')[:120]}."
            )
            if a.get("headline"):
                body.append(f"  Headline: {a['headline'][:240]}")
        docs.append(_doc("nws_alerts", body))

    if obs_out and (obs_out.get("precip_last_hour_mm") is not None
                    or obs_out.get("precip_last_6h_mm") is not None):
        body = [
            f"Source: NWS Station Observations. Nearest ASOS: {obs_out['station_name']} "
            f"({obs_out['station_id']}, {obs_out['distance_km']} km).",
            f"Observation time: {obs_out.get('obs_time') or 'unknown'}.",
        ]
        if obs_out.get("precip_last_hour_mm") is not None:
            body.append(f"Precipitation last 1 h: {obs_out['precip_last_hour_mm']} mm.")
        if obs_out.get("precip_last_6h_mm") is not None:
            body.append(f"Precipitation last 6 h: {obs_out['precip_last_6h_mm']} mm.")
        docs.append(_doc("nws_obs", body))

    if ttm_out and ttm_out.get("available") and ttm_out.get("interesting"):
        docs.append(_doc("ttm_forecast", [
            "Source: Granite TimeSeries TTM r2 (Ekambaram et al. 2024).",
            f"Forecast peak surge residual at {ttm_out['station_name']}: "
            f"{ttm_out['forecast_peak_ft']} ft, expected "
            f"{ttm_out['forecast_peak_minutes_ahead']} minutes from now.",
            f"Recent peak |residual| in context window: "
            f"{ttm_out['history_peak_abs_ft']} ft.",
        ]))

    # ---- reconcile ----
    rec_t0 = time.time()
    rec_step = {"step": "reconcile_live_now", "started_at": rec_t0, "ok": False}
    trace.append(rec_step)
    if not docs or len(docs) == 1:  # only the live_target doc, no actual signals
        paragraph = ("**Status.** **No active flood-relevant signals at this time** for "
                     f"{place} [live_target].")
        audit = {"raw": paragraph, "dropped": []}
        rec_step["ok"] = True
    else:
        def _on_token(delta: str):
            if progress_q is not None:
                progress_q.put({"kind": "token", "delta": delta})
        try:
            from app.framing import augment_system_prompt
            framed_prompt = augment_system_prompt(
                EXTRA_SYSTEM_PROMPT, query=query, intent=plan.intent,
            )
            paragraph, audit = _reconcile(
                docs, on_token=_on_token if progress_q else None,
                system_prompt=framed_prompt,
            )
            rec_step["ok"] = True
        except Exception as e:
            paragraph = "Could not produce a live-conditions report."
            audit = {"raw": "", "dropped": []}
            rec_step["err"] = str(e)
    rec_step["elapsed_s"] = round(time.time() - rec_t0, 2)
    _emit(rec_step)

    return {
        "intent": "live_now",
        "query": query,
        "place": place,
        "plan": {
            "intent": plan.intent,
            "targets": plan.targets,
            "specialists": plan.specialists,
            "rationale": plan.rationale,
        },
        "noaa_tides":  tides_out,
        "nws_alerts":  alerts_out,
        "nws_obs":     obs_out,
        "ttm_forecast": ttm_out,
        "paragraph":   paragraph,
        "audit":       audit,
        "trace":       trace,
        "total_s":     round(time.time() - t0, 2),
    }


def _run_step(trace: list, name: str, fn, progress_q=None) -> Any:
    t0 = time.time()
    rec = {"step": name, "started_at": t0, "ok": False}
    trace.append(rec)
    try:
        out = fn()
        rec["ok"] = True
        rec["result"] = {k: out.get(k) for k in list(out.keys())[:3]} if isinstance(out, dict) else None
        return out
    except Exception as e:
        rec["err"] = str(e)
        log.exception("%s failed", name)
        return None
    finally:
        rec["elapsed_s"] = round(time.time() - t0, 2)
        if progress_q is not None:
            progress_q.put({"kind": "step", **rec})


def _doc(doc_id: str, body_lines: list[str]) -> dict:
    return {"role": f"document {doc_id}", "content": "\n".join(body_lines)}


def _reconcile(docs: list[dict], on_token=None,
                system_prompt: str = EXTRA_SYSTEM_PROMPT) -> tuple[str, dict]:
    from app.reconcile import verify_paragraph
    messages = docs + [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Write the live-conditions briefing now."},
    ]
    # live_now is the smallest intent: ~4 live docs, short briefing.
    # num_predict 200 caps to a 2-section status note.
    OPTS = {"temperature": 0, "num_ctx": 2048, "num_predict": 200}
    if on_token is None:
        resp = llm.chat(model=OLLAMA_MODEL, messages=messages, options=OPTS)
        raw = resp["message"]["content"].strip()
    else:
        chunks: list[str] = []
        for chunk in llm.chat(model=OLLAMA_MODEL, messages=messages,
                                 stream=True, options=OPTS):
            delta = (chunk.get("message") or {}).get("content") or ""
            if delta:
                chunks.append(delta)
                on_token(delta)
        raw = "".join(chunks).strip()
    cleaned, dropped = verify_paragraph(raw, docs)
    return cleaned, {"raw": raw, "dropped": dropped}
