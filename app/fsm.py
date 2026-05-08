"""Riprap Burr FSM — linear specialist pipeline for one address.

Each action either produces a structured fact (which becomes a document
the reconciler can cite) or stays silent on failure. The reconciler
(Granite 4.1) only sees documents from specialists that actually
produced data — the silence-over-confabulation contract.
"""
from __future__ import annotations

import logging
import threading as _threading
import time
from typing import Any

import geopandas as gpd
from burr.core import ApplicationBuilder, State, action
from shapely.geometry import Point

from app.context import floodnet, microtopo, noaa_tides, nws_alerts, nws_obs, nyc311
from app.energy import estimate as energy_estimate
from app.flood_layers import dep_stormwater, ida_hwm, prithvi_water, sandy_inundation
from app.geocode import geocode_one
from app.live import floodnet_forecast as fn_forecast
from app.live import ttm_forecast
from app.rag import retrieve as rag_retrieve
from app.reconcile import reconcile as run_reconcile
from app.registers import doe_schools as r_schools
from app.registers import doh_hospitals as r_hospitals
from app.registers import mta_entrances as r_mta
from app.registers import nycha as r_nycha

log = logging.getLogger("riprap.fsm")

# NYC five-borough bbox. Specialists whose data sources are NYC-only
# (Sandy 2012, NYC DEP Stormwater, FloodNet, NYC 311, NYC microtopo
# raster, NYC Hurricane Ida Prithvi polygons) skip with an explicit
# "out of NYC scope" reason when geocode lands outside this envelope.
# Live specialists (NWS / NOAA / TTM) and the NY-State Ida HWMs run
# unconditionally.
_NYC_S, _NYC_W, _NYC_N, _NYC_E = 40.49, -74.27, 40.92, -73.69


def _in_nyc(lat, lon) -> bool:
    if lat is None or lon is None:
        return False
    return _NYC_S <= lat <= _NYC_N and _NYC_W <= lon <= _NYC_E

# Thread-local hook so the streaming endpoint can subscribe to per-token
# Granite output during reconcile, without threading a callback through
# every Burr action signature.
_FSM_LOCAL = _threading.local()


def set_token_callback(on_token):
    """Install a per-thread on_token(delta) callable for the next reconcile.
    Pass None to clear."""
    _FSM_LOCAL.on_token = on_token


def _current_token_callback():
    return getattr(_FSM_LOCAL, "on_token", None)


def set_mellea_attempt_callback(fn):
    _FSM_LOCAL.on_mellea_attempt = fn


def _current_mellea_attempt_callback():
    return getattr(_FSM_LOCAL, "on_mellea_attempt", None)


def set_strict_mode(strict: bool):
    """Per-thread flag — when True the linear FSM's reconcile step routes
    through Mellea-validated rejection sampling instead of the standard
    streaming reconciler. Disables token streaming for that step."""
    _FSM_LOCAL.strict = bool(strict)


def _current_strict_mode() -> bool:
    return bool(getattr(_FSM_LOCAL, "strict", False))


def set_planned_specialists(spec_names):
    """Install a per-thread set of specialist names from the planner.

    Used by step_reconcile to trim doc messages: documents whose family
    prefix doesn't match any planned specialist are dropped before the
    Mellea call. Cuts ~30-50% of prompt tokens on local Ollama, where
    the FSM otherwise hands the reconciler every specialist's output
    even if the planner only asked for a subset."""
    _FSM_LOCAL.planned_specialists = set(spec_names) if spec_names else None


def _current_planned_specialists():
    return getattr(_FSM_LOCAL, "planned_specialists", None)


def set_user_query(query: str | None):
    """Install the user's original natural-language query for question-aware
    framing in step_reconcile. The FSM's state["query"] is the geocoder
    input (often just the street address), which doesn't carry the
    user's question shape — set this separately so Capstone can detect
    'should I worry' / 'is disclosure required' / etc."""
    _FSM_LOCAL.user_query = query


def _current_user_query() -> str | None:
    return getattr(_FSM_LOCAL, "user_query", None)


def set_planner_intent(intent: str | None):
    """Install the planner's classified intent so step_reconcile can pass
    it to the framing detector as a tiebreaker on bare-place queries."""
    _FSM_LOCAL.planner_intent = intent


def _current_planner_intent() -> str | None:
    return getattr(_FSM_LOCAL, "planner_intent", None)


# Canonical Burr: one action per specialist, sequential transitions.
# A previous version of this module wrapped 16 specialists in a single
# fan-out action that ran them concurrently in a ThreadPoolExecutor;
# that path was removed because it sometimes hung after the fan-out
# completed (Burr-internal post-action cleanup with custom executors)
# and made the trace UI's per-step timing harder to reason about.
# Parallelism, when wanted, belongs at the inference layer
# (vLLM / Ollama NUM_PARALLEL), not the FSM.

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
            return state.update(sandy=None, trace=trace)
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(sandy=None, trace=trace)
        pt_geom = (gpd.GeoDataFrame(geometry=[Point(state["lon"], state["lat"])],
                                    crs="EPSG:4326")
                   .to_crs("EPSG:2263").iloc[0].geometry)
        flag = sandy_inundation.inside_raster(pt_geom)
        rec["ok"] = True; rec["result"] = {"inside": flag}
        return state.update(sandy=flag, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("sandy failed")
        return state.update(sandy=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["dep", "trace"])
def step_dep(state: State) -> State:
    rec, trace = _step(state, "dep_stormwater")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(dep=None, trace=trace)
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(dep=None, trace=trace)
        pt_geom = (gpd.GeoDataFrame(geometry=[Point(state["lon"], state["lat"])],
                                    crs="EPSG:4326")
                   .to_crs("EPSG:2263").iloc[0].geometry)
        out: dict[str, Any] = {}
        for scen in ["dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current"]:
            cls = dep_stormwater.join_raster(pt_geom, scen)
            out[scen] = {
                "depth_class": cls,
                "depth_label": dep_stormwater.DEPTH_CLASS.get(cls, "outside"),
                "citation": f"NYC DEP Stormwater Flood Map — {dep_stormwater.label(scen)}",
            }
        rec["ok"] = True; rec["result"] = {k: v["depth_label"] for k, v in out.items()}
        return state.update(dep=out, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("dep failed")
        return state.update(dep=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["floodnet", "trace"])
def step_floodnet(state: State) -> State:
    rec, trace = _step(state, "floodnet")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(floodnet=None, trace=trace)
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(floodnet=None, trace=trace)
        s = floodnet.summary_for_point(state["lat"], state["lon"], radius_m=600)
        s["radius_m"] = 600
        rec["ok"] = True
        rec["result"] = {"n_sensors": s["n_sensors"],
                         "n_events_3y": s["n_flood_events_3y"]}
        return state.update(floodnet=s, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("floodnet failed")
        return state.update(floodnet=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["nyc311", "trace"])
def step_311(state: State) -> State:
    rec, trace = _step(state, "nyc311")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(nyc311=None, trace=trace)
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(nyc311=None, trace=trace)
        s = nyc311.summary_for_point(state["lat"], state["lon"], radius_m=200, years=5)
        rec["ok"] = True; rec["result"] = {"n": s["n"]}
        return state.update(nyc311=s, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("311 failed")
        return state.update(nyc311=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["ida_hwm", "trace"])
def step_ida_hwm(state: State) -> State:
    rec, trace = _step(state, "ida_hwm_2021")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(ida_hwm=None, trace=trace)
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
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
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


@action(reads=["lat", "lon"], writes=["prithvi_live", "trace"])
def step_prithvi_live(state: State) -> State:
    """Live Sentinel-2 water segmentation via Prithvi-EO 2.0.

    Network + 300M-param forward pass per query, so it's the slowest
    specialist by far. Gracefully no-ops via the underlying module if
    `RIPRAP_PRITHVI_LIVE_ENABLE=0` or if STAC / model load fails.
    """
    rec, trace = _step(state, "prithvi_eo_live")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(prithvi_live=None, trace=trace)
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(prithvi_live=None, trace=trace)
        from app.flood_layers import prithvi_live
        s = prithvi_live.fetch(state["lat"], state["lon"])
        rec["ok"] = bool(s.get("ok"))
        if not s.get("ok"):
            rec["err"] = s.get("err") or s.get("skipped") or "no observation"
        else:
            rec["result"] = {
                "scene_date": (s.get("item_datetime") or "")[:10],
                "cloud_cover": s.get("cloud_cover"),
                "pct_water_500m": s.get("pct_water_within_500m"),
                "pct_water_5km": s.get("pct_water_full"),
            }
        return state.update(prithvi_live=s, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("prithvi_live failed")
        return state.update(prithvi_live=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["ttm_311_forecast", "trace"])
def step_ttm_311_forecast(state: State) -> State:
    """TTM r2 zero-shot forecast on weekly 311 flood-complaint counts
    at this specific address (200 m radius). 52 weeks of context →
    4 weeks of forecast. Per-query, per-address, citable."""
    rec, trace = _step(state, "ttm_311_forecast")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(ttm_311_forecast=None, trace=trace)
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(ttm_311_forecast=None, trace=trace)
        s = ttm_forecast.weekly_311_forecast_for_point(state["lat"], state["lon"])
        rec["ok"] = bool(s.get("available"))
        if not rec["ok"]:
            rec["err"] = s.get("reason", "unavailable")
        else:
            rec["result"] = {
                "history_total": s.get("history_total_complaints"),
                "history_recent_mean": s.get("history_recent_3mo_mean"),
                "forecast_mean": s.get("forecast_mean_per_week"),
                "forecast_peak": s.get("forecast_peak_per_week"),
                "accelerating": s.get("accelerating"),
            }
        return state.update(ttm_311_forecast=s, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("ttm_311_forecast failed")
        return state.update(ttm_311_forecast=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["terramind", "trace"])
def step_terramind(state: State) -> State:
    """TerraMind v1 base — DEM → S2L2A synthesis as a per-query
    cognitive-engine node. ~3-7s on M3 CPU. Output is a
    *synthetic-prior* — explicitly fourth epistemic class alongside
    empirical / modeled / proxy. Frame the doc body and reconciler
    narration as 'plausible synthesis from terrain context', never
    'imaged' or 'reconstructed'."""
    rec, trace = _step(state, "terramind_synthesis")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(terramind=None, trace=trace)
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(terramind=None, trace=trace)
        from app.context import terramind_synthesis
        s = terramind_synthesis.fetch(state["lat"], state["lon"])
        rec["ok"] = bool(s.get("ok"))
        if not s.get("ok"):
            rec["err"] = s.get("err") or s.get("skipped") or "terramind unavailable"
        else:
            rec["result"] = {
                "tim_chain": s.get("tim_chain"),
                "diffusion_steps": s.get("diffusion_steps"),
                "dem_mean_m": s.get("dem_mean_m"),
                "synth_chip_shape": s.get("synth_chip_shape"),
                "elapsed_s": s.get("elapsed_s"),
            }
        return state.update(terramind=s, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("terramind failed")
        return state.update(terramind=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["noaa_tides", "trace"])
def step_noaa_tides(state: State) -> State:
    rec, trace = _step(state, "noaa_tides")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(noaa_tides=None, trace=trace)
        s = noaa_tides.summary_for_point(state["lat"], state["lon"])
        rec["ok"] = s.get("error") is None
        rec["result"] = {
            "station": s["station_id"],
            "observed_ft_mllw": s["observed_ft_mllw"],
            "residual_ft": s["residual_ft"],
        }
        if s.get("error"): rec["err"] = s["error"]
        return state.update(noaa_tides=s, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("noaa_tides failed")
        return state.update(noaa_tides=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["nws_alerts", "trace"])
def step_nws_alerts(state: State) -> State:
    rec, trace = _step(state, "nws_alerts")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(nws_alerts=None, trace=trace)
        s = nws_alerts.summary_for_point(state["lat"], state["lon"])
        rec["ok"] = s.get("error") is None
        rec["result"] = {"n_active": s["n_active"]}
        if s.get("error"): rec["err"] = s["error"]
        return state.update(nws_alerts=s, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("nws_alerts failed")
        return state.update(nws_alerts=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["nws_obs", "trace"])
def step_nws_obs(state: State) -> State:
    rec, trace = _step(state, "nws_obs")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(nws_obs=None, trace=trace)
        s = nws_obs.summary_for_point(state["lat"], state["lon"])
        rec["ok"] = s.get("error") is None
        rec["result"] = {
            "station": s["station_id"],
            "p1h_mm": s["precip_last_hour_mm"],
            "p6h_mm": s["precip_last_6h_mm"],
        }
        if s.get("error"): rec["err"] = s["error"]
        return state.update(nws_obs=s, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("nws_obs failed")
        return state.update(nws_obs=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["ttm_forecast", "trace"])
def step_ttm_forecast(state: State) -> State:
    """Granite TTM r2 zero-shot forecast of the Battery surge residual."""
    rec, trace = _step(state, "ttm_forecast")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(ttm_forecast=None, trace=trace)
        s = ttm_forecast.summary_for_point(state["lat"], state["lon"])
        if not s.get("available"):
            rec["ok"] = False
            rec["err"] = s.get("reason", "TTM unavailable")
            return state.update(ttm_forecast=None, trace=trace)
        rec["ok"] = True
        rec["result"] = {
            "context": s["context_length"],
            "horizon": s["horizon_steps"],
            "forecast_peak_ft": s["forecast_peak_ft"],
            "forecast_peak_min_ahead": s["forecast_peak_minutes_ahead"],
            "interesting": s["interesting"],
        }
        return state.update(ttm_forecast=s, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("ttm_forecast failed")
        return state.update(ttm_forecast=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["ttm_battery_surge", "trace"])
def step_ttm_battery_surge(state: State) -> State:
    """Granite TTM r2 fine-tune — 96 h hourly Battery surge nowcast.

    Same TTM r2 backbone family as step_ttm_forecast but a different
    artefact: msradam/Granite-TTM-r2-Battery-Surge, trained on AMD
    MI300X. Hourly cadence vs the zero-shot's 6-min, 4-day vs 9.6 h
    horizon. Both can fire on the same query — the reconciler frames
    each as a distinct forecast in the briefing."""
    rec, trace = _step(state, "ttm_battery_surge")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(ttm_battery_surge=None, trace=trace)
        # Battery gauge is a single point; the forecast applies citywide
        # to NYC harbor entrance, so we don't gate by NYC bbox.
        from app.live import ttm_battery_surge
        s = ttm_battery_surge.fetch()
        rec["ok"] = bool(s.get("available"))
        if not rec["ok"]:
            rec["err"] = s.get("reason", "unavailable")
            return state.update(ttm_battery_surge=None, trace=trace)
        rec["result"] = {
            "context_h": s.get("context_hours"),
            "horizon_h": s.get("horizon_hours"),
            "forecast_peak_m": s.get("forecast_peak_m"),
            "forecast_peak_hours_ahead": s.get("forecast_peak_hours_ahead"),
            "interesting": s.get("interesting"),
        }
        return state.update(ttm_battery_surge=s, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("ttm_battery_surge failed")
        return state.update(ttm_battery_surge=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["floodnet_forecast", "trace"])
def step_floodnet_forecast(state: State) -> State:
    """TTM r2 forecast of flood-event recurrence at the nearest FloodNet
    sensor. Reuses the same (512, 96) singleton as ttm_311_forecast — no
    additional model loaded into memory. Silent when the sensor has too
    few historical events for a defensible forecast."""
    rec, trace = _step(state, "floodnet_forecast")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(floodnet_forecast=None, trace=trace)
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(floodnet_forecast=None, trace=trace)
        s = fn_forecast.summary_for_point(state["lat"], state["lon"])
        rec["ok"] = bool(s.get("available"))
        if not rec["ok"]:
            rec["err"] = s.get("reason", "unavailable")
        else:
            rec["result"] = {
                "sensor_id": s.get("sensor_id"),
                "distance_m": s.get("distance_from_query_m"),
                "history_28d": s.get("history_recent_28d_events"),
                "forecast_28d": s.get("forecast_28d_expected_events"),
                "accelerating": s.get("accelerating"),
            }
        return state.update(floodnet_forecast=s if rec["ok"] else None,
                            trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("floodnet_forecast failed")
        return state.update(floodnet_forecast=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["mta_entrances", "trace"])
def step_mta_entrances(state: State) -> State:
    rec, trace = _step(state, "mta_entrance_exposure")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(mta_entrances=None, trace=trace)
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(mta_entrances=None, trace=trace)
        s = r_mta.summary_for_point(state["lat"], state["lon"])
        if not s.get("available"):
            rec["ok"] = False; rec["err"] = "no entrances within radius"
            return state.update(mta_entrances=None, trace=trace)
        rec["ok"] = True
        rec["result"] = {
            "n_entrances": s["n_entrances"],
            "n_inside_sandy_2012": s["n_inside_sandy_2012"],
            "n_in_dep_extreme_2080": s["n_in_dep_extreme_2080"],
        }
        return state.update(mta_entrances=s, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("mta_entrances failed")
        return state.update(mta_entrances=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["nycha_developments", "trace"])
def step_nycha(state: State) -> State:
    rec, trace = _step(state, "nycha_development_exposure")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(nycha_developments=None, trace=trace)
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(nycha_developments=None, trace=trace)
        s = r_nycha.summary_for_point(state["lat"], state["lon"])
        if not s.get("available"):
            rec["ok"] = False; rec["err"] = "no NYCHA developments within radius"
            return state.update(nycha_developments=None, trace=trace)
        rec["ok"] = True
        rec["result"] = {
            "n_developments": s["n_developments"],
            "n_inside_sandy_2012": s["n_inside_sandy_2012"],
            "n_in_dep_extreme_2080": s["n_in_dep_extreme_2080"],
        }
        return state.update(nycha_developments=s, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("nycha failed")
        return state.update(nycha_developments=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["doe_schools", "trace"])
def step_doe_schools(state: State) -> State:
    rec, trace = _step(state, "doe_school_exposure")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(doe_schools=None, trace=trace)
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(doe_schools=None, trace=trace)
        s = r_schools.summary_for_point(state["lat"], state["lon"])
        if not s.get("available"):
            rec["ok"] = False; rec["err"] = "no schools within radius"
            return state.update(doe_schools=None, trace=trace)
        rec["ok"] = True
        rec["result"] = {
            "n_schools": s["n_schools"],
            "n_inside_sandy_2012": s["n_inside_sandy_2012"],
            "n_in_dep_extreme_2080": s["n_in_dep_extreme_2080"],
        }
        return state.update(doe_schools=s, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("doe_schools failed")
        return state.update(doe_schools=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["doh_hospitals", "trace"])
def step_doh_hospitals(state: State) -> State:
    rec, trace = _step(state, "doh_hospital_exposure")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(doh_hospitals=None, trace=trace)
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(doh_hospitals=None, trace=trace)
        s = r_hospitals.summary_for_point(state["lat"], state["lon"])
        if not s.get("available"):
            rec["ok"] = False; rec["err"] = "no hospitals within radius"
            return state.update(doh_hospitals=None, trace=trace)
        rec["ok"] = True
        rec["result"] = {
            "n_hospitals": s["n_hospitals"],
            "n_inside_sandy_2012": s["n_inside_sandy_2012"],
            "n_in_dep_extreme_2080": s["n_in_dep_extreme_2080"],
        }
        return state.update(doh_hospitals=s, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("doh_hospitals failed")
        return state.update(doh_hospitals=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["microtopo", "trace"])
def step_microtopo(state: State) -> State:
    rec, trace = _step(state, "microtopo_lidar")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(microtopo=None, trace=trace)
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(microtopo=None, trace=trace)
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




@action(reads=["lat", "lon"], writes=["eo_chip", "trace"])
def step_eo_chip(state: State) -> State:
    """Fetch one S2L2A + S1RTC + DEM chip per query and stash it in
    state for the TerraMind-NYC specialists.

    Centralised so step_terramind_lulc and step_terramind_buildings
    don't each re-fetch ~150 MB of imagery. Best-effort by design —
    a deps-missing or no-scene outcome writes `{ok: False, skipped: ...}`
    and the downstream TerraMind specialists silently no-op."""
    rec, trace = _step(state, "eo_chip_fetch")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(eo_chip=None, trace=trace)
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(eo_chip=None, trace=trace)
        from app.context import eo_chip_cache
        chip = eo_chip_cache.fetch(state["lat"], state["lon"])
        rec["ok"] = bool(chip.get("ok"))
        if not rec["ok"]:
            rec["err"] = chip.get("skipped") or chip.get("err") or "unavailable"
        else:
            rec["result"] = {
                "scene_id": (chip.get("s2_meta") or {}).get("scene_id"),
                "scene_date": ((chip.get("s2_meta") or {}).get("datetime") or "")[:10],
                "cloud_cover": (chip.get("s2_meta") or {}).get("cloud_cover"),
                "has_s1": chip.get("s1") is not None,
                "has_dem": chip.get("dem") is not None,
            }
        return state.update(eo_chip=chip, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("eo_chip failed")
        return state.update(eo_chip=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon", "eo_chip"], writes=["terramind_lulc", "trace"])
def step_terramind_lulc(state: State) -> State:
    """5-class macro NYC LULC via msradam/TerraMind-NYC-Adapters.

    Consumes the shared chip from step_eo_chip; if that didn't fire
    cleanly this no-ops. Adapter loading (~1.6 GB base + ~325 MB LoRA)
    is lazy on first call and cached across queries."""
    rec, trace = _step(state, "terramind_lulc")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(terramind_lulc=None, trace=trace)
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(terramind_lulc=None, trace=trace)
        chip = state.get("eo_chip") or {}
        if not chip.get("ok"):
            rec["ok"] = False
            rec["err"] = chip.get("skipped") or chip.get("err") or "no chip"
            return state.update(terramind_lulc=None, trace=trace)
        from app.context import terramind_nyc
        tensors = chip.get("tensors") or {}
        out = terramind_nyc.lulc(
            tensors.get("S2L2A"),
            s1rtc=tensors.get("S1RTC"),
            dem=tensors.get("DEM"),
            bounds_4326=chip.get("bounds_4326"),
        )
        rec["ok"] = bool(out.get("ok"))
        if not rec["ok"]:
            rec["err"] = out.get("skipped") or out.get("err") or "unavailable"
        else:
            rec["result"] = {
                "dominant_class": out.get("dominant_class"),
                "dominant_pct": out.get("dominant_pct"),
                "n_classes_observed": len(out.get("class_fractions") or {}),
            }
        return state.update(terramind_lulc=out, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("terramind_lulc failed")
        return state.update(terramind_lulc=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon", "eo_chip"],
        writes=["terramind_buildings", "trace"])
def step_terramind_buildings(state: State) -> State:
    """Binary NYC building-footprint mask via msradam/TerraMind-NYC-Adapters."""
    rec, trace = _step(state, "terramind_buildings")
    try:
        if state.get("lat") is None:
            rec["ok"] = False; rec["err"] = "no coords"
            return state.update(terramind_buildings=None, trace=trace)
        if not _in_nyc(state["lat"], state["lon"]):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(terramind_buildings=None, trace=trace)
        chip = state.get("eo_chip") or {}
        if not chip.get("ok"):
            rec["ok"] = False
            rec["err"] = chip.get("skipped") or chip.get("err") or "no chip"
            return state.update(terramind_buildings=None, trace=trace)
        from app.context import terramind_nyc
        tensors = chip.get("tensors") or {}
        out = terramind_nyc.buildings(
            tensors.get("S2L2A"),
            s1rtc=tensors.get("S1RTC"),
            dem=tensors.get("DEM"),
            bounds_4326=chip.get("bounds_4326"),
        )
        rec["ok"] = bool(out.get("ok"))
        if not rec["ok"]:
            rec["err"] = out.get("skipped") or out.get("err") or "unavailable"
        else:
            rec["result"] = {
                "pct_buildings": out.get("pct_buildings"),
                "n_building_components": out.get("n_building_components"),
            }
        return state.update(terramind_buildings=out, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("terramind_buildings failed")
        return state.update(terramind_buildings=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["geocode", "sandy", "dep", "floodnet", "nyc311", "microtopo",
               "ida_hwm", "prithvi_water", "noaa_tides", "nws_alerts", "nws_obs",
               "ttm_forecast"],
        writes=["rag", "trace"])
def step_rag(state: State) -> State:
    rec, trace = _step(state, "rag_granite_embedding")
    try:
        geo = state.get("geocode") or {}
        if not _in_nyc(geo.get("lat"), geo.get("lon")):
            rec["ok"] = False; rec["err"] = "out of NYC scope"
            return state.update(rag=[], trace=trace)
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
        for v in dep.values():
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


@action(reads=["rag"], writes=["gliner", "trace"])
def step_gliner(state: State) -> State:
    """GLiNER typed-entity extraction over the top RAG paragraphs.

    Adds structured fields (`agency`, `dollar_amount`,
    `infrastructure_project`, `nyc_location`, `date_range`) the
    reconciler can cite with `[gliner_<source>]`. Silent no-op when
    disabled via RIPRAP_GLINER_ENABLE=0 or when the model failed to
    load — preserves the existing FSM contract.
    """
    rec, trace = _step(state, "gliner_extract")
    try:
        from app.context.gliner_extract import extract_for_rag_hits
        hits = state.get("rag") or []
        if not hits:
            rec["ok"] = True
            rec["result"] = {"sources": 0, "skipped": "no rag hits"}
            return state.update(gliner={}, trace=trace)
        out = extract_for_rag_hits(hits)
        rec["ok"] = True
        rec["result"] = {
            "sources": len(out),
            "totals_by_label": _label_counts(out),
        }
        return state.update(gliner=out, trace=trace)
    except Exception as e:
        rec["ok"] = False
        rec["err"] = str(e)
        log.exception("gliner failed")
        return state.update(gliner={}, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


def _label_counts(gliner_out: dict[str, dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for src in gliner_out.values():
        for e in src.get("entities", []):
            counts[e["label"]] = counts.get(e["label"], 0) + 1
    return counts


@action(reads=["geocode", "sandy", "dep", "floodnet", "nyc311", "microtopo",
               "ida_hwm", "prithvi_water", "prithvi_live", "terramind",
               "terramind_lulc", "terramind_buildings",
               "noaa_tides", "nws_alerts", "nws_obs", "ttm_forecast",
               "ttm_311_forecast", "floodnet_forecast", "ttm_battery_surge",
               "mta_entrances",
               "nycha_developments", "doe_schools", "doh_hospitals",
               "rag", "gliner"],
        writes=["paragraph", "audit", "mellea", "trace"])
def step_reconcile(state: State) -> State:
    is_strict = _current_strict_mode()
    rec, trace = _step(state, "mellea_reconcile_address" if is_strict else "reconcile_granite41")
    mellea_meta = None
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
            "noaa_tides": state.get("noaa_tides"),
            "nws_alerts": state.get("nws_alerts"),
            "nws_obs": state.get("nws_obs"),
            "ttm_forecast": state.get("ttm_forecast"),
            "ttm_311_forecast": state.get("ttm_311_forecast"),
            "floodnet_forecast": state.get("floodnet_forecast"),
            "ttm_battery_surge": state.get("ttm_battery_surge"),
            "rag": state.get("rag"),
            "gliner": state.get("gliner"),
            "prithvi_live": state.get("prithvi_live"),
            "terramind": state.get("terramind"),
            "terramind_lulc": state.get("terramind_lulc"),
            "terramind_buildings": state.get("terramind_buildings"),
            "mta_entrances": state.get("mta_entrances"),
            "nycha_developments": state.get("nycha_developments"),
            "doe_schools": state.get("doe_schools"),
            "doh_hospitals": state.get("doh_hospitals"),
        }
        if is_strict:
            from app.framing import augment_system_prompt
            from app.mellea_validator import DEFAULT_LOOP_BUDGET, reconcile_strict_streaming
            from app.reconcile import EXTRA_SYSTEM_PROMPT, build_documents, trim_docs_to_plan
            doc_msgs = build_documents(snap)
            doc_msgs = trim_docs_to_plan(doc_msgs, _current_planned_specialists())
            if not doc_msgs:
                para = "No grounded data available for this address."
                audit = {"raw": para, "dropped": []}
            else:
                token_cb = _current_token_callback()
                attempt_cb = _current_mellea_attempt_callback()
                framed_prompt = augment_system_prompt(
                    EXTRA_SYSTEM_PROMPT,
                    query=_current_user_query() or state.get("query") or "",
                    intent=_current_planner_intent() or "single_address",
                )
                mres = reconcile_strict_streaming(
                    doc_msgs, framed_prompt,
                    user_prompt="Write the cited paragraph now.",
                    loop_budget=DEFAULT_LOOP_BUDGET,
                    on_token=(lambda d, _ai: token_cb(d)) if token_cb else None,
                    on_attempt_end=attempt_cb,
                )
                para = mres["paragraph"]
                audit = {"raw": para, "dropped": []}
                mellea_meta = {
                    "rerolls": mres["rerolls"],
                    "n_attempts": mres["n_attempts"],
                    "requirements_passed": mres["requirements_passed"],
                    "requirements_failed": mres["requirements_failed"],
                    "requirements_total": mres["requirements_total"],
                    "model": mres["model"],
                    "loop_budget": mres["loop_budget"],
                }
            rec["result"] = {
                "rerolls": (mellea_meta or {}).get("rerolls"),
                "passed": (f"{len((mellea_meta or {}).get('requirements_passed') or [])}/"
                           f"{(mellea_meta or {}).get('requirements_total') or 0}"),
                "paragraph_chars": len(para),
            }
        else:
            para, audit = run_reconcile(snap, return_audit=True,
                                        on_token=_current_token_callback())
            rec["result"] = {
                "paragraph_chars": len(para),
                "dropped_sentences": len(audit["dropped"]),
            }
        rec["ok"] = True
        return state.update(paragraph=para, audit=audit,
                            mellea=mellea_meta, trace=trace)
    except Exception as e:
        rec["ok"] = False; rec["err"] = str(e)
        log.exception("reconcile failed")
        return state.update(paragraph="", audit={"raw": "", "dropped": []},
                            mellea=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


import os as _os  # noqa: E402


# Specialists that involve large spatial joins (every NYCHA development
# overlapped against multiple flood layers, every DOE school footprint
# joined to DEM/HAND, etc.) or per-query model inference (Prithvi-EO live
# STAC + ViT, TerraMind diffusion). They're ~1-3 minutes apiece on a
# laptop on the FIRST call (the lru_caches inside the registers warm up
# afterwards). The previous parallel-fan-out FSM hid that cost behind
# the longest single specialist; the linear FSM exposes it.
#
# Default OFF on local-Ollama so the demo briefing returns in well under
# 90 s. Enable explicitly with RIPRAP_HEAVY_SPECIALISTS=1 (e.g. on the
# AMD-vLLM path, where the reconciler's ~5 s leaves room for the joins).
#
# Remote ML lift: when RIPRAP_ML_BACKEND=remote (or auto with a base URL
# set) the heavy specialists' GPU work runs on the droplet, so the local
# wall-clock cost drops from ~60 s to ~5 s. Default ON in that case so
# the public demo never silently disables them.
def _remote_ml_configured() -> bool:
    backend = _os.environ.get("RIPRAP_ML_BACKEND", "auto").lower()
    if backend == "local":
        return False
    return bool(_os.environ.get("RIPRAP_ML_BASE_URL", "").strip())


_HEAVY_DEFAULT = (
    "1" if (
        _os.environ.get("RIPRAP_LLM_PRIMARY", "ollama").lower() != "ollama"
        or _remote_ml_configured()
    ) else "0"
)
_HEAVY_SPECIALISTS_ENABLED = _os.environ.get(
    "RIPRAP_HEAVY_SPECIALISTS", _HEAVY_DEFAULT,
).lower() in ("1", "true", "yes")

# NYCHA / DOE / DOH registers load a 91 MB sandy_inundation.geojson via
# geopandas on first call.  On machines with slow I/O or single-threaded
# Python GIL contention (M3 local dev) this takes 3–5 min and makes the
# first single_address query appear hung.  Disable by default; enable on
# the AMD droplet where the server pre-warms these at startup.
_NYCHA_REGISTERS_ENABLED = _os.environ.get(
    "RIPRAP_NYCHA_REGISTERS", "0",
).lower() in ("1", "true", "yes")


def build_app(query: str):
    """Linear, single-action-per-step Burr application.

    Order: cheap-first geo + flood layers, then live live network signals,
    then RAG → reconcile. Heavy specialists (NYCHA / DOE / DOH register
    joins, Prithvi-EO live STAC, TerraMind diffusion) are gated behind
    RIPRAP_HEAVY_SPECIALISTS — see the module-level note above.
    """
    builder = (
        ApplicationBuilder()
        .with_state(query=query, trace=[])
        .with_entrypoint("geocode")
    )

    actions: dict[str, Any] = {
        "geocode": step_geocode,
        "sandy": step_sandy,
        "dep": step_dep,
        "floodnet": step_floodnet,
        "nyc311": step_311,
        "noaa_tides": step_noaa_tides,
        "nws_alerts": step_nws_alerts,
        "nws_obs": step_nws_obs,
        "ttm_forecast": step_ttm_forecast,
        "ttm_311_forecast": step_ttm_311_forecast,
        "floodnet_forecast": step_floodnet_forecast,
        "ttm_battery_surge": step_ttm_battery_surge,
        "microtopo": step_microtopo,
        "ida_hwm": step_ida_hwm,
        "mta_entrances": step_mta_entrances,
        "prithvi": step_prithvi,  # baked GeoJSON polygons for Ida; cheap
    }
    if _HEAVY_SPECIALISTS_ENABLED and _NYCHA_REGISTERS_ENABLED:
        actions["nycha"] = step_nycha
        actions["doe_schools"] = step_doe_schools
        actions["doh_hospitals"] = step_doh_hospitals
    if _HEAVY_SPECIALISTS_ENABLED:
        actions["prithvi_live"] = step_prithvi_live
        actions["terramind"] = step_terramind
        # New TerraMind-NYC LoRA family — one chip fetch feeds two
        # specialists. Keep eo_chip directly before the two consumers
        # so the chip stays warm in memory and isn't garbage-collected
        # by anything in between.
        actions["eo_chip"] = step_eo_chip
        actions["terramind_lulc"] = step_terramind_lulc
        actions["terramind_buildings"] = step_terramind_buildings
    actions["rag"] = step_rag
    actions["gliner"] = step_gliner
    actions["reconcile"] = step_reconcile

    # Sequential transitions — pair every adjacent action in the dict order.
    keys = list(actions.keys())
    transitions = list(zip(keys, keys[1:]))

    return (
        builder.with_actions(**actions).with_transitions(*transitions).build()
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
        "terramind": final_state.get("terramind"),
        "terramind_lulc": final_state.get("terramind_lulc"),
        "terramind_buildings": final_state.get("terramind_buildings"),
        "eo_chip": final_state.get("eo_chip"),
        "noaa_tides": final_state.get("noaa_tides"),
        "nws_alerts": final_state.get("nws_alerts"),
        "nws_obs": final_state.get("nws_obs"),
        "ttm_forecast": final_state.get("ttm_forecast"),
        "ttm_311_forecast": final_state.get("ttm_311_forecast"),
        "floodnet_forecast": final_state.get("floodnet_forecast"),
        "ttm_battery_surge": final_state.get("ttm_battery_surge"),
        "mta_entrances": final_state.get("mta_entrances"),
        "nycha_developments": final_state.get("nycha_developments"),
        "doe_schools": final_state.get("doe_schools"),
        "doh_hospitals": final_state.get("doh_hospitals"),
        "rag": final_state.get("rag"),
        "paragraph": final_state.get("paragraph"),
        "audit": final_state.get("audit"),
        "mellea": final_state.get("mellea"),
        "energy": _summarize_energy(trace),
        "trace": trace,
    }


def iter_steps(query: str):
    """Yield SSE-friendly events as the FSM runs.

    Each Burr action emits exactly one trace record on completion; we
    yield it as a `step` event the moment the iterate loop returns from
    that action. Reconciler tokens stream through the threadlocal
    `set_token_callback` (installed before this generator is iterated),
    not through this queue.

    Burr's `app.iterate(halt_after=["reconcile"])` runs synchronously,
    yielding `(action, result, state)` after every action. We drive it
    in a background thread so the per-action SSE events reach the
    client as soon as each action returns, while the reconciler's
    token callback fires concurrently from the same thread.
    """
    import queue

    q: queue.Queue[tuple[str, Any] | None] = queue.Queue()
    seen_keys: set[tuple[str, float]] = set()

    def _push_step(rec: dict) -> None:
        key = (rec.get("step", ""), rec.get("started_at", 0.0))
        if key in seen_keys:
            return
        seen_keys.add(key)
        q.put(("step", rec))

    app = build_app(query)
    final_state_holder: dict[str, Any] = {}

    # Threadlocals are per-thread; the request thread (single_address.run
    # / neighborhood.run) sets the strict-mode flag, planner specialist
    # set, and token / Mellea-attempt callbacks, but Burr's app.iterate
    # runs in this generator's thread. Snapshot the request-thread state
    # and re-install on the iterate thread so step_reconcile sees them.
    _captured_strict = _current_strict_mode()
    _captured_planned = _current_planned_specialists()
    _captured_token_cb = _current_token_callback()
    _captured_mellea_cb = _current_mellea_attempt_callback()

    def _run_iterate():
        set_strict_mode(_captured_strict)
        set_planned_specialists(_captured_planned)
        set_token_callback(_captured_token_cb)
        set_mellea_attempt_callback(_captured_mellea_cb)
        try:
            for _action_obj, _result, state in app.iterate(halt_after=["reconcile"]):
                final_state_holder["state"] = state
                # Each action appends one record to state.trace; emit the
                # most recent so the SSE client gets the step event the
                # moment Burr returns from that action.
                trace = state.get("trace") or []
                if trace:
                    _push_step(trace[-1])
        except Exception as e:
            log.exception("iterate raised")
            q.put(("error", {"err": f"{type(e).__name__}: {e}"}))
        finally:
            set_strict_mode(False)
            set_planned_specialists(None)
            set_token_callback(None)
            set_mellea_attempt_callback(None)
            q.put(None)  # sentinel

    runner = _threading.Thread(target=_run_iterate, name="riprap-fsm",
                               daemon=True)
    runner.start()

    while True:
        item = q.get()
        if item is None:
            break
        kind, payload = item
        if kind == "step":
            yield {
                "kind": "step",
                "step": payload.get("step"),
                "ok": payload.get("ok"),
                "elapsed_s": payload.get("elapsed_s"),
                "result": payload.get("result"),
                "err": payload.get("err"),
            }
        elif kind == "error":
            yield {"kind": "error", **payload}

    runner.join(timeout=5)
    state = final_state_holder.get("state")
    if state is None:
        yield {"kind": "final", "paragraph": "", "error": "FSM failed before any action completed"}
        return
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
        "prithvi_live": state.get("prithvi_live"),
        "terramind": state.get("terramind"),
        "terramind_lulc": state.get("terramind_lulc"),
        "terramind_buildings": state.get("terramind_buildings"),
        "noaa_tides": state.get("noaa_tides"),
        "nws_alerts": state.get("nws_alerts"),
        "nws_obs": state.get("nws_obs"),
        "ttm_forecast": state.get("ttm_forecast"),
        "ttm_311_forecast": state.get("ttm_311_forecast"),
        "floodnet_forecast": state.get("floodnet_forecast"),
        "ttm_battery_surge": state.get("ttm_battery_surge"),
        "mta_entrances": state.get("mta_entrances"),
        "nycha_developments": state.get("nycha_developments"),
        "doe_schools": state.get("doe_schools"),
        "doh_hospitals": state.get("doh_hospitals"),
        "rag": state.get("rag"),
        "gliner": state.get("gliner"),
        "paragraph": state.get("paragraph"),
        "audit": state.get("audit"),
        "mellea": state.get("mellea"),
        "energy": _summarize_energy(trace),
    }
