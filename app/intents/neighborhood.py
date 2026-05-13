"""neighborhood intent — resolve target text to one or more NTA polygons,
then run polygon-level specialists and reconcile.

The set of polygon-capable specialists is currently:
  - sandy_inundation.coverage_for_polygon
  - dep_stormwater.coverage_for_polygon (per scenario)
  - nyc311.summary_for_polygon
  - microtopo.microtopo_for_polygon

Other specialists (FloodNet, Ida HWM, Prithvi) are still point-based;
in Phase 2 we'll add polygon support for them. For now, neighborhood
mode produces the four signals above + RAG, and the reconciler emits
a structurally-different briefing aimed at a place rather than an
address.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app import llm
from app.areas import nta
from app.context import microtopo, nyc311
from app.flood_layers import dep_stormwater, sandy_inundation
from app.rag import retrieve as rag_retrieve
from app.reconcile import citations_from_docs

log = logging.getLogger("riprap.intent.neighborhood")

import os as _os  # noqa: E402

OLLAMA_MODEL = _os.environ.get("RIPRAP_RECONCILER_MODEL",
                                _os.environ.get("RIPRAP_OLLAMA_MODEL", "granite4.1:8b"))

EXTRA_SYSTEM_PROMPT = """Write a flood-exposure briefing for an NYC neighborhood. Use ONLY the facts in the provided documents.

Output this markdown skeleton verbatim, filling each `<...>` with content drawn only from the documents. After every numerical claim, append the document id in square brackets — e.g. `<value> [sandy_nta]`. Bold at most one phrase per section using `**...**`. Omit any section whose supporting facts are absent from the documents.

```
**Status.**
<one sentence: name the neighborhood from [nta_resolve] and the dominant exposure pattern>.

**Empirical evidence.**
<1-3 sentences citing observed flood evidence: Sandy coverage from [sandy_nta], 311 counts from [nyc311_nta], any FloodNet or HWM signals>.

**Modeled scenarios.**
<1-2 sentences citing modeled flooding from [dep_*_nta] (fraction of polygon in each scenario) and terrain from [microtopo_nta] (median HAND, fraction of polygon with HAND below 1 m)>.

**Policy context.**
<1 sentence per RAG hit, citing the agency name and [rag_*]>.
```

Constraints:
- Copy numerical values verbatim from documents. Do not round, paraphrase, or substitute.
- Speak about the place as a polygon (use phrases like "of the neighborhood" or "of the NTA"), not as an address.
- If only [nta_resolve] is present and no other documents, output exactly: `No grounded data available for this neighborhood.`
"""


def run(plan, query: str, progress_q=None, strict: bool = False) -> dict[str, Any]:  # TODO(cleanup): cc-grade-F (73)
    """Execute the planner's neighborhood Plan.

    Resolves all targets to NTAs, picks the largest matching NTA (or the
    first if multiple equally good), runs the polygon specialists, and
    reconciles via Granite 4.1.

    strict=True routes the reconciler through Mellea-validated rejection
    sampling. Disables token streaming.
    """
    t0 = time.time()
    trace: list[dict] = []

    def _emit(r: dict):
        if progress_q is not None:
            progress_q.put({"kind": "step", **r})

    # Resolve targets to NTAs. Try the planner's pick first; if it gave no
    # usable target, scan the raw query text for any known neighborhood name.
    target_text = next(
        (t["text"] for t in plan.targets if t.get("type") in ("nta", "borough")),
        None,
    )
    rec = {"step": "nta_resolve", "started_at": t0, "ok": False}
    trace.append(rec)
    matches = nta.resolve(target_text) if target_text else []
    if not matches:
        matches = nta.resolve_from_text(query)
    if not matches:
        rec["err"] = f"no NTA match in target={target_text!r} or query={query!r}"
        rec["elapsed_s"] = round(time.time() - t0, 2)
        return _empty_result(plan, query, trace, error=rec["err"])
    target = matches[0]
    rec["ok"] = True
    rec["result"] = {
        "nta_code": target["nta_code"],
        "nta_name": target["nta_name"],
        "borough":  target["borough"],
        "n_matches": len(matches),
        # Bbox lets the UI fly-to and render the polygon while the rest
        # of the specialists are still running.
        "bbox":     list(target["geometry"].bounds),
    }
    rec["elapsed_s"] = round(time.time() - t0, 2)
    _emit(rec)

    poly = target["geometry"]
    docs: list[dict] = []
    sandy_out = None
    dep_out = {}
    nyc311_out = None
    micro_out = None
    rag_out = []
    prithvi_live_out = None
    terramind_out = None

    # ---- sandy ----
    if "sandy" in plan.specialists:
        s_t0 = time.time()
        srec = {"step": "sandy_nta", "started_at": s_t0, "ok": False}
        trace.append(srec)
        try:
            sandy_out = sandy_inundation.coverage_for_polygon(poly)
            srec["ok"] = True
            srec["result"] = {"fraction": sandy_out["fraction"], "inside": sandy_out["inside"]}
        except Exception as e:
            srec["err"] = str(e)
            log.exception("sandy polygon failed")
        srec["elapsed_s"] = round(time.time() - s_t0, 2)
        _emit(srec)

    # ---- dep_stormwater ----
    if "dep_stormwater" in plan.specialists:
        for scen in ["dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current"]:
            d_t0 = time.time()
            drec = {"step": f"{scen}_nta", "started_at": d_t0, "ok": False}
            trace.append(drec)
            try:
                cov = dep_stormwater.coverage_for_polygon(poly, scen)
                dep_out[scen] = cov
                drec["ok"] = True
                drec["result"] = {"fraction_any": cov["fraction_any"]}
            except Exception as e:
                drec["err"] = str(e)
                log.exception("%s polygon failed", scen)
            drec["elapsed_s"] = round(time.time() - d_t0, 2)
            _emit(drec)

    # ---- nyc311 ----
    if "nyc311" in plan.specialists:
        n_t0 = time.time()
        nrec = {"step": "nyc311_nta", "started_at": n_t0, "ok": False}
        trace.append(nrec)
        try:
            nyc311_out = nyc311.summary_for_polygon(poly, years=3)
            nrec["ok"] = True
            nrec["result"] = {"n": nyc311_out["n"]}
        except Exception as e:
            nrec["err"] = str(e)
            log.exception("nyc311 polygon failed")
        nrec["elapsed_s"] = round(time.time() - n_t0, 2)
        _emit(nrec)

    # ---- microtopo ----
    if "microtopo" in plan.specialists:
        m_t0 = time.time()
        mrec = {"step": "microtopo_nta", "started_at": m_t0, "ok": False}
        trace.append(mrec)
        try:
            micro_out = microtopo.microtopo_for_polygon(poly)
            mrec["ok"] = micro_out is not None
            mrec["result"] = {
                "elev_median_m": (micro_out or {}).get("elev_median_m"),
                "frac_hand_lt1": (micro_out or {}).get("frac_hand_lt1"),
            }
        except Exception as e:
            mrec["err"] = str(e)
            log.exception("microtopo polygon failed")
        mrec["elapsed_s"] = round(time.time() - m_t0, 2)
        _emit(mrec)

    # ---- Prithvi-EO live water mask (NTA centroid) ----
    # Polygon-scoped queries don't have a single point of interest, but
    # the NTA centroid is a fair sampling point: the 5 km chip the
    # specialist fetches comfortably covers any NTA. The reconciler
    # gets an `[prithvi_live]` doc with the % water observed today, and
    # the frontend gets a GeoJSON layer to paint over the NTA polygon.
    try:
        from app.flood_layers import prithvi_live as plive_mod
        if plive_mod.ENABLE:
            p_t0 = time.time()
            prec = {"step": "prithvi_eo_live", "started_at": p_t0, "ok": False}
            trace.append(prec)
            centroid = poly.centroid
            prithvi_live_out = plive_mod.fetch(centroid.y, centroid.x)
            prec["ok"] = bool(prithvi_live_out and prithvi_live_out.get("ok"))
            if prec["ok"]:
                prec["result"] = {
                    "scene_date": (prithvi_live_out.get("item_datetime") or "")[:10],
                    "cloud_cover": prithvi_live_out.get("cloud_cover"),
                    "pct_water_5km": prithvi_live_out.get("pct_water_full"),
                }
            else:
                prec["err"] = (prithvi_live_out or {}).get("err") \
                    or (prithvi_live_out or {}).get("skipped") or "no observation"
            prec["elapsed_s"] = round(time.time() - p_t0, 2)
            _emit(prec)
    except Exception as e:
        log.exception("prithvi_live (neighborhood) failed")
        prithvi_live_out = {"ok": False, "err": str(e)}

    # ---- TerraMind synthesis (NTA centroid) ----
    # Generative-prior tier — synthesized ESRI Land Cover from the
    # local LiDAR DEM at the NTA centroid. Renders as dashed-outline
    # polygons on the map alongside the polygon-aggregated specialists.
    try:
        from app.context import terramind_synthesis as tm_mod
        if tm_mod.ENABLE:
            t_t0 = time.time()
            trec = {"step": "terramind_synthesis", "started_at": t_t0, "ok": False}
            trace.append(trec)
            centroid = poly.centroid
            terramind_out = tm_mod.fetch(centroid.y, centroid.x)
            trec["ok"] = bool(terramind_out and terramind_out.get("ok"))
            if trec["ok"]:
                trec["result"] = {
                    "tim_chain": terramind_out.get("tim_chain"),
                    "dominant_class": terramind_out.get("dominant_class_display")
                                       or terramind_out.get("dominant_class"),
                    "dominant_pct": terramind_out.get("dominant_pct"),
                    "n_classes": terramind_out.get("n_classes_observed"),
                }
            else:
                trec["err"] = (terramind_out or {}).get("err") \
                    or (terramind_out or {}).get("skipped") or "no synthesis"
            trec["elapsed_s"] = round(time.time() - t_t0, 2)
            _emit(trec)
    except Exception as e:
        log.exception("terramind (neighborhood) failed")
        terramind_out = {"ok": False, "err": str(e)}

    # ---- rag ----
    if "rag" in plan.specialists:
        r_t0 = time.time()
        rrec = {"step": "rag_nta", "started_at": r_t0, "ok": False}
        trace.append(rrec)
        try:
            q = (f"flood exposure {target['nta_name']} {target['borough']} "
                 "vulnerability hardening mitigation")
            rag_out = rag_retrieve(q, k=3, min_score=0.45)
            rrec["ok"] = True
            rrec["result"] = {"hits": len(rag_out)}
        except Exception as e:
            rrec["err"] = str(e)
            log.exception("rag polygon failed")
        rrec["elapsed_s"] = round(time.time() - r_t0, 2)
        _emit(rrec)

    # ---- build documents ----
    docs.append(_doc("nta_resolve", [
        "Source: NYC DCP Neighborhood Tabulation Areas 2020.",
        f"Target neighborhood: {target['nta_name']} (NTA {target['nta_code']}), "
        f"in the borough of {target['borough']}.",
        f"Community District: {target.get('cdta') or 'unknown'}.",
    ]))
    if sandy_out and sandy_out["inside"]:
        docs.append(_doc("sandy_nta", [
            "Source: NYC Sandy Inundation Zone (NYC OD 5xsi-dfpx).",
            f"Fraction of {target['nta_name']} inside the 2012 inundation extent: "
            f"{sandy_out['fraction'] * 100:.1f}%.",
            f"Total NTA area: {sandy_out['polygon_area_m2']/1e6:.2f} km².",
        ]))
    for scen, cov in dep_out.items():
        if cov["fraction_any"] > 0:
            cls = cov["fraction_class"]
            docs.append(_doc(f"{scen}_nta", [
                f"Source: {cov['label']}.",
                f"Fraction of {target['nta_name']} inside any modeled flooded area: "
                f"{cov['fraction_any'] * 100:.1f}%.",
                f"Of which: {cls.get(1, 0) * 100:.1f}% in nuisance band (>4 in to 1 ft), "
                f"{cls.get(2, 0) * 100:.1f}% in 1-4 ft band, "
                f"{cls.get(3, 0) * 100:.1f}% in >4 ft band.",
            ]))
    if nyc311_out and nyc311_out.get("n", 0) > 0:
        body = [
            "Source: NYC 311 service requests (Socrata erm2-nwe9), aggregated inside the NTA polygon.",
            f"Flood-related complaints in the last 3 years inside {target['nta_name']}: "
            f"{nyc311_out['n']}.",
        ]
        if nyc311_out.get("by_descriptor"):
            top = "; ".join(f"{k}: {v}" for k, v in list(nyc311_out["by_descriptor"].items())[:3])
            body.append(f"Top descriptors: {top}.")
        docs.append(_doc("nyc311_nta", body))
    if micro_out and micro_out.get("n_cells", 0) > 0:
        body = [
            "Source: USGS 3DEP DEM (precomputed citywide GeoTIFF) with derived HAND and TWI rasters; aggregated over NTA polygon.",
            f"Polygon contains {micro_out['n_cells']} 30-m DEM cells.",
            f"Median elevation: {micro_out['elev_median_m']} m; "
            f"10th-percentile elevation: {micro_out['elev_p10_m']} m.",
        ]
        if micro_out.get("hand_median_m") is not None:
            body.append(
                f"Median HAND (Height Above Nearest Drainage): "
                f"{micro_out['hand_median_m']} m. "
                f"Fraction of polygon cells with HAND below 1 m "
                f"(near-channel, water reaches at flood): "
                f"{(micro_out.get('frac_hand_lt1') or 0) * 100:.1f}%."
            )
        if micro_out.get("twi_median") is not None:
            body.append(
                f"Median TWI: {micro_out['twi_median']}. "
                f"Fraction of polygon cells with TWI > 10 (saturation-prone): "
                f"{(micro_out.get('frac_twi_gt10') or 0) * 100:.1f}%."
            )
        docs.append(_doc("microtopo_nta", body))
    if prithvi_live_out and prithvi_live_out.get("ok"):
        docs.append(_doc("prithvi_live", [
            "Source: Prithvi-EO 2.0 (Sen1Floods11 fine-tune) live "
            "segmentation over a Sentinel-2 L2A scene from Microsoft "
            f"Planetary Computer, sampled at the NTA centroid of "
            f"{target['nta_name']}.",
            f"Sentinel-2 scene id: {prithvi_live_out.get('item_id')}.",
            f"Observation date: "
            f"{(prithvi_live_out.get('item_datetime') or '')[:10]}.",
            f"Cloud cover: {prithvi_live_out.get('cloud_cover', 0):.3f}%.",
            f"% water across the 5 km chip around the centroid: "
            f"{prithvi_live_out.get('pct_water_full', 0):.2f}.",
        ]))
    if terramind_out and terramind_out.get("ok"):
        body = [
            "Source: TerraMind 1.0 base (IBM/ESA, Apache-2.0) any-to-any "
            "generative foundation model. SYNTHETIC PRIOR — generated "
            "categorical land-cover from the LiDAR DEM at the NTA "
            f"centroid of {target['nta_name']}; not a measurement.",
            f"Chain: {' -> '.join(terramind_out.get('tim_chain') or ['DEM','LULC_synthetic'])}.",
            f"Diffusion steps: {terramind_out.get('diffusion_steps')}.",
            f"Diffusion seed: {terramind_out.get('diffusion_seed')}.",
            f"Dominant synthetic class: "
            f"{terramind_out.get('dominant_class_display') or terramind_out.get('dominant_class')} "
            f"at {terramind_out.get('dominant_pct', 0):.1f}% (tentative ESRI "
            "Land Cover labels).",
        ]
        for label, pct in (terramind_out.get("class_fractions") or {}).items():
            body.append(f"  - {label}: {pct:.1f}%")
        body.append("Use 'TerraMind generated a plausible synthetic "
                    "land-cover prior' framing — never 'imaged' or "
                    "'reconstructed'.")
        docs.append(_doc("terramind_synthetic", body))
    for h in rag_out:
        docs.append(_doc(h["doc_id"], [
            f"Source: {h['citation']}, page {h.get('page', '')}.",
            f"Retrieved passage (verbatim): {h['text']}",
        ]))

    # ---- reconcile ----
    rec_t0 = time.time()
    rec_step = {"step": "reconcile_neighborhood", "started_at": rec_t0, "ok": False}
    trace.append(rec_step)
    paragraph = ""
    audit = {"raw": "", "dropped": []}
    mellea_meta = None
    if docs and strict:
        rec_step["step"] = "mellea_reconcile_neighborhood"
        try:
            from app.framing import augment_system_prompt
            from app.mellea_validator import DEFAULT_LOOP_BUDGET, reconcile_strict_streaming
            from app.reconcile import trim_docs_to_plan as _trim
            docs = _trim(docs, set(plan.specialists or []))
            def _on_token(delta: str, attempt_idx: int):
                if progress_q is not None:
                    progress_q.put({"kind": "token", "delta": delta,
                                    "attempt": attempt_idx})
            def _on_attempt_end(attempt_idx, passed, failed):
                if progress_q is not None:
                    progress_q.put({"kind": "mellea_attempt",
                                    "attempt": attempt_idx,
                                    "passed": passed, "failed": failed})
            framed_prompt = augment_system_prompt(
                EXTRA_SYSTEM_PROMPT, query=query, intent=plan.intent,
            )
            mres = reconcile_strict_streaming(
                docs, framed_prompt,
                user_prompt="Write the cited briefing now.",
                model=OLLAMA_MODEL, loop_budget=DEFAULT_LOOP_BUDGET,
                on_token=_on_token if progress_q else None,
                on_attempt_end=_on_attempt_end if progress_q else None,
            )
            paragraph = mres["paragraph"]
            audit = {"raw": paragraph, "dropped": []}
            mellea_meta = {
                "rerolls": mres["rerolls"],
                "n_attempts": mres["n_attempts"],
                "requirements_passed": mres["requirements_passed"],
                "requirements_failed": mres["requirements_failed"],
                "requirements_total": mres["requirements_total"],
                "model": mres["model"], "loop_budget": mres["loop_budget"],
            }
            rec_step["ok"] = True
            rec_step["result"] = {
                "rerolls": mellea_meta["rerolls"],
                "passed": f"{len(mellea_meta['requirements_passed'])}/{mellea_meta['requirements_total']}",
                "paragraph_chars": len(paragraph),
            }
        except Exception as e:
            rec_step["err"] = str(e)
            log.exception("Mellea-validated reconcile failed")
    elif docs:
        def _on_token(delta: str):
            if progress_q is not None:
                progress_q.put({"kind": "token", "delta": delta})
        try:
            paragraph, audit = _reconcile(docs, on_token=_on_token if progress_q else None)
            rec_step["ok"] = True
            rec_step["result"] = {"paragraph_chars": len(paragraph),
                                  "dropped": len(audit["dropped"])}
        except Exception as e:
            rec_step["err"] = str(e)
            log.exception("neighborhood reconcile failed")
    else:
        paragraph = "No grounded data available for this neighborhood."
        rec_step["ok"] = True
        rec_step["result"] = {"paragraph_chars": len(paragraph)}
    rec_step["elapsed_s"] = round(time.time() - rec_t0, 2)
    _emit(rec_step)

    cite_list = citations_from_docs(docs)

    target_safe = {k: v for k, v in target.items() if k != "geometry"}
    target_safe["bbox"] = list(target["geometry"].bounds)  # [minx, miny, maxx, maxy]
    return {
        "intent":      "neighborhood",
        "query":       query,
        "plan": {
            "intent": plan.intent,
            "targets": plan.targets,
            "specialists": plan.specialists,
            "rationale": plan.rationale,
        },
        "target":      target_safe,
        "n_matches":   len(matches),
        "sandy_nta":   sandy_out,
        "dep_nta":     dep_out,
        "nyc311_nta":  nyc311_out,
        "microtopo_nta": micro_out,
        "prithvi_live": prithvi_live_out,
        "terramind": terramind_out,
        "rag":         rag_out,
        "paragraph":   paragraph,
        "audit":       audit,
        "mellea":      mellea_meta,
        "citations":   cite_list,
        "trace":       trace,
        "total_s":     round(time.time() - t0, 2),
    }


def _doc(doc_id: str, body_lines: list[str]) -> dict:
    return {"role": f"document {doc_id}", "content": "\n".join(body_lines)}


def _reconcile(docs: list[dict], on_token=None) -> tuple[str, dict]:
    from app.reconcile import verify_paragraph
    messages = docs + [
        {"role": "system", "content": EXTRA_SYSTEM_PROMPT},
        {"role": "user", "content": "Write the cited briefing now."},
    ]
    # num_ctx 4096 covers our actual prompt (system ~600 + 6 docs ~2000)
    # with margin; 8192 was over-allocating KV cache. num_predict caps the
    # briefing at ~400 tokens — enough for 4 sections, no runaway.
    OPTS = {"temperature": 0, "num_ctx": 4096, "num_predict": 600}
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


def _empty_result(plan, query: str, trace: list, error: str) -> dict:
    return {
        "intent":    "neighborhood",
        "query":     query,
        "error":     error,
        "plan": {
            "intent": plan.intent,
            "targets": plan.targets,
            "specialists": plan.specialists,
            "rationale": plan.rationale,
        },
        "trace":     trace,
        "citations": [],
        "paragraph": f"Could not resolve target to an NTA: {error}",
    }
