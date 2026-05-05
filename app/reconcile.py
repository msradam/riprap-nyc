"""Document-grounded reconciliation via Granite 4.1 (local Ollama).

Uses Granite 4.1's native grounded-generation interface: each specialist
that produced data becomes a separate message with role="document <doc_id>".
Ollama's chat template lifts those into the model's `<documents>` system
block and prepends IBM's official grounded-generation system prompt.

Specialists that didn't fire emit nothing — silence over confabulation.
The model is post-trained to refuse to ground on absent documents.

A server-side post-check verifies every numeric token in the output appears
verbatim in the source documents. Sentences with ungrounded numbers are
dropped from the rendered paragraph (still recorded in the trace as
unverified for audit). This is the cheapest reliable guardrail against
the worst hallucination class — fabricated stats — and it's deterministic.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

from app import llm

log = logging.getLogger("riprap.reconcile")

# Reconciliation is the synthesis step — citation discipline + structured
# output adherence both improve materially with the 8b variant.
# RIPRAP_RECONCILER_MODEL is the canonical name; RIPRAP_OLLAMA_MODEL is
# kept as a back-compat fallback. Default is now 8b on production
# deployments (HF Space ships granite4.1:8b in the container).
OLLAMA_MODEL = os.environ.get("RIPRAP_RECONCILER_MODEL",
                              os.environ.get("RIPRAP_OLLAMA_MODEL", "granite4.1:8b"))

CITATION_NOAA_TIDES = ("NOAA CO-OPS Tides & Currents API "
                       "(api.tidesandcurrents.noaa.gov), 6-min cadence")
CITATION_NWS_ALERTS = ("NWS Public Alerts API (api.weather.gov/alerts/active), "
                       "filtered to flood-relevant event types")
CITATION_NWS_OBS = ("NWS Station Observations API "
                    "(api.weather.gov/stations/<id>/observations/latest)")
CITATION_TTM_FORECAST = (
    "Granite TimeSeries TTM r2 (Ekambaram et al. 2024, NeurIPS) — "
    "ibm-granite/granite-timeseries-ttm-r2 via granite-tsfm. "
    "Zero-shot forecast of the surge residual (observed minus astronomical "
    "tide) at the Battery, NY (NOAA station 8518750). 6-min cadence, "
    "~51 h context, ~9.6 h horizon."
)

# The Ollama chat template auto-prepends Granite's own grounded-generation
# system suffix once the message list contains role="document" entries.
# This text is OUR additional system prompt, prepended to that suffix.
EXTRA_SYSTEM_PROMPT = """Write a flood-exposure briefing for an NYC address. Use ONLY the facts in the provided documents.

Output this markdown skeleton verbatim, filling each `<...>` with content drawn only from the documents. **Every sentence that contains a number MUST end with a `[doc_id]` citation — including derived measurements (TWI, percentile, ratio).** Repeat the source citation if the value is reused. Bold at most one phrase per section using `**...**`. Omit any section whose supporting facts are absent from the documents.

```
**Status.**
<one sentence: dominant exposure signal(s) for this address, citing the strongest documents>.

**Empirical evidence.**
<1-3 sentences citing observed flood evidence: Sandy from [sandy], 311 counts from [nyc311], FloodNet from [floodnet], Ida HWMs from [ida_hwm], Prithvi polygons from [prithvi_water]>.

**Modeled scenarios.**
<1-2 sentences citing modeled flooding from [dep_*] and terrain from [microtopo] (HAND, TWI, percentile). When a [floodnet_forecast_*] doc is present, add one sentence on the forecast event recurrence at the cited sensor>.

**Policy context.**
<1 sentence per RAG hit, citing the agency name and [rag_*]>.
```

Constraints:
- Copy numerical values verbatim from documents. Do not round.
- Name a specific weather event only if a document explicitly applies it to this address.
- For RAG documents (doc_ids starting with `rag_`): describe what the report SAYS at the policy or asset-class level. Do not assert findings the report did not make about this specific address.
- Microtopo percentile direction: a LOW percentile means topographic LOW POINT (water pools); HIGH percentile means HIGH GROUND. State the direction correctly or omit the percentile.
- If no documents are present, output exactly: `No grounded data available for this address.`
"""


# ---- Hallucination guardrail: numeric grounding post-check -----------------

# Numbers must be preceded by whitespace, start-of-string, or punctuation
# OTHER than '-'. This prevents `Extreme-2080` from being parsed as the
# negative number `-2080` (the hyphen is a word separator, not a sign).
_NUM_RE = re.compile(r"(?:(?<=^)|(?<=[\s(\[/]))-?\d[\d,]*(?:\.\d+)?")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[])")
# Strings that are too generic OR are well-known NYC system names rather
# than measurements (311, 911 are city service lines, not values).
_TRIVIAL_NUMS = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "100",
                 "311", "911", "211"}


def _normalize_num(s: str) -> set[str]:
    """A numeric value can appear in a document with or without commas, with
    or without trailing zeros. Return a small set of plausible string
    representations to substring-search for."""
    forms = {s}
    no_comma = s.replace(",", "")
    forms.add(no_comma)
    if "." in no_comma:
        forms.add(no_comma.rstrip("0").rstrip("."))
    return {f for f in forms if f}


def _docs_corpus(doc_msgs: list[dict]) -> str:
    """Join all document message contents (and their role suffixes — those
    carry the doc_id, which is itself a number-free identifier) into one
    big haystack we substring-search for numeric claims."""
    return "\n".join(m.get("content", "") for m in doc_msgs)


# Recognise structured-output section headers like `**Status.**` on their
# own line. These are NOT sentences and are kept verbatim.
_SECTION_HEADER_RE = re.compile(r"^\s*\*\*[A-Z][A-Za-z\s/]+\.\*\*\s*$", re.MULTILINE)

# Granite sometimes emits the four headers inline rather than on their own
# lines (e.g. `**Status.** This address ... **Empirical evidence.** ...`).
# Normalise to one-per-line so the section-renderer regex matches.
_KNOWN_SECTION_HEADERS = ["Status", "Empirical evidence", "Modeled scenarios",
                          "Policy context"]
_INLINE_HEADER_RE = re.compile(
    r"\*\*(" + "|".join(re.escape(h) for h in _KNOWN_SECTION_HEADERS) + r")\.\*\*"
)


def _split_inline_headers(text: str) -> str:
    """Inject a newline before each `**Header.**` so headers sit on their own
    line. The render path and verifier both depend on this."""
    text = _INLINE_HEADER_RE.sub(lambda m: f"\n**{m.group(1)}.**\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_markdown(text: str) -> str:
    """Remove bold markers and citation tags so the numeric scan operates on
    raw content. Used only for the haystack-substring check, not the rendered
    output."""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # **bold** -> bold
    text = re.sub(r"\[[a-z0-9_]+\]", "", text, flags=re.I)  # drop [doc_id]
    return text


def verify_paragraph(paragraph: str, doc_msgs: list[dict]) -> tuple[str, list[dict]]:
    """Drop sentences whose numeric tokens don't appear in any source doc.

    Section-header lines (e.g. `**Status.**`) and inline bold (`**foo**`)
    are preserved verbatim; the verifier strips them only for the
    numeric-grounding check. Sentences are split on sentence-end
    punctuation followed by whitespace + a capital letter or '['.

    Returns (clean_paragraph, dropped_sentences_with_reason).
    """
    paragraph = _split_inline_headers(paragraph)
    haystack = _docs_corpus(doc_msgs)
    out_blocks: list[str] = []
    dropped: list[dict] = []
    body_buf: list[str] = []

    def flush_body():
        if not body_buf:
            return
        body = " ".join(body_buf).strip()
        body_buf.clear()
        if not body:
            return
        sentences = _SENTENCE_END_RE.split(body)
        kept_sents: list[str] = []
        for sent in sentences:
            sent_stripped = sent.strip()
            if not sent_stripped:
                continue
            sent_clean = _strip_markdown(sent_stripped)
            nums = _NUM_RE.findall(sent_clean)
            ungrounded = []
            for n in nums:
                if n in _TRIVIAL_NUMS:
                    continue
                forms = _normalize_num(n)
                if not any(f in haystack for f in forms):
                    ungrounded.append(n)
            if ungrounded:
                dropped.append({"sentence": sent_stripped,
                                "ungrounded_numbers": ungrounded})
                log.warning("dropped ungrounded sentence: %r (nums: %s)",
                            sent_stripped, ungrounded)
                continue
            kept_sents.append(sent_stripped)
        if kept_sents:
            out_blocks.append(" ".join(kept_sents))

    for line in paragraph.splitlines():
        if _SECTION_HEADER_RE.match(line):
            flush_body()
            out_blocks.append(line.strip())
        else:
            body_buf.append(line.strip())
    flush_body()

    cleaned = "\n".join(b for b in out_blocks if b).strip()
    if not cleaned:
        cleaned = "Could not produce a verifiable summary; see the data panels."
    return cleaned, dropped


def _doc_message(doc_id: str, body_lines: list[str]) -> dict:
    """One Granite-native document message. The doc_id rides on the role
    suffix; Ollama's template uses it as the document title and lifts the
    pair into the <documents> block."""
    return {"role": f"document {doc_id}", "content": "\n".join(body_lines)}


def trim_docs_to_plan(doc_msgs: list[dict],
                      planned_specialists: set[str] | None) -> list[dict]:
    """Drop document messages whose doc_id family wasn't in the planner's
    specialist list.

    The FSM's parallel fan-out runs every specialist regardless of what
    the planner asked for; this lets the user see all the data come in
    via the trace + map. But for the reconciler we want only what the
    planner judged relevant, both to cut prompt tokens (≈30-50% on
    typical single_address queries) and to keep the briefing focused.

    Doc IDs are mapped to specialist family prefixes:
      sandy -> {sandy}
      dep_stormwater -> {dep_*}
      floodnet -> {floodnet}
      nyc311 -> {nyc311}
      microtopo -> {microtopo}
      mta_entrances -> {mta_entrance_*}
      nycha_developments -> {nycha_dev_*}
      doe_schools -> {doe_school_*}
      doh_hospitals -> {nyc_hospital_*}        # historical id naming
      ida_hwm -> {ida_hwm}
      prithvi_water -> {prithvi_water}
      noaa_tides -> {noaa_tides}
      nws_alerts -> {nws_alerts}
      nws_obs -> {nws_obs}
      ttm_forecast -> {ttm_forecast}
      ttm_311_forecast -> {ttm_311_forecast}
      floodnet_forecast -> {floodnet_forecast_*}
      terramind -> {terramind_*, syn_*}
      rag -> {rag_*}
      nta_resolve -> {nta_resolve, nta_*}
      dob_permits -> {dob_*}

    Always preserved (never trimmed):
      geocode, scope_note, nta_resolve — they orient the briefing or
      gate scope and the planner doesn't always name them explicitly.

    Set RIPRAP_TRIM_DOCS=0 to disable (defaults on).
    """
    import os as _os  # local import to keep module top tidy
    if not planned_specialists or not doc_msgs:
        return doc_msgs
    if _os.environ.get("RIPRAP_TRIM_DOCS", "1").lower() in ("0", "false", "no"):
        return doc_msgs

    # Build the allowed-prefix set from the planner's specialists.
    PREFIXES_BY_SPECIALIST: dict[str, tuple[str, ...]] = {
        "sandy":              ("sandy",),
        "dep_stormwater":     ("dep_",),
        "floodnet":           ("floodnet",),
        "nyc311":             ("nyc311",),
        "microtopo":          ("microtopo",),
        "ida_hwm":            ("ida_hwm",),
        "prithvi_water":      ("prithvi_water",),
        "noaa_tides":         ("noaa_tides",),
        "nws_alerts":         ("nws_alerts",),
        "nws_obs":            ("nws_obs",),
        "ttm_forecast":       ("ttm_forecast",),
        "ttm_311_forecast":   ("ttm_311_forecast",),
        "floodnet_forecast":  ("floodnet_forecast",),
        "ttm_battery_surge":  ("ttm_battery",),
        "terramind":          ("terramind", "syn_"),
        "terramind_lulc":     ("tm_lulc",),
        "terramind_buildings": ("tm_buildings",),
        "rag":                ("rag_",),
        "rag_mta":            ("rag_",),
        "nta_resolve":        ("nta_resolve", "nta_"),
        "dob_permits":        ("dob_",),
        "mta_entrances":      ("mta_entrance",),
        "nycha_developments": ("nycha_dev",),
        "doe_schools":        ("doe_school", "nyc_school"),
        "doh_hospitals":      ("doh_hospital", "nyc_hospital"),
    }
    ALWAYS_KEEP = ("geocode", "scope_note", "nta_resolve")

    allowed_prefixes: set[str] = set()
    for spec in planned_specialists:
        for p in PREFIXES_BY_SPECIALIST.get(spec, ()):
            allowed_prefixes.add(p)
    if not allowed_prefixes:
        return doc_msgs  # planner gave us nothing matchable; bail safely

    kept: list[dict] = []
    for m in doc_msgs:
        role = m.get("role", "")
        if not role.startswith("document "):
            kept.append(m)
            continue
        doc_id = role[len("document "):].strip()
        if doc_id.startswith(ALWAYS_KEEP):
            kept.append(m)
            continue
        if any(doc_id.startswith(p) for p in allowed_prefixes):
            kept.append(m)
    return kept


def build_documents(state: dict[str, Any]) -> list[dict]:
    """Build Granite-native document-role messages, gated so absent
    specialists emit no document at all.

    Document emission order follows the Stones grouping: geocode preamble,
    then Cornerstone (static hazard record), Keystone (asset register),
    Touchstone (live sensors + EO), Lodestone (forecasts), and finally
    policy-context retrieval (RAG + GLiNER) as ancillary. The grouping
    is also the order they're iterated for prompt building, so the
    Capstone (reconciler) sees the four data-Stones in canonical order.

    Scope guard: if the resolved address is OUTSIDE the NYC bbox, only
    the geocode + live national specialists emit documents. NYC-specific
    layers (Sandy, DEP, FloodNet, NYC 311, microtopo, Ida HWMs, Prithvi,
    NYC RAG corpus) are suppressed and a `scope_note` doc is added telling
    the reconciler not to invoke NYC content.
    """
    docs: list[dict] = []

    geo = state.get("geocode") or {}
    NYC_S, NYC_W, NYC_N, NYC_E = 40.49, -74.27, 40.92, -73.69
    out_of_nyc = (
        geo.get("lat") is not None and geo.get("lon") is not None and not (
            NYC_S <= geo["lat"] <= NYC_N and NYC_W <= geo["lon"] <= NYC_E
        )
    )

    # ---- Preamble: scope_note (out-of-NYC) + geocode -------------------
    if out_of_nyc:
        # Compose a single live-conditions snapshot from whatever the
        # national specialists produced. This always emits when out_of_nyc,
        # even on a calm day, so the reconciler has SOMETHING grounded to
        # report instead of only a list of what doesn't apply.
        place_label = (geo.get("borough") or geo.get("address") or
                       f"{geo['lat']:.4f}, {geo['lon']:.4f}")
        body = [
            "Source: Riprap planner + national live specialists. Scope "
            "guard: this address is OUTSIDE NYC; NYC-specific datasets "
            "are not in scope at this location.",
            f"Resolved location: {place_label} ({geo['lat']:.4f}, "
            f"{geo['lon']:.4f}).",
        ]
        tides = state.get("noaa_tides") or {}
        if tides.get("station_id") and tides.get("error") is None:
            tline = (f"NOAA Tides & Currents — nearest gauge: "
                     f"{tides.get('station_name')} (NOAA "
                     f"{tides.get('station_id')}, "
                     f"{tides.get('distance_km')} km from address).")
            body.append(tline)
            if tides.get("observed_ft_mllw") is not None:
                body.append(
                    f"Observed water level: {tides['observed_ft_mllw']} ft "
                    f"above MLLW; predicted: "
                    f"{tides.get('predicted_ft_mllw')} ft; residual "
                    f"(observed minus predicted): "
                    f"{tides.get('residual_ft')} ft."
                )
            else:
                body.append("No water-level observation reported by the "
                            "gauge in the last poll.")
        alerts = state.get("nws_alerts") or {}
        body.append(
            f"NWS Public Alerts at point: {alerts.get('n_active', 0)} "
            "active flood-relevant alert(s)."
        )
        if alerts.get("alerts"):
            for a in alerts["alerts"][:3]:
                body.append(
                    f"- {a.get('event','?')} (severity "
                    f"{a.get('severity','?')}, urgency "
                    f"{a.get('urgency','?')}); expires "
                    f"{(a.get('expires') or '')[:16]}; area: "
                    f"{(a.get('areaDesc') or '')[:120]}."
                )
        obs = state.get("nws_obs") or {}
        if obs.get("station_id") and obs.get("error") is None:
            line = (f"Nearest NWS ASOS: {obs.get('station_name')} "
                    f"({obs.get('station_id')}, "
                    f"{obs.get('distance_km')} km).")
            body.append(line)
            if obs.get("precip_last_hour_mm") is not None:
                body.append(
                    f"Precipitation last 1 h: "
                    f"{obs['precip_last_hour_mm']} mm; last 6 h: "
                    f"{obs.get('precip_last_6h_mm')} mm."
                )
            else:
                body.append("No precipitation reported in the last hourly "
                            "observation.")
        ttm = state.get("ttm_forecast") or {}
        if ttm.get("available") and ttm.get("interesting"):
            body.append(
                f"Granite TTM r2 surge forecast at the Battery: peak "
                f"residual {ttm.get('forecast_peak_ft')} ft expected in "
                f"{ttm.get('forecast_peak_minutes_ahead')} minutes — note "
                f"this gauge is in NYC harbor, not local to this address."
            )
        docs.append(_doc_message("scope_note", body))

    if geo:
        body = [
            "Source: NYC DCP Geosearch (geosearch.planninglabs.nyc).",
            f"Resolved address: {geo['address']}.",
            f"Borough: {geo.get('borough') or 'unknown'}.",
            f"Coordinates: {geo['lat']:.5f} N, {geo['lon']:.5f} W.",
        ]
        if geo.get("bbl"):
            body.append(f"BBL (tax-lot id): {geo['bbl']}.")
        docs.append(_doc_message("geocode", body))

    # ---- Cornerstone — The Hazard Reader -------------------------------
    # Static record of what NYC's ground remembers about flooding: the
    # 2012 Sandy empirical extent, modelled DEP stormwater scenarios,
    # 2021 Ida USGS high-water marks, baked Prithvi-EO Ida-attributable
    # polygons, and LiDAR microtopography (elevation / HAND / TWI).

    # Gate: only emit the Sandy doc when the address is actually inside the
    # 2012 extent. Granite has a strong training prior associating NYC + flood
    # + Brooklyn with Sandy and will misread "outside" as "inside" if given
    # the chance — silence-over-confabulation rules.
    if not out_of_nyc and state.get("sandy") is True:
        body = [
            "Source: NYC Sandy Inundation Zone (NYC OpenData 5xsi-dfpx, "
            "empirical extent of areas flooded by Hurricane Sandy in 2012).",
            "FACT: The address is LOCATED WITHIN this empirical 2012 inundation extent.",
            "INTERPRETATION: Hurricane Sandy did flood this address (or this immediate parcel) on October 29-30, 2012. This is a historical fact, not a model prediction.",
            "Do not state the opposite. The address is inside the Sandy inundation zone.",
        ]
        docs.append(_doc_message("sandy", body))

    dep = state.get("dep")
    if not out_of_nyc and dep:
        for scen, info in dep.items():
            if info.get("depth_class", 0) > 0:
                body = [
                    f"Source: {info['citation']}.",
                    "Address inside scenario footprint: yes.",
                    f"Modeled depth class: {info['depth_label']}.",
                ]
                docs.append(_doc_message(scen, body))

    ida = state.get("ida_hwm")
    if not out_of_nyc and ida and (ida.get("n_within_radius") or 0) > 0:
        body = [
            "Source: USGS STN Hurricane Ida 2021 high-water marks (Event 312, NY State).",
            f"USGS HWMs within {ida['radius_m']} m: {ida['n_within_radius']}.",
        ]
        if ida.get("max_height_above_gnd_ft") is not None:
            body.append(f"Max water height above ground: {ida['max_height_above_gnd_ft']} ft.")
        if ida.get("max_elev_ft") is not None:
            body.append(f"Max HWM elevation: {ida['max_elev_ft']} ft.")
        if ida.get("nearest_dist_m") is not None:
            body.append(f"Nearest HWM site: {ida['nearest_site']} ({ida['nearest_dist_m']} m away).")
        docs.append(_doc_message("ida_hwm", body))

    pw = state.get("prithvi_water")
    if not out_of_nyc and pw and pw.get("nearest_distance_m") is not None:
        body = [
            "Source: Prithvi-EO 2.0 (300M params, NASA/IBM, Apache-2.0). "
            "Sen1Floods11 fine-tune for water/flood semantic segmentation, "
            "run via TerraTorch on a real Hurricane Ida pre/post HLS Sentinel-2 "
            f"pair: {pw['scene_id']} (dates: {pw['scene_date']}).",
            "INTERPRETATION: the polygons are pixels classified as water in the "
            "post-event scene (2021-09-02, ~12 h after Ida peak rainfall) but NOT "
            "in the pre-event reference (2021-08-25). They are candidate "
            "Ida-attributable surface inundation.",
            f"Address sits inside an Ida-attributable inundation polygon: "
            f"{'YES' if pw['inside_water_polygon'] else 'no'}.",
            f"Distance to nearest Ida-attributable polygon: {pw['nearest_distance_m']} m.",
            f"Distinct Ida-attributable polygons within 500 m: "
            f"{pw['n_polygons_within_500m']}.",
            "Honest scope: subway entrances and basement apartments — the dominant "
            "Ida damage mode in NYC — are not visible to optical satellites. By the "
            "Sep 2 16:02 UTC pass much pluvial street water had drained. The signal "
            "primarily captures marsh/parkland ponding, riverside spillover, and "
            "low-lying inundation that survived ~12 hours.",
        ]
        docs.append(_doc_message("prithvi_water", body))

    mt = state.get("microtopo")
    if not out_of_nyc and mt:
        # Compute a categorical topographic position so Granite can't flip
        # the directional reading of the percentile.
        p200 = mt["rel_elev_pct_200m"]
        if p200 < 25:
            position = ("topographic LOW POINT — surface runoff in the "
                        "200 m neighbourhood routes toward this location")
        elif p200 > 75:
            position = ("RELATIVELY HIGH GROUND — most of the 200 m "
                        "neighbourhood is at lower elevation than this address")
        else:
            position = ("MID-SLOPE — neither a clear low point nor high ground")
        body = [
            "Source: USGS 3DEP 30 m DEM (LiDAR-derived) via py3dep, with TWI and HAND derived using whitebox-workflows hydrology toolkit.",
            f"Point elevation at this address: {mt['point_elev_m']} m above sea level.",
            f"Topographic position relative to surroundings: {position}.",
            f"Fraction of cells within 200 m radius that are LOWER in elevation than this address: {mt['rel_elev_pct_200m']}%.",
            f"Fraction of cells within 750 m radius that are LOWER in elevation than this address: {mt['rel_elev_pct_750m']}%.",
            f"Basin relief (max elevation in 750 m AOI minus address elevation): {mt['basin_relief_m']} m.",
        ]
        if mt.get("hand_m") is not None:
            hand_v = mt["hand_m"]
            hand_interp = (
                "very low (sub-meter) — the address sits at or near drainage level"
                if hand_v < 1.0 else
                "low (1-3 m) — the address is close to the local drainage line"
                if hand_v < 3.0 else
                "moderate (3-8 m) — typical urban-block elevation above drainage"
                if hand_v < 8.0 else
                "high (>8 m) — the address sits well above the local drainage network"
            )
            body.append(
                f"Height Above Nearest Drainage (HAND): {hand_v} m. "
                f"Interpretation: {hand_interp}. HAND is the standard hydrology "
                f"index for vertical distance from a cell to the nearest channel; "
                f"used by USGS, USACE, and InfoWorks ICM."
            )
        if mt.get("twi") is not None:
            twi_v = mt["twi"]
            twi_interp = (
                "low — the cell sheds water; not saturation-prone"
                if twi_v < 6 else
                "moderate"
                if twi_v < 10 else
                "high — the cell tends to accumulate water"
                if twi_v < 14 else
                "very high — saturation-prone terrain"
            )
            body.append(
                f"Topographic Wetness Index (TWI): {twi_v}. "
                f"Interpretation: {twi_interp}. TWI = ln(specific catchment area / tan slope) "
                f"is the TOPMODEL framework's saturation propensity metric."
            )
        docs.append(_doc_message("microtopo", body))

    # ---- Keystone — The Asset Register ---------------------------------
    # Per-asset documents for transit, housing, education, healthcare, and
    # the TerraMind synthetic-prior land-cover (slated to be replaced by
    # the NYC-Buildings LoRA in a later commit). Each register specialist
    # emits one doc per asset so the reconciler can cite specifically
    # (e.g. [mta_entrance_54], [nycha_dev_004]). Caps keep the total
    # payload bounded; specialists already truncated to their per-query
    # maxes.
    mta = state.get("mta_entrances")
    if not out_of_nyc and mta and mta.get("available"):
        for e in mta.get("entrances", [])[:6]:
            sid = e.get("station_id")
            body = [
                "Source: MTA Open Data subway entrances "
                "+ NYC OEM Sandy 2012 Inundation Zone (5xsi-dfpx) "
                "+ NYC DEP Stormwater Flood Maps + USGS 3DEP DEM.",
                (f"Station {e.get('station_name')} ({e.get('daytime_routes')}), "
                 f"entrance type {e.get('entrance_type')}, "
                 f"{e.get('distance_m')} m from query."),
                (f"Entrance elevation {e.get('elevation_m')} m, "
                 f"HAND (height above nearest drainage) {e.get('hand_m')} m."),
            ]
            if e.get("inside_sandy_2012"):
                body.append("This entrance is inside the 2012 Sandy "
                            "Inundation Zone (empirical).")
            else:
                body.append("This entrance is NOT inside the 2012 Sandy "
                            "Inundation Zone.")
            if (e.get("dep_extreme_2080_class") or 0) > 0:
                body.append(
                    f"NYC DEP Extreme-2080 scenario: "
                    f"{e.get('dep_extreme_2080_label')}.")
            if (e.get("dep_moderate_2050_class") or 0) > 0:
                body.append(
                    f"NYC DEP Moderate-2050 scenario: "
                    f"{e.get('dep_moderate_2050_label')}.")
            body.append("ADA-accessible (heuristic from entrance_type): "
                        f"{'yes' if e.get('ada_accessible') else 'no'}.")
            docs.append(_doc_message(f"mta_entrance_{sid}", body))

    nycha = state.get("nycha_developments")
    if not out_of_nyc and nycha and nycha.get("available"):
        for d in nycha.get("developments", [])[:4]:
            tds = d.get("tds_num")
            body = [
                "Source: NYC Open Data NYCHA Developments (phvi-damg) "
                "+ NYC OEM Sandy 2012 Inundation Zone (5xsi-dfpx) "
                "+ NYC DEP Stormwater Flood Maps + USGS 3DEP DEM.",
                (f"NYCHA development {d.get('development')} (TDS {tds}, "
                 f"{d.get('borough')}), footprint {d.get('footprint_km2')} km², "
                 f"{d.get('distance_m')} m from query."),
                (f"Representative-point elevation {d.get('rep_elevation_m')} m, "
                 f"HAND {d.get('rep_hand_m')} m."),
                (f"{d.get('pct_inside_sandy_2012')}% of footprint inside the "
                 "2012 Sandy Inundation Zone (empirical)."),
            ]
            if (d.get("pct_in_dep_extreme_2080") or 0) > 0:
                body.append(
                    f"{d.get('pct_in_dep_extreme_2080')}% of footprint inside "
                    "NYC DEP Extreme-2080 scenario "
                    f"(of which {d.get('pct_in_dep_extreme_2080_deep')}% in the "
                    "deepest >4 ft band).")
            if (d.get("pct_in_dep_moderate_2050") or 0) > 0:
                body.append(
                    f"{d.get('pct_in_dep_moderate_2050')}% of footprint inside "
                    "NYC DEP Moderate-2050 scenario.")
            docs.append(_doc_message(f"nycha_dev_{tds}", body))

    schools = state.get("doe_schools")
    if not out_of_nyc and schools and schools.get("available"):
        for s in schools.get("schools", [])[:5]:
            lc = s.get("loc_code")
            body = [
                "Source: NYC DOE Locations Points "
                "+ NYC OEM Sandy 2012 Inundation Zone (5xsi-dfpx) "
                "+ NYC DEP Stormwater Flood Maps + USGS 3DEP DEM.",
                (f"School {s.get('loc_name')} ({lc}, {s.get('address')}, "
                 f"{s.get('borough')}), {s.get('distance_m')} m from query."),
                (f"School-point elevation {s.get('elevation_m')} m, "
                 f"HAND {s.get('hand_m')} m."),
            ]
            if s.get("inside_sandy_2012"):
                body.append("This school is inside the 2012 Sandy "
                            "Inundation Zone (empirical).")
            else:
                body.append("This school is NOT inside the 2012 Sandy "
                            "Inundation Zone (centroid-point join; "
                            "building-footprint join is a documented "
                            "follow-up).")
            if (s.get("dep_extreme_2080_class") or 0) > 0:
                body.append(
                    f"NYC DEP Extreme-2080 scenario: "
                    f"{s.get('dep_extreme_2080_label')}.")
            if (s.get("dep_moderate_2050_class") or 0) > 0:
                body.append(
                    f"NYC DEP Moderate-2050 scenario: "
                    f"{s.get('dep_moderate_2050_label')}.")
            docs.append(_doc_message(f"doe_school_{lc}", body))

    hospitals = state.get("doh_hospitals")
    if not out_of_nyc and hospitals and hospitals.get("available"):
        for h in hospitals.get("hospitals", [])[:4]:
            fid = h.get("fac_id")
            body = [
                "Source: NYS DOH Health Facility Certification (vn5v-hh5r) "
                "+ NYC OEM Sandy 2012 Inundation Zone (5xsi-dfpx) "
                "+ NYC DEP Stormwater Flood Maps + USGS 3DEP DEM.",
                (f"Hospital {h.get('facility_name')} (NYS DOH facility "
                 f"{fid}, {h.get('address')}, {h.get('borough')}), "
                 f"operator {h.get('operator_name')}, "
                 f"ownership {h.get('ownership_type')}, "
                 f"{h.get('distance_m')} m from query."),
                (f"Hospital-point elevation {h.get('elevation_m')} m, "
                 f"HAND {h.get('hand_m')} m."),
            ]
            if h.get("inside_sandy_2012"):
                body.append("This hospital is inside the 2012 Sandy "
                            "Inundation Zone (empirical).")
            else:
                body.append("This hospital is NOT inside the 2012 Sandy "
                            "Inundation Zone (centroid-point join; "
                            "building-footprint join is a documented "
                            "follow-up).")
            if (h.get("dep_extreme_2080_class") or 0) > 0:
                body.append(
                    f"NYC DEP Extreme-2080 scenario: "
                    f"{h.get('dep_extreme_2080_label')}.")
            if (h.get("dep_moderate_2050_class") or 0) > 0:
                body.append(
                    f"NYC DEP Moderate-2050 scenario: "
                    f"{h.get('dep_moderate_2050_label')}.")
            docs.append(_doc_message(f"nyc_hospital_{fid}", body))

    # TerraMind synthetic-prior — explicitly fourth epistemic class
    # alongside empirical / modeled / proxy. Reconciler narration must
    # frame this as "TerraMind generated a plausible land-cover map from
    # terrain context", never "imaged" or "reconstructed". Class labels
    # are tentative against ESRI Land Cover 2020-2022 schema. Slated for
    # replacement by the NYC-Buildings LoRA in a later migration commit.
    tm = state.get("terramind")
    if not out_of_nyc and tm and tm.get("ok"):
        body = [
            "Source: TerraMind 1.0 base (IBM/ESA, Apache-2.0) any-to-any "
            "generative foundation model. This is a SYNTHETIC PRIOR, "
            "not a measurement: TerraMind generates plausible categorical "
            "land-cover maps from terrain context, never observations.",
            f"Chain: {' -> '.join(tm.get('tim_chain') or ['DEM', 'LULC_synthetic'])}.",
            f"Diffusion steps: {tm.get('diffusion_steps', '?')}.",
            f"Diffusion seed (reproducibility): {tm.get('diffusion_seed', '?')}.",
            f"Input DEM mean elevation at this address: "
            f"{tm.get('dem_mean_m', 0):.2f} m (NYC 30 m LiDAR raster).",
            f"Label schema: {tm.get('label_schema', 'ESRI Land Cover, tentative')}.",
            f"Dominant synthetic land-cover class: "
            f"{tm.get('dominant_class_display') or tm.get('dominant_class', 'unknown')} at "
            f"{tm.get('dominant_pct', 0):.1f}% of the 5 km area.",
            f"Synthetic class fractions ({tm.get('n_classes_observed', 0)} "
            f"classes observed):",
        ]
        for label, pct in (tm.get("class_fractions") or {}).items():
            body.append(f"  - {label}: {pct:.1f}%")
        body.extend([
            "synthetic_modality: true",
            "Use only the careful framing 'TerraMind generated a "
            "plausible synthetic land-cover prior from the terrain "
            "context, with class labels tentatively aligned to ESRI "
            "schema'. Do NOT claim measurement, imaging, observation, "
            "or reconstruction.",
        ])
        docs.append(_doc_message("terramind_synthetic", body))

    # TerraMind-NYC Buildings adapter (msradam/TerraMind-NYC-Adapters,
    # Apache-2.0, fine-tuned on NYC building footprints on AMD MI300X).
    # Distinct from the synthetic-prior block above — this is a real
    # segmentation against the per-query Sentinel-2/1/DEM chip and
    # reports an empirical building-footprint area fraction.
    tmb = state.get("terramind_buildings")
    if not out_of_nyc and tmb and tmb.get("ok"):
        body = [
            "Source: msradam/TerraMind-NYC-Adapters (Apache-2.0) — NYC "
            "Buildings LoRA on TerraMind 1.0 base, fine-tuned on AMD "
            "Instinct MI300X. Test mIoU 0.5511 on held-out NYC chips.",
            f"Adapter: {tmb.get('adapter')}.",
            f"Predicted building-footprint coverage in chip: "
            f"{tmb.get('pct_buildings')}%.",
        ]
        if tmb.get("n_building_components") is not None:
            body.append(
                f"Distinct building connected components: "
                f"{tmb.get('n_building_components')}."
            )
        body.append(
            "Class labels: " + ", ".join(tmb.get("class_labels") or [])
            + "."
        )
        docs.append(_doc_message("tm_buildings", body))

    # ---- Touchstone — The Live Observer --------------------------------
    # Live sensors and per-query EO that change minute to minute:
    # FloodNet ultrasonic depth, NYC 311 flood complaints, NWS hourly
    # METAR observations, NOAA tide-gauge water levels, Prithvi-EO
    # live water segmentation. The reconciler treats these as right-now
    # context, not historical record.
    fn = state.get("floodnet")
    if not out_of_nyc and fn and fn.get("n_sensors", 0) > 0:
        body = [
            "Source: FloodNet NYC ultrasonic depth sensor network (api.floodnet.nyc).",
            f"Sensors within {fn['radius_m']} m: {fn['n_sensors']}.",
            f"Sensors with labeled flood events in last 3 years: {fn['n_sensors_with_events']}.",
            f"Total flood events at those sensors: {fn['n_flood_events_3y']}.",
        ]
        peak = fn.get("peak_event")
        if peak and peak.get("max_depth_mm") is not None:
            ts = (peak.get("start_time") or "")[:10]
            body.append(
                f"Peak event: {peak['max_depth_mm']} mm depth at sensor "
                f"{peak['deployment_id']} starting {ts}."
            )
        docs.append(_doc_message("floodnet", body))

    nyc311 = state.get("nyc311")
    if not out_of_nyc and nyc311 and nyc311.get("n", 0) > 0:
        body = [
            "Source: NYC 311 service requests (Socrata erm2-nwe9, 2010-present).",
            f"311 flood-related complaints within {nyc311['radius_m']} m, last {nyc311['years']} years: {nyc311['n']}.",
        ]
        if nyc311.get("by_descriptor"):
            top = "; ".join(f"{k}: {v}" for k, v in nyc311["by_descriptor"].items())
            body.append(f"Top descriptors and counts: {top}.")
        if nyc311.get("by_year"):
            yrs = ", ".join(f"{y}: {n}" for y, n in nyc311["by_year"].items())
            body.append(f"Per-year counts: {yrs}.")
        docs.append(_doc_message("nyc311", body))

    obs = state.get("nws_obs")
    if not out_of_nyc and obs and obs.get("station_id") and obs.get("error") is None and (
        obs.get("precip_last_hour_mm") is not None or
        obs.get("precip_last_6h_mm") is not None
    ):
        body = [
            f"Source: {CITATION_NWS_OBS}.",
            f"Nearest hourly METAR station: {obs['station_name']} ({obs['station_id']}, "
            f"{obs['distance_km']} km away).",
            f"Observation time: {obs.get('obs_time') or 'unknown'}.",
        ]
        if obs.get("precip_last_hour_mm") is not None:
            body.append(f"Precipitation last 1 h: {obs['precip_last_hour_mm']} mm.")
        if obs.get("precip_last_3h_mm") is not None:
            body.append(f"Precipitation last 3 h: {obs['precip_last_3h_mm']} mm.")
        if obs.get("precip_last_6h_mm") is not None:
            body.append(f"Precipitation last 6 h: {obs['precip_last_6h_mm']} mm.")
        body.append(
            "Heavy short-duration rainfall (e.g. >25 mm/h or >50 mm/6 h) is the "
            "primary driver of NYC pluvial / sewer-backup flooding; the static "
            "DEP scenarios assume specific rainfall intensities."
        )
        docs.append(_doc_message("nws_obs", body))

    tides = state.get("noaa_tides")
    if not out_of_nyc and tides and tides.get("observed_ft_mllw") is not None:
        body = [
            f"Source: {CITATION_NOAA_TIDES}.",
            f"Nearest tide gauge: {tides['station_name']} (NOAA station "
            f"{tides['station_id']}, {tides['distance_km']} km away).",
            f"Observation time (LST/LDT): {tides.get('obs_time') or 'unknown'}.",
            f"Current observed water level above MLLW: {tides['observed_ft_mllw']} ft.",
        ]
        if tides.get("predicted_ft_mllw") is not None:
            body.append(
                f"Astronomical tide prediction at the same instant: "
                f"{tides['predicted_ft_mllw']} ft above MLLW."
            )
        if tides.get("residual_ft") is not None:
            interp = (
                "approximately at predicted level"
                if abs(tides["residual_ft"]) < 0.5 else
                "elevated above prediction (positive residual is consistent with "
                "wind-driven setup or storm surge)"
                if tides["residual_ft"] > 0 else
                "below prediction (negative residual is consistent with offshore wind)"
            )
            body.append(
                f"Residual (observed minus predicted): {tides['residual_ft']} ft — "
                f"{interp}."
            )
        body.append(
            "Note: this is real-time tidal context for nearby coastal water level. "
            "The address itself may be inland — the reading describes the bay/harbor "
            "level the gauge is in, not the address."
        )
        docs.append(_doc_message("noaa_tides", body))

    # Per-query Sentinel-2 water-segmentation observation. Distinct from
    # `prithvi_water` (the offline 2021 Ida polygons in the Cornerstone
    # group) — this one fires against today's imagery and emits a dated
    # observation.
    plive = state.get("prithvi_live")
    if not out_of_nyc and plive and plive.get("ok"):
        body = [
            "Source: msradam/Prithvi-EO-2.0-NYC-Pluvial (Apache-2.0) — "
            "NYC-Pluvial v2 fine-tune of Prithvi-EO 2.0 trained on AMD "
            "Instinct MI300X via AMD Developer Cloud (test flood IoU "
            "0.5979). Live segmentation over a Sentinel-2 L2A scene "
            "from Microsoft Planetary Computer.",
            f"Sentinel-2 scene id: {plive.get('item_id', 'unknown')}.",
            f"Observation date: {(plive.get('item_datetime') or 'unknown')[:10]}.",
            f"Cloud cover: {plive.get('cloud_cover', 0):.3f}%.",
            f"% water within 500 m of address: "
            f"{plive.get('pct_water_within_500m', 0):.2f}.",
            f"% water across 5 km chip: "
            f"{plive.get('pct_water_full', 0):.2f}.",
        ]
        docs.append(_doc_message("prithvi_live", body))

    # TerraMind-NYC LULC adapter — current 5-class macro land-cover from
    # the per-query Sentinel-2/1/DEM chip. Empirical observation, not the
    # synthetic-prior emitted by the legacy `terramind_synthetic` doc.
    tml = state.get("terramind_lulc")
    if not out_of_nyc and tml and tml.get("ok"):
        body = [
            "Source: msradam/TerraMind-NYC-Adapters (Apache-2.0) — NYC "
            "LULC LoRA on TerraMind 1.0 base, fine-tuned on AMD "
            "Instinct MI300X. Test mIoU 0.5866 on held-out NYC chips.",
            f"Adapter: {tml.get('adapter')}.",
            f"Dominant land-cover class in chip: "
            f"{tml.get('dominant_class')} at {tml.get('dominant_pct')}%.",
            "Per-class fractions:",
        ]
        for label, pct in (tml.get("class_fractions") or {}).items():
            body.append(f"  - {label}: {pct}%")
        docs.append(_doc_message("tm_lulc", body))

    # ---- Lodestone — The Projector -------------------------------------
    # Forward-looking signals: NWS public flood alerts, Granite TTM r2
    # zero-shot Battery surge residual, per-address NYC 311 weekly rate,
    # FloodNet sensor recurrence. Every cited number here is a forecast.
    alerts = state.get("nws_alerts") or {}
    active = alerts.get("alerts") or []
    if not out_of_nyc and active:
        body = [
            f"Source: {CITATION_NWS_ALERTS}.",
            f"Active flood-relevant alerts at this address right now: {len(active)}.",
        ]
        for a in active[:4]:
            body.append(
                f"- {a.get('event','(event)')} (severity: {a.get('severity','?')}, "
                f"urgency: {a.get('urgency','?')}); issued {a.get('sent','')[:16]}, "
                f"expires {a.get('expires','')[:16]}; "
                f"sender: {a.get('sender_name','NWS')}; "
                f"area: {(a.get('areaDesc') or '')[:120]}."
            )
            if a.get("headline"):
                body.append(f"  Headline (verbatim): {a['headline'][:240]}")
        body.append(
            "These are official NWS alerts retrieved live; if any FLOOD or "
            "FLASH FLOOD WARNING/WATCH is in this list, it applies to the "
            "address right now and should be foregrounded."
        )
        docs.append(_doc_message("nws_alerts", body))

    ttm = state.get("ttm_forecast")
    if not out_of_nyc and ttm and ttm.get("available") and ttm.get("interesting"):
        body = [
            f"Source: {CITATION_TTM_FORECAST}.",
            f"Gauge: {ttm['station_name']} (NOAA {ttm['station_id']}, "
            f"{ttm.get('distance_km', '?')} km from address — closest of "
            "Battery / Kings Point / Sandy Hook).",
            f"Context window: {ttm['context_length']} samples (~"
            f"{ttm['context_length']*6/60:.1f} h of 6-min residual).",
            f"Forecast horizon: {ttm['horizon_steps']} samples (~"
            f"{ttm['horizon_steps']*6/60:.1f} h ahead).",
            f"Recent residual: {ttm['history_recent_ft']} ft "
            f"(residual = observed water level minus astronomical prediction).",
            f"Recent peak |residual| in context: {ttm['history_peak_abs_ft']} ft.",
            f"Forecast peak residual: {ttm['forecast_peak_ft']} ft, expected "
            f"{ttm['forecast_peak_minutes_ahead']} minutes from now "
            f"(at {ttm['forecast_peak_time_utc']} UTC).",
            "INTERPRETATION: positive residual is a wind-driven setup or "
            "storm-surge component on top of the tide; the model predicts the "
            "non-tidal part NOAA's astronomical predictor does not cover.",
        ]
        docs.append(_doc_message("ttm_forecast", body))

    # Per-address 311 flood-complaint forecast — different time scale,
    # different signal entirely. TTM r2 zero-shot on daily counts
    # (~17 months of history → ~3 months of forecast). Aggregated to
    # weekly for the narration since readers think in weeks.
    ttm311 = state.get("ttm_311_forecast")
    if not out_of_nyc and ttm311 and ttm311.get("available"):
        accel = ('YES — forecast > 50% above recent 30-day baseline'
                 if ttm311.get('accelerating')
                 else 'no — forecast in line with recent baseline')
        body = [
            "Source: IBM Granite TimeSeries TTM r2 (Ekambaram et al. 2024, "
            "NeurIPS) zero-shot forecast on NYC 311 flood-complaint history "
            "(Sewer Backup, Catch Basin Clogged/Flooding, Street Flooding, "
            "Manhole Overflow) within "
            f"{ttm311.get('radius_m', 200)} m of the address.",
            f"Context window: {ttm311['days_context']} days "
            f"({ttm311['days_context'] // 7} weeks) ending "
            f"{ttm311.get('context_window_end', '?')}.",
            f"Total complaints in context window: "
            f"{ttm311['history_total_complaints']}.",
            f"History recent 30-day rate: {ttm311['history_recent_30d_mean']} "
            f"complaints/day "
            f"(≈{ttm311['history_weekly_equivalent']} per week).",
            f"Forecast horizon: {ttm311['days_horizon']} days "
            f"({ttm311['days_horizon'] // 7} weeks) ahead.",
            f"Forecast rate: {ttm311['forecast_mean_per_day']} complaints/day "
            f"(≈{ttm311['forecast_weekly_equivalent']} per week).",
            f"Forecast peak day: {ttm311['forecast_peak_day']} complaints, "
            f"day +{ttm311['forecast_peak_day_offset']}.",
            f"Acceleration cue: {accel}.",
            "INTERPRETATION: this is a per-address pattern forecast, not "
            "a city-wide trend. Zero-history addresses get a zero-baseline "
            "forecast (legitimate); the more relevant cite is when there's "
            "a multi-month complaint history that the model is extrapolating.",
        ]
        docs.append(_doc_message("ttm_311_forecast", body))

    # FloodNet sensor forecast — TTM r2 on the nearest sensor's
    # historical flood-event recurrence. Reuses the (512, 96)
    # singleton from ttm_311_forecast — same model class, different
    # data stream. Doc id includes the sensor deployment id so the
    # citation is unambiguous when multiple sensors are nearby.
    fnf = state.get("floodnet_forecast")
    if not out_of_nyc and fnf and fnf.get("available"):
        accel = ("YES — next-28-day forecast > 50% above prior-28-day "
                 "observed count"
                 if fnf.get("accelerating")
                 else "no — forecast in line with recent baseline")
        doc_id = fnf.get("doc_id") or "floodnet_forecast"
        body = [
            "Source: FloodNet NYC ultrasonic depth sensor network "
            "(api.floodnet.nyc) historical flood events, forecast by "
            "IBM Granite TimeSeries TTM r2 (Ekambaram et al. 2024, "
            "NeurIPS).",
            f"Sensor: {fnf['sensor_name']} (deployment "
            f"{fnf['sensor_id']}) at {fnf['sensor_street']}, "
            f"{fnf['sensor_borough']}.",
            f"Distance from query: {fnf['distance_from_query_m']} m.",
            f"History window: {fnf['history_window_days']} days; "
            f"{fnf['history_total_events']} flood events observed total, "
            f"{fnf['history_recent_28d_events']} in the most recent "
            f"28 days.",
            f"Forecast horizon: {fnf['forecast_horizon_days']} days.",
            f"Forecast next-28-day expected events: "
            f"{fnf['forecast_28d_expected_events']}.",
            f"Forecast peak day offset: +{fnf['forecast_peak_day_offset']} "
            f"(value {fnf['forecast_peak_day_value']}).",
            f"Acceleration cue: {accel}.",
            "INTERPRETATION: this is a per-sensor recurrence forecast — "
            "expected count of labelled flood events at that specific "
            "deployment over the horizon, not an above-curb-event "
            "probability. CUSP/Brooklyn College operates the sensors and "
            "publishes the historical events; this forecast is Riprap's "
            "extension to the same dataset, computable per-query.",
        ]
        docs.append(_doc_message(doc_id, body))

    # Granite TTM r2 — Battery surge fine-tune (msradam/Granite-TTM-r2-
    # Battery-Surge, Apache-2.0, fine-tuned on AMD MI300X). Hourly
    # cadence, 96 h horizon — distinct from the existing zero-shot
    # ttm_forecast above, which runs at 6-min cadence over a 9.6 h
    # horizon. Both can fire on the same query.
    tbs = state.get("ttm_battery_surge")
    if (not out_of_nyc and tbs and tbs.get("available")
            and tbs.get("interesting")):
        body = [
            "Source: msradam/Granite-TTM-r2-Battery-Surge (Apache-2.0). "
            "Fine-tune of ibm-granite/granite-timeseries-ttm-r2 trained "
            "on AMD Instinct MI300X via AMD Developer Cloud. Test MAE "
            "0.1091 m, -41% vs persistence and -25% vs zero-shot TTM r2.",
            f"Gauge: {tbs['station_name']} (NOAA {tbs['station_id']}).",
            f"Context window: {tbs['context_hours']} hours "
            f"(~{tbs['context_hours']/24:.1f} days) of hourly surge "
            "residual (verified water level minus harmonic tide).",
            f"Forecast horizon: {tbs['horizon_hours']} hours "
            f"(~{tbs['horizon_hours']/24:.1f} days ahead).",
            f"Recent residual: {tbs['history_recent_m']} m.",
            f"Recent peak |residual| in context: "
            f"{tbs['history_peak_abs_m']} m.",
            f"Forecast peak surge residual: {tbs['forecast_peak_m']} m, "
            f"expected {tbs['forecast_peak_hours_ahead']} hours from "
            f"now (at {tbs['forecast_peak_time_utc']} UTC).",
            "INTERPRETATION: positive residual is the meteorological "
            "component (storm surge, atmospheric pressure, wind setup) "
            "on top of astronomical tide. The Battery is the dominant "
            "NYC harbor-entrance gauge — its surge characterises Sandy "
            "and Ida conditions citywide.",
        ]
        docs.append(_doc_message("ttm_battery", body))

    # ---- Policy context (RAG + GLiNER, ancillary to the four Stones) ---
    # Retrieved policy paragraphs and GLiNER typed-entity extractions.
    # These don't belong to a specific Stone — they ground the
    # briefing's "Policy context" section.
    rag_hits = [] if out_of_nyc else (state.get("rag") or [])
    for h in rag_hits:
        body = [
            f"Source: {h['citation']}, page {h['page']}.",
            f"Retrieved passage (verbatim): {h['text']}",
        ]
        docs.append(_doc_message(h["doc_id"], body))

    # Per-source structured fields the reconciler can cite as
    # [gliner_<source>] in addition to the parent [rag_<source>].
    gliner = (state.get("gliner") or {})
    if not out_of_nyc and gliner:
        for source, payload in gliner.items():
            ents = payload.get("entities") or []
            if not ents:
                continue
            body = [
                f"Source PDF (parent retriever doc_id: {payload.get('rag_doc_id', '?')}, "
                f"title: {payload.get('title', '?')}).",
                f"Paragraph excerpt: \"{payload.get('paragraph_excerpt', '')}\"",
                "Typed entities extracted by GLiNER (verbatim spans):",
            ]
            for e in ents:
                body.append(
                    f"  - [{e['label']}] {e['text']}  (score={e.get('score', 0):.2f})"
                )
            docs.append(_doc_message(f"gliner_{source}", body))

    return docs


def reconcile(state: dict[str, Any], model: str = OLLAMA_MODEL,
              return_audit: bool = False, on_token=None):
    """Run Granite reconciliation, then drop sentences with ungrounded numbers.

    If on_token is provided, the model is run in streaming mode and
    on_token(delta) is called for each chunk as Granite generates.

    If return_audit=True, returns (paragraph, audit_dict) where audit_dict
    has 'raw' (Granite's original output) and 'dropped' (list of dropped
    sentences with their ungrounded numeric tokens).
    """
    doc_msgs = build_documents(state)
    if not doc_msgs:
        msg = "No grounded data available for this address."
        return (msg, {"raw": msg, "dropped": []}) if return_audit else msg

    messages = doc_msgs + [
        {"role": "system", "content": EXTRA_SYSTEM_PROMPT},
        {"role": "user", "content": "Write the cited paragraph now."},
    ]
    # single_address: 13 specialists may fire, doc bodies are short.
    # num_ctx 4096 covers ~700 system + ~2500 docs. num_predict 400 caps
    # the 4-section briefing at ~300-350 tokens.
    OPTS = {"temperature": 0, "num_ctx": 4096, "num_predict": 400}
    if on_token is None:
        resp = llm.chat(model=model, messages=messages, options=OPTS)
        raw = resp["message"]["content"].strip()
    else:
        chunks: list[str] = []
        for chunk in llm.chat(model=model, messages=messages, stream=True,
                                 options=OPTS):
            delta = (chunk.get("message") or {}).get("content") or ""
            if delta:
                chunks.append(delta)
                on_token(delta)
        raw = "".join(chunks).strip()

    cleaned, dropped = verify_paragraph(raw, doc_msgs)
    if return_audit:
        return cleaned, {"raw": raw, "dropped": dropped}
    return cleaned
