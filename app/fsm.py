"""HeliOS-NYC Burr FSM for address-query flood risk.

Linear pipeline; each action degrades gracefully (empty result -> no doc).
The reconciler (Granite 4.1) only sees documents from specialists that
actually produced data.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import geopandas as gpd
from burr.core import ApplicationBuilder, State, action
from shapely.geometry import Point

from app.context import floodnet, microtopo, nyc311
from app.energy import estimate as energy_estimate
from app.flood_layers import dep_stormwater, ida_hwm, prithvi_water, sandy_inundation
from app.geocode import geocode_one
from app.rag import retrieve as rag_retrieve
from app.reconcile import reconcile as run_reconcile

log = logging.getLogger("helios_nyc.fsm")


def _step(state: State, name: str) -> dict[str, Any]:
    """Append a step record to the trace; returns the dict so the action
    can mutate timing/result fields."""
    trace = list(state.get("trace", []))
    rec = {"step": name, "started_at": time.time(), "ok": None}
    trace.append(rec)
    return rec, trace


@action(reads=["query"], writes=["geocode", "lat", "lon", "trace"])
def step_geocode(state: State) -> State:
    rec, trace = _step(state, "geocode")
    try:
        hit = geocode_one(state["query"])
        if hit is None:
            rec["ok"] = False
            rec["err"] = "no geocoder match"
            # Burr requires every declared write to be populated. Emit
            # explicit None rather than leaving keys absent.
            return state.update(geocode=None, lat=None, lon=None, trace=trace)
        rec["ok"] = True
        rec["result"] = {"address": hit.address, "lat": hit.lat, "lon": hit.lon}
        return state.update(
            geocode={"address": hit.address, "borough": hit.borough,
                     "lat": hit.lat, "lon": hit.lon,
                     "bbl": hit.bbl, "bin": hit.bin},
            lat=hit.lat, lon=hit.lon, trace=trace,
        )
    except Exception as e:
        rec["ok"] = False
        rec["err"] = str(e)
        log.exception("geocode failed")
        return state.update(geocode=None, lat=None, lon=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["sandy", "trace"])
def step_sandy(state: State) -> State:
    rec, trace = _step(state, "sandy_inundation")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(trace=trace)
        pt = gpd.GeoDataFrame(geometry=[Point(state["lon"], state["lat"])], crs="EPSG:4326").to_crs("EPSG:2263")
        flag = bool(sandy_inundation.join(pt).iloc[0])
        rec["ok"] = True; rec["result"] = {"inside": flag}
        return state.update(sandy=flag, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("sandy failed")
        return state.update(trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["dep", "trace"])
def step_dep(state: State) -> State:
    rec, trace = _step(state, "dep_stormwater")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(trace=trace)
        pt = gpd.GeoDataFrame(geometry=[Point(state["lon"], state["lat"])], crs="EPSG:4326").to_crs("EPSG:2263")
        out: dict[str, Any] = {}
        for scen in ["dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current"]:
            j = dep_stormwater.join(pt, scen).iloc[0]
            out[scen] = {
                "depth_class": int(j["depth_class"]),
                "depth_label": j["depth_label"],
                "citation": f"NYC DEP Stormwater Flood Map — {dep_stormwater.label(scen)}",
            }
        rec["ok"] = True; rec["result"] = {k: v["depth_label"] for k, v in out.items()}
        return state.update(dep=out, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("dep failed")
        return state.update(trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["floodnet", "trace"])
def step_floodnet(state: State) -> State:
    rec, trace = _step(state, "floodnet")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(trace=trace)
        s = floodnet.summary_for_point(state["lat"], state["lon"], radius_m=600)
        s["radius_m"] = 600
        rec["ok"] = True
        rec["result"] = {"n_sensors": s["n_sensors"],
                         "n_events_3y": s["n_flood_events_3y"]}
        return state.update(floodnet=s, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("floodnet failed")
        return state.update(trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["nyc311", "trace"])
def step_311(state: State) -> State:
    rec, trace = _step(state, "nyc311")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(trace=trace)
        s = nyc311.summary_for_point(state["lat"], state["lon"], radius_m=200, years=5)
        rec["ok"] = True; rec["result"] = {"n": s["n"]}
        return state.update(nyc311=s, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("311 failed")
        return state.update(trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["ida_hwm", "trace"])
def step_ida_hwm(state: State) -> State:
    rec, trace = _step(state, "ida_hwm_2021")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(trace=trace)
        s = ida_hwm.summary_for_point(state["lat"], state["lon"], radius_m=800)
        if s is None:
            rec["ok"] = False; rec["err"] = "HWM data missing"
            return state.update(ida_hwm=None, trace=trace)
        rec["ok"] = True
        rec["result"] = {
            "n_within_800m": s.n_within_radius,
            "max_height_above_gnd_ft": s.max_height_above_gnd_ft,
            "nearest_m": s.nearest_dist_m,
        }
        return state.update(ida_hwm=vars(s), trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("ida_hwm failed")
        return state.update(ida_hwm=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["prithvi_water", "trace"])
def step_prithvi(state: State) -> State:
    rec, trace = _step(state, "prithvi_eo_v2")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(prithvi_water=None, trace=trace)
        s = prithvi_water.summary_for_point(state["lat"], state["lon"])
        if s is None:
            rec["ok"] = False; rec["err"] = "Prithvi mask missing"
            return state.update(prithvi_water=None, trace=trace)
        rec["ok"] = True
        rec["result"] = {
            "inside_water_polygon": s.inside_water_polygon,
            "nearest_distance_m": s.nearest_distance_m,
            "n_polygons_within_500m": s.n_polygons_within_500m,
        }
        return state.update(prithvi_water=vars(s), trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("prithvi failed")
        return state.update(prithvi_water=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["microtopo", "trace"])
def step_microtopo(state: State) -> State:
    rec, trace = _step(state, "microtopo_lidar")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(trace=trace)
        m = microtopo.microtopo_at(state["lat"], state["lon"])
        if m is None:
            rec["ok"] = False; rec["err"] = "DEM fetch failed"
            return state.update(microtopo=None, trace=trace)
        rec["ok"] = True
        rec["result"] = {
            "elev_m": m.point_elev_m,
            "pct_200m": m.rel_elev_pct_200m,
            "relief_m": m.basin_relief_m,
        }
        return state.update(microtopo=vars(m), trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("microtopo failed")
        return state.update(microtopo=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["geocode", "sandy", "dep", "floodnet", "nyc311", "microtopo", "ida_hwm", "prithvi_water"],
        writes=["rag", "trace"])
def step_rag(state: State) -> State:
    rec, trace = _step(state, "rag_granite_embedding")
    try:
        geo = state.get("geocode") or {}
        sandy = state.get("sandy")
        dep = state.get("dep") or {}
        # Build a context-rich query so retrieval pulls policy paragraphs
        # relevant to *this* address, not generic flood text.
        bits = []
        if geo.get("address"):
            bits.append(f"address {geo['address']}")
        if geo.get("borough"):
            bits.append(f"in {geo['borough']}")
        if sandy:
            bits.append("inside Hurricane Sandy 2012 inundation zone")
        for k, v in dep.items():
            if v.get("depth_class", 0) > 0:
                bits.append(f"in {v['depth_label']} pluvial scenario")
        bits.append("flood resilience plan, vulnerability, hardening, mitigation")
        q = "; ".join(bits)
        hits = rag_retrieve(q, k=3, min_score=0.45)
        rec["ok"] = True
        rec["result"] = {"hits": len(hits),
                         "top": [(h["doc_id"], round(h["score"], 2)) for h in hits]}
        return state.update(rag=hits, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("rag failed")
        return state.update(rag=[], trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["geocode", "sandy", "dep", "floodnet", "nyc311", "microtopo",
               "ida_hwm", "prithvi_water", "rag"],
        writes=["paragraph", "audit", "trace"])
def step_reconcile(state: State) -> State:
    rec, trace = _step(state, "reconcile_granite41")
    try:
        snap = {
            "geocode": state.get("geocode"),
            "sandy": state.get("sandy"),
            "dep": state.get("dep"),
            "floodnet": state.get("floodnet"),
            "nyc311": state.get("nyc311"),
            "microtopo": state.get("microtopo"),
            "ida_hwm": state.get("ida_hwm"),
            "prithvi_water": state.get("prithvi_water"),
            "rag": state.get("rag"),
        }
        para, audit = run_reconcile(snap, return_audit=True)
        rec["ok"] = True
        rec["result"] = {
            "paragraph_chars": len(para),
            "dropped_sentences": len(audit["dropped"]),
        }
        return state.update(paragraph=para, audit=audit, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("reconcile failed")
        return state.update(paragraph="", audit={"raw": "", "dropped": []}, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


def build_app(query: str):
    return (
        ApplicationBuilder()
        .with_actions(
            geocode=step_geocode,
            sandy=step_sandy,
            dep=step_dep,
            floodnet=step_floodnet,
            nyc311=step_311,
            microtopo=step_microtopo,
            ida_hwm=step_ida_hwm,
            prithvi=step_prithvi,
            rag=step_rag,
            reconcile=step_reconcile,
        )
        .with_transitions(
            ("geocode", "sandy"),
            ("sandy", "dep"),
            ("dep", "floodnet"),
            ("floodnet", "nyc311"),
            ("nyc311", "microtopo"),
            ("microtopo", "ida_hwm"),
            ("ida_hwm", "prithvi"),
            ("prithvi", "rag"),
            ("rag", "reconcile"),
        )
        .with_state(query=query, trace=[])
        .with_entrypoint("geocode")
        .build()
    )


def _summarize_energy(trace: list) -> dict | None:
    rec_step = next((t for t in trace if t.get("step") == "reconcile_granite41"
                     and t.get("ok")), None)
    if not rec_step:
        return None
    total_s = sum(t.get("elapsed_s", 0) or 0 for t in trace)
    return energy_estimate(rec_step.get("elapsed_s", 0) or 0, total_s)


def run(query: str) -> dict[str, Any]:
    app = build_app(query)
    final_action, _, final_state = app.run(halt_after=["reconcile"])
    trace = final_state.get("trace", [])
    return {
        "query": query,
        "geocode": final_state.get("geocode"),
        "sandy": final_state.get("sandy"),
        "dep": final_state.get("dep"),
        "floodnet": final_state.get("floodnet"),
        "nyc311": final_state.get("nyc311"),
        "microtopo": final_state.get("microtopo"),
        "ida_hwm": final_state.get("ida_hwm"),
        "prithvi_water": final_state.get("prithvi_water"),
        "rag": final_state.get("rag"),
        "paragraph": final_state.get("paragraph"),
        "audit": final_state.get("audit"),
        "energy": _summarize_energy(trace),
        "trace": trace,
    }


def iter_steps(query: str):
    """Yield (action_name, partial_state_dict) after each Burr action.

    Used by the web UI for SSE streaming — each yield is a "step lit up"
    moment. The final yield carries the reconciled paragraph.
    """
    app = build_app(query)
    last_trace_len = 0
    for action_obj, result, state in app.iterate(halt_after=["reconcile"]):
        trace = list(state.get("trace", []))
        # Yield only the new trace records since the prior step
        new_records = trace[last_trace_len:]
        last_trace_len = len(trace)
        for rec in new_records:
            yield {
                "kind": "step",
                "step": rec["step"],
                "ok": rec.get("ok"),
                "elapsed_s": rec.get("elapsed_s"),
                "result": rec.get("result"),
                "err": rec.get("err"),
            }
    # final
    trace = state.get("trace", [])
    yield {
        "kind": "final",
        "geocode": state.get("geocode"),
        "sandy": state.get("sandy"),
        "dep": state.get("dep"),
        "floodnet": state.get("floodnet"),
        "nyc311": state.get("nyc311"),
        "microtopo": state.get("microtopo"),
        "ida_hwm": state.get("ida_hwm"),
        "prithvi_water": state.get("prithvi_water"),
        "rag": state.get("rag"),
        "paragraph": state.get("paragraph"),
        "audit": state.get("audit"),
        "energy": _summarize_energy(trace),
    }
