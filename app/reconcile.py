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

import ollama

log = logging.getLogger("riprap.reconcile")

OLLAMA_MODEL = os.environ.get("HELIOS_NYC_OLLAMA_MODEL", "granite4.1:3b")

# Granite auto-prepends its own grounded-generation system prompt when the
# message list contains "document" roles. This adds *additional* rules.
EXTRA_SYSTEM_PROMPT = """You are Riprap's grounded reconciler. Produce a SHORT factual paragraph (4-7 sentences) summarising flood risk at a NYC address. Use ONLY information from the documents provided.

Citation format — STRICT:
- After every factual or numerical claim, cite the originating document by its doc_id in square brackets, e.g. [sandy] or [floodnet].
- Use square brackets [ and ]. Never parentheses, never the word "source".
- A claim drawn from multiple documents may carry multiple tags, e.g. [sandy][floodnet].

Hard rules — non-negotiable:
- Copy numerical values verbatim from documents. Do not round.
- Do NOT name a specific weather event (Hurricane Sandy, Ida, Henri, Ophelia, etc.) unless THIS document set explicitly mentions that event applies to THIS address. The fact that a RAG passage discusses an event in passing is NOT licence to apply it to the address. If you mention an event, you must cite the specific document supporting that the event affected this address.
- Do NOT invent dates, sensor IDs, hazard categories, or street/neighborhood names beyond what the documents contain.
- For RAG documents whose id starts with `rag_`: paraphrase the retrieved passage at the policy / agency level — talk about what the agency report SAYS about flood risk in general or for this asset class — do not assert findings the report did not make about this specific address. Cite with the doc_id.
- Stay neutral. No editorialising. No future speculation.
- If no documents are present, output exactly: No grounded data available for this address.

Microtopo interpretation hint:
- A LOW percentile (e.g. 5%) means the address is at a topographic LOW POINT in its surroundings — water tends to pool there. A HIGH percentile (e.g. 80%) means the address sits on relatively HIGH ground. Get this direction right or omit the percentile.
"""


# ---- Hallucination guardrail: numeric grounding post-check -----------------

_NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[])")
# Strings that are too generic to be useful as grounding evidence; ignore
# them when matching numeric tokens.
_TRIVIAL_NUMS = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "100"}


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


def verify_paragraph(paragraph: str, doc_msgs: list[dict]) -> tuple[str, list[dict]]:
    """Drop sentences whose numeric tokens don't appear in any source doc.

    Returns (clean_paragraph, dropped_sentences_with_reason). Sentences are
    split on sentence-end punctuation followed by whitespace + a capital
    letter or '['. The bracketed-citation tags `[doc_id]` and document
    roles in the source message list are excluded from the haystack so we
    don't accidentally accept fabricated values that happen to be
    substrings of doc_ids.
    """
    haystack = _docs_corpus(doc_msgs)

    sentences = _SENTENCE_END_RE.split(paragraph.strip())
    kept: list[str] = []
    dropped: list[dict] = []

    for sent in sentences:
        sent_stripped = sent.strip()
        if not sent_stripped:
            continue
        # remove citation tags before extracting numbers (they're not claims)
        sent_no_cites = re.sub(r"\[[a-z0-9_]+\]", "", sent_stripped, flags=re.I)
        nums = _NUM_RE.findall(sent_no_cites)
        ungrounded = []
        for n in nums:
            if n in _TRIVIAL_NUMS:
                continue
            forms = _normalize_num(n)
            if not any(f in haystack for f in forms):
                ungrounded.append(n)

        if ungrounded:
            dropped.append({"sentence": sent_stripped, "ungrounded_numbers": ungrounded})
            log.warning("dropped ungrounded sentence: %r (nums: %s)", sent_stripped, ungrounded)
            continue
        kept.append(sent_stripped)

    cleaned = " ".join(kept).strip()
    if not cleaned:
        cleaned = "Could not produce a verifiable summary; see the data panels."
    return cleaned, dropped


def _doc_message(doc_id: str, body_lines: list[str]) -> dict:
    """One Granite-native document message. The doc_id rides on the role
    suffix; Ollama's template uses it as the document title and lifts the
    pair into the <documents> block."""
    return {"role": f"document {doc_id}", "content": "\n".join(body_lines)}


def build_documents(state: dict[str, Any]) -> list[dict]:
    """Build Granite-native document-role messages, gated so absent
    specialists emit no document at all."""
    docs: list[dict] = []

    geo = state.get("geocode")
    if geo:
        body = [
            f"Source: NYC DCP Geosearch (geosearch.planninglabs.nyc).",
            f"Resolved address: {geo['address']}.",
            f"Borough: {geo.get('borough') or 'unknown'}.",
            f"Coordinates: {geo['lat']:.5f} N, {geo['lon']:.5f} W.",
        ]
        if geo.get("bbl"):
            body.append(f"BBL (tax-lot id): {geo['bbl']}.")
        docs.append(_doc_message("geocode", body))

    # Gate: only emit the Sandy doc when the address is actually inside the
    # 2012 extent. Granite has a strong training prior associating NYC + flood
    # + Brooklyn with Sandy and will misread "outside" as "inside" if given
    # the chance — silence-over-confabulation rules.
    if state.get("sandy") is True:
        body = [
            "Source: NYC Sandy Inundation Zone (NYC OpenData 5xsi-dfpx, "
            "empirical extent of areas flooded by Hurricane Sandy in 2012).",
            "FACT: The address is LOCATED WITHIN this empirical 2012 inundation extent.",
            "INTERPRETATION: Hurricane Sandy did flood this address (or this immediate parcel) on October 29-30, 2012. This is a historical fact, not a model prediction.",
            "Do not state the opposite. The address is inside the Sandy inundation zone.",
        ]
        docs.append(_doc_message("sandy", body))

    dep = state.get("dep")
    if dep:
        for scen, info in dep.items():
            if info.get("depth_class", 0) > 0:
                body = [
                    f"Source: {info['citation']}.",
                    f"Address inside scenario footprint: yes.",
                    f"Modeled depth class: {info['depth_label']}.",
                ]
                docs.append(_doc_message(scen, body))

    fn = state.get("floodnet")
    if fn and fn.get("n_sensors", 0) > 0:
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

    pw = state.get("prithvi_water")
    if pw and pw.get("nearest_distance_m") is not None:
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

    ida = state.get("ida_hwm")
    if ida and (ida.get("n_within_radius") or 0) > 0:
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

    mt = state.get("microtopo")
    if mt:
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

    rag_hits = state.get("rag") or []
    for h in rag_hits:
        body = [
            f"Source: {h['citation']}, page {h['page']}.",
            f"Retrieved passage (verbatim): {h['text']}",
        ]
        docs.append(_doc_message(h["doc_id"], body))

    nyc311 = state.get("nyc311")
    if nyc311 and nyc311.get("n", 0) > 0:
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

    return docs


def reconcile(state: dict[str, Any], model: str = OLLAMA_MODEL,
              return_audit: bool = False):
    """Run Granite reconciliation, then drop sentences with ungrounded numbers.

    If return_audit=True, returns (paragraph, audit_dict) where audit_dict
    has 'raw' (Granite's original output) and 'dropped' (list of dropped
    sentences with their ungrounded numeric tokens).
    """
    doc_msgs = build_documents(state)
    if not doc_msgs:
        msg = "No grounded data available for this address."
        return (msg, {"raw": msg, "dropped": []}) if return_audit else msg

    messages = (
        doc_msgs
        + [
            {"role": "system", "content": EXTRA_SYSTEM_PROMPT},
            {"role": "user", "content": "Write the cited paragraph now."},
        ]
    )
    resp = ollama.chat(
        model=model,
        messages=messages,
        options={"temperature": 0, "num_ctx": 8192},
    )
    raw = resp["message"]["content"].strip()
    cleaned, dropped = verify_paragraph(raw, doc_msgs)

    if return_audit:
        return cleaned, {"raw": raw, "dropped": dropped}
    return cleaned
