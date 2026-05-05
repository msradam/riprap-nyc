// Riprap web client — subscribes to SSE, lights up FSM steps, renders the report.

const STEP_LABELS = {
  geocode:                ["Geocode (DCP Geosearch)",          "address → lat/lon, BBL"],
  sandy_inundation:       ["Sandy Inundation (NYC OD)",        "empirical 2012 extent"],
  dep_stormwater:         ["DEP Stormwater Maps",              "pluvial scenarios + 2080 SLR"],
  floodnet:               ["FloodNet sensor network",          "live ultrasonic depth sensors"],
  nyc311:                 ["NYC 311 archive",                  "flood complaints in buffer"],
  noaa_tides:             ["NOAA Tides & Currents (live)",     "Battery / Kings Pt / Sandy Hook water level"],
  nws_alerts:             ["NWS Public Alerts (live)",         "active flood-relevant alerts at point"],
  nws_obs:                ["NWS METAR observation (live)",     "nearest ASOS recent precipitation"],
  ttm_forecast:           ["Granite TTM r2 (TimeSeries)",      "9.6h surge-residual nowcast at the Battery"],
  microtopo_lidar:        ["LiDAR terrain (DEM + TWI + HAND)", "USGS 3DEP DEM + whitebox-workflows hydrology"],
  ida_hwm_2021:           ["Ida 2021 high-water marks",        "USGS empirical post-event extent"],
  prithvi_eo_v2:          ["Prithvi-EO 2.0 (300M, NASA/IBM)",  "Sen1Floods11 satellite water segmentation"],
  rag_granite_embedding:  ["Granite Embedding 278M (RAG)",     "policy corpus retrieval"],
  reconcile_granite41:    ["Granite 4.1 reconcile (local)",    "document-grounded synthesis"],
};

const STEPS_ORDER = [
  "geocode", "sandy_inundation", "dep_stormwater", "floodnet", "nyc311",
  "noaa_tides", "nws_alerts", "nws_obs", "ttm_forecast",
  "microtopo_lidar", "ida_hwm_2021", "prithvi_eo_v2",
  "rag_granite_embedding", "reconcile_granite41",
];

const $ = (s) => document.querySelector(s);

let evtSrc = null;
let map = null;
let mapInit = false;

const MAP_STYLE = {
  version: 8,
  sources: {
    carto: {
      type: "raster",
      tiles: ["https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors © CARTO",
    },
  },
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#fafbfd" } },
    { id: "carto", type: "raster", source: "carto" },
  ],
};

function ensureMap() {
  if (mapInit) return;
  mapInit = true;
  map = new maplibregl.Map({
    container: "map",
    style: MAP_STYLE,
    center: [-74.0, 40.72],
    zoom: 10,
    attributionControl: { compact: true },
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "top-right");

  map.on("load", async () => {
    // Sandy + DEP layers — empty until first query (we clip per-address)
    map.addSource("sandy", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    map.addLayer({
      id: "sandy-fill", type: "fill", source: "sandy",
      paint: { "fill-color": "#fc5d52", "fill-opacity": 0.28 },
    });
    map.addLayer({
      id: "sandy-line", type: "line", source: "sandy",
      paint: { "line-color": "#fc5d52", "line-width": 0.6, "line-opacity": 0.6 },
    });

    map.addSource("dep", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    map.addLayer({
      id: "dep-fill", type: "fill", source: "dep",
      paint: {
        "fill-color": [
          "match", ["get", "Flooding_Category"],
          1, "#568adf", 2, "#1642DF", 3, "#031553", "#568adf",
        ],
        "fill-opacity": 0.32,
      },
    });

    // Prithvi-EO 2.0 satellite water polygons. Visually distinct from the
    // modeled DEP/Sandy layers — teal outline + low fill says "what the
    // satellite saw" not "what FEMA/DEP modeled".
    map.addSource("prithvi", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    map.addLayer({
      id: "prithvi-fill", type: "fill", source: "prithvi",
      paint: { "fill-color": "#0d9488", "fill-opacity": 0.18 },
    });
    map.addLayer({
      id: "prithvi-line", type: "line", source: "prithvi",
      paint: { "line-color": "#0d9488", "line-width": 1.2, "line-opacity": 0.85 },
    });

    // empty floodnet + addr sources, populated per query
    map.addSource("floodnet", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    map.addLayer({
      id: "floodnet-circles", type: "circle", source: "floodnet",
      paint: {
        "circle-radius": 6,
        "circle-color": ["case", [">", ["get", "n_events_3y"], 0], "#fc5d52", "#1a8754"],
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 1.8,
      },
    });
    map.on("click", "floodnet-circles", (e) => {
      const f = e.features[0];
      const p = f.properties;
      new maplibregl.Popup()
        .setLngLat(f.geometry.coordinates)
        .setHTML(`<b>${p.name}</b><br>${p.street}<br>events 3y: ${p.n_events_3y}<br>peak: ${p.peak_depth_mm} mm`)
        .addTo(map);
    });

    map.addSource("addr", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    map.addLayer({
      id: "addr-marker", type: "circle", source: "addr",
      paint: {
        "circle-radius": 9,
        "circle-color": "#1642DF",
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 2.5,
      },
    });
  });
}

async function updateMapForResult(geo) {
  ensureMap();
  if (!map.loaded()) {
    await new Promise(res => map.once("load", res));
  }
  // address marker
  map.getSource("addr").setData({
    type: "FeatureCollection",
    features: [{
      type: "Feature",
      geometry: { type: "Point", coordinates: [geo.lon, geo.lat] },
      properties: { address: geo.address },
    }],
  });
  // load all per-address layers in parallel
  const url = (p) => `${p}?lat=${geo.lat}&lon=${geo.lon}&r=1500`;
  const [sandy, dep, prithvi, fn] = await Promise.all([
    fetch(url("/api/layers/sandy")).then(r => r.json()).catch(() => null),
    fetch(url("/api/layers/dep_extreme_2080")).then(r => r.json()).catch(() => null),
    fetch(url("/api/layers/prithvi_water")).then(r => r.json()).catch(() => null),
    fetch(`/api/floodnet_near?lat=${geo.lat}&lon=${geo.lon}&r=1000`).then(r => r.json()).catch(() => null),
  ]);
  if (sandy)   map.getSource("sandy").setData(sandy);
  if (dep)     map.getSource("dep").setData(dep);
  if (prithvi) map.getSource("prithvi").setData(prithvi);
  if (fn)      map.getSource("floodnet").setData(fn);

  // Hide the Prithvi legend item when no polygons render here. The
  // model only marks satellite-observed water bodies — for landlocked
  // addresses there's nothing to draw, and an empty legend entry would
  // confuse rather than inform.
  const prithviLegend = document.querySelector(".legend .sw.prithvi");
  if (prithviLegend) {
    const hasPrithvi = prithvi && (prithvi.features || []).length > 0;
    prithviLegend.parentElement.style.display = hasPrithvi ? "" : "none";
  }

  map.flyTo({ center: [geo.lon, geo.lat], zoom: 14, speed: 1.2 });
}

function resetUI(query) {
  $("#trace").classList.remove("hidden");
  $("#report").classList.add("hidden");
  $("#meta").classList.add("hidden");
  $("#paragraph").innerHTML = "";
  const kf = $("#keyFindings"); if (kf) kf.innerHTML = "";
  const ec = $("#evidenceCards"); if (ec) ec.innerHTML = "";
  const pl = $("#policyList"); if (pl) pl.innerHTML = "";
  const ps = $("#policySection"); if (ps) ps.classList.add("hidden");
  const s = $("#sources"); if (s) s.innerHTML = "";
  $("#addr").innerHTML = "";
  CITE_INDEX = {};

  const ul = $("#steps");
  ul.innerHTML = "";
  for (const sid of STEPS_ORDER) {
    const [lbl, hint] = STEP_LABELS[sid] || [sid, ""];
    const li = document.createElement("li");
    li.id = "step-" + sid;
    li.className = "pending";
    li.innerHTML = `
      <span class="icon">○</span>
      <div>
        <div class="label">${lbl}</div>
        <div class="meta">${hint}</div>
      </div>
      <span class="meta time"></span>`;
    ul.appendChild(li);
  }
  // mark first one running
  $("#step-" + STEPS_ORDER[0]).classList.replace("pending", "running");
}

function markStep(stepId, ev) {
  const li = document.getElementById("step-" + stepId);
  if (!li) return;
  li.className = ev.ok ? "ok" : "err";
  li.querySelector(".icon").textContent = ev.ok ? "✓" : "✗";
  if (ev.elapsed_s != null) {
    li.querySelector(".time").textContent = ev.elapsed_s.toFixed(2) + "s";
  }
  if (ev.result) {
    let div = li.querySelector(".result");
    if (!div) {
      div = document.createElement("div");
      div.className = "result";
      li.appendChild(div);
    }
    div.textContent = formatResult(ev.result);
  } else if (ev.err) {
    let div = li.querySelector(".result");
    if (!div) {
      div = document.createElement("div");
      div.className = "result";
      li.appendChild(div);
    }
    div.textContent = "error: " + ev.err;
  }

  // mark next pending step running
  const idx = STEPS_ORDER.indexOf(stepId);
  if (idx >= 0 && idx + 1 < STEPS_ORDER.length) {
    const next = document.getElementById("step-" + STEPS_ORDER[idx + 1]);
    if (next && next.classList.contains("pending")) {
      next.classList.replace("pending", "running");
    }
  }
}

function formatResult(r) {
  if (typeof r !== "object") return String(r);
  return Object.entries(r)
    .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`)
    .join(" · ");
}

// Map doc_id -> footnote number for the current report; built fresh each query
let CITE_INDEX = {};

function rewriteCitations(text) {
  // Replace [doc_id] with <span class="cite" title="...">N</span> using the
  // CITE_INDEX. doc_ids not in the index get their first appearance assigned.
  return text.replace(/\[([a-z0-9_]+)\]/gi, (_, d) => {
    const norm = d.toLowerCase();
    if (CITE_INDEX[norm] == null) {
      CITE_INDEX[norm] = Object.keys(CITE_INDEX).length + 1;
    }
    const n = CITE_INDEX[norm];
    return `<span class="cite" title="source ${n} — ${SOURCE_LABELS[norm] || norm}">${n}</span>`;
  });
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderMarkdown(text) {
  // Tiny safe markdown subset:
  //   **Header.**          (on its own line) -> <h4 class="rsum-h">Header</h4>
  //   **inline bold**       (mid-sentence)  -> <strong>...</strong>
  // We escape HTML first to defang any injection in model output.
  const lines = text.split("\n");
  const out = [];
  let bodyBuf = [];
  const flushBody = () => {
    if (!bodyBuf.length) return;
    const body = bodyBuf.join(" ").trim();
    bodyBuf = [];
    if (!body) return;
    const safe = escapeHtml(body)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    out.push(`<p class="rsum-p">${safe}</p>`);
  };
  const headerRe = /^\s*\*\*([A-Z][A-Za-z\s/]+)\.\*\*\s*$/;
  for (const line of lines) {
    const m = line.match(headerRe);
    if (m) {
      flushBody();
      out.push(`<h4 class="rsum-h">${escapeHtml(m[1])}</h4>`);
    } else {
      bodyBuf.push(line);
    }
  }
  flushBody();
  return out.join("");
}

function renderParagraph(text) {
  // Build markdown structure FIRST, then rewrite citations inside. Citations
  // are bracketed tokens like [sandy] which don't conflict with our markdown.
  $("#paragraph").innerHTML = rewriteCitations(renderMarkdown(text));
}

const SOURCE_LABELS = {
  geocode:                "NYC DCP Geosearch",
  sandy:                  "NYC OpenData 5xsi-dfpx — Sandy 2012 inundation",
  dep_extreme_2080:       "NYC DEP Stormwater — Extreme 3.66 in/hr + 2080 SLR",
  dep_moderate_2050:      "NYC DEP Stormwater — Moderate 2.13 in/hr + 2050 SLR",
  dep_moderate_current:   "NYC DEP Stormwater — Moderate 2.13 in/hr current",
  floodnet:               "FloodNet NYC — live ultrasonic sensor network",
  nyc311:                 "NYC 311 (Socrata erm2-nwe9) — flood descriptors",
  microtopo:              "USGS 3DEP 30 m DEM via py3dep",
  ida_hwm:                "USGS STN — Hurricane Ida 2021 HWMs (Event 312, NY)",
  prithvi_water:          "Prithvi-EO 2.0 (300M, NASA/IBM) — Hurricane Ida 2021 pre/post HLS diff (Aug 25 vs Sep 2)",
  rag_dep_2013:           "NYC DEP Wastewater Resiliency Plan (2013)",
  rag_nycha:              "NYCHA — Flood Resilience: Lessons Learned",
  rag_coned:              "Con Edison Climate Change Resilience Plan (Case 22-E-0222)",
  rag_mta:                "MTA Climate Resilience Roadmap (Oct 2025)",
  rag_comptroller:        "NYC Comptroller — \"Is NYC Ready for Rain?\" (2024)",
  noaa_tides:             "NOAA CO-OPS Tides & Currents — live water level (6-min)",
  nws_alerts:             "NWS Public Alerts API — active flood-relevant alerts",
  nws_obs:                "NWS Station Observations — nearest ASOS hourly METAR",
  ttm_forecast:           "Granite TimeSeries TTM r2 — surge-residual nowcast (Ekambaram et al. 2024, NeurIPS)",
};

// ----------------------------------------------------------------------
// CIVIC ASSESSMENT REPORT — header strip, tier badge, key findings,
// evidence cards, policy quotes, methodology footer.
// ----------------------------------------------------------------------

// Tier meta — uses the new composite breakpoints, mirrors app/score.py.
// Tooltip copy explicitly states scope: exposure, not damage probability.
function tierMeta(tier) {
  if (tier === 1) return {tier: 1, label: "High exposure",
    help: "Multiple sub-indices saturated; empirical and/or modeled scenarios both indicate substantial exposure. Not a damage probability."};
  if (tier === 2) return {tier: 2, label: "Elevated exposure",
    help: "At least one sub-index near saturation; significant overlap with empirical or modeled scenarios. Not a damage probability."};
  if (tier === 3) return {tier: 3, label: "Moderate exposure",
    help: "Partial signals across categories; scenario- or neighborhood-specific exposure. Not a damage probability."};
  if (tier === 4) return {tier: 4, label: "Limited exposure",
    help: "A single contextual signal; no positive scenario hits."};
  return {tier: 0, label: "No flagged exposure",
    help: "No positive flood signal across the assessed sources."};
}

// ---- Score computation: mirrors app/score.py.composite() exactly ---------
// Three thematic sub-indices, equal weights within each, max-empirical
// floor. Live signals (NWS alerts, surge, precip) are NOT in this score
// per IPCC AR6 WG II's distinction between exposure (static) and event
// occurrence (live).
const REG_W = {
  fema_1pct: 1.0, fema_02pct: 0.5,
  dep_moderate_2050: 0.75, dep_extreme_2080: 0.50, dep_tidal_2050: 0.75,
};
const HYD_W = {
  hand_band: 1.0, twi_quartile: 0.5,
  elev_pct_200m_inv: 0.5, elev_pct_750m_inv: 0.5, basin_relief_band: 0.25,
};
const EMP_W = {
  sandy: 1.0,
  ida_hwm_within_100m: 1.0, ida_hwm_within_800m: 0.5,
  prithvi_polygon: 0.75, complaints_band: 0.75, floodnet_trigger: 0.75,
};

const handBand   = (h)   => h == null ? 0 : (h < 1 ? 1 : h < 3 ? 0.66 : h < 10 ? 0.33 : 0);
const pctInvBand = (p)   => p == null ? 0 : (p < 10 ? 1 : p < 25 ? 0.66 : p < 50 ? 0.33 : 0);
const twiBand    = (t)   => t == null ? 0 : (t >= 12 ? 1 : t >= 10 ? 0.66 : t >= 8 ? 0.33 : 0);
const reliefBand = (r)   => r == null ? 0 : (r >= 8 ? 1 : r >= 4 ? 0.66 : r >= 2 ? 0.33 : 0);
const complBand  = (n)   => !n ? 0 : (n >= 10 ? 1 : n >= 3 ? 0.66 : 0.33);
const sumW = (w) => Object.values(w).reduce((a, b) => a + b, 0);

function computeComposite(ev) {
  const dep = ev.dep || {};
  const mt  = ev.microtopo || {};
  const ida = ev.ida_hwm || {};
  const pw  = ev.prithvi_water || {};

  // Build the signal dict in the shape app/score.py expects.
  const s = {
    // Regulatory
    fema_1pct:           false,            // not yet wired in this build
    fema_02pct:          false,
    dep_moderate_2050:   (dep.dep_moderate_2050?.depth_class || 0) > 0,
    dep_extreme_2080:    (dep.dep_extreme_2080?.depth_class || 0) > 0,
    dep_tidal_2050:      false,            // tidal scenario not in current FSM
    // Hydrological
    hand_m:              mt.hand_m,
    twi:                 mt.twi,
    rel_elev_pct_200m:   mt.rel_elev_pct_200m,
    rel_elev_pct_750m:   mt.rel_elev_pct_750m,
    basin_relief_m:      mt.basin_relief_m,
    // Empirical
    sandy:               !!ev.sandy,
    ida_hwm_within_100m: (ida.nearest_dist_m != null && ida.nearest_dist_m < 100) ||
                         (ida.n_within_radius || 0) > 0 && (ida.nearest_dist_m || 9999) < 100,
    ida_hwm_within_800m: (ida.n_within_radius || 0) > 0,
    prithvi_polygon:     !!pw.inside_water_polygon,
    complaints_count:    ev.nyc311?.n || 0,
    floodnet_trigger:    (ev.floodnet?.n_flood_events_3y || 0) > 0,
  };

  // Regulatory sub-index (binary signals)
  let regRaw = 0;
  for (const [k, w] of Object.entries(REG_W)) regRaw += s[k] ? w : 0;
  const reg = regRaw / sumW(REG_W);

  // Hydrological sub-index (banded continuous)
  const hydBands = {
    hand_band:         handBand(s.hand_m),
    twi_quartile:      twiBand(s.twi),
    elev_pct_200m_inv: pctInvBand(s.rel_elev_pct_200m),
    elev_pct_750m_inv: pctInvBand(s.rel_elev_pct_750m),
    basin_relief_band: reliefBand(s.basin_relief_m),
  };
  let hydRaw = 0;
  for (const [k, w] of Object.entries(HYD_W)) hydRaw += w * hydBands[k];
  const hyd = hydRaw / sumW(HYD_W);

  // Empirical sub-index
  const empVals = {
    sandy:               s.sandy ? 1 : 0,
    ida_hwm_within_100m: s.ida_hwm_within_100m ? 1 : 0,
    ida_hwm_within_800m: s.ida_hwm_within_800m ? 1 : 0,
    prithvi_polygon:     s.prithvi_polygon ? 1 : 0,
    complaints_band:     complBand(s.complaints_count),
    floodnet_trigger:    s.floodnet_trigger ? 1 : 0,
  };
  let empRaw = 0;
  for (const [k, w] of Object.entries(EMP_W)) empRaw += w * empVals[k];
  const emp = empRaw / sumW(EMP_W);

  const composite = reg + hyd + emp;

  // Tier breakpoints (mirror score.py)
  let tier = 0;
  if      (composite >= 1.50) tier = 1;
  else if (composite >= 1.00) tier = 2;
  else if (composite >= 0.50) tier = 3;
  else if (composite >= 0.01) tier = 4;

  // Max-empirical floor: Sandy or HWM-within-100m → tier ≤ 2
  const floorApplied = !!(s.sandy || s.ida_hwm_within_100m);
  if (floorApplied && (tier === 0 || tier > 2)) tier = 2;

  return {
    subindices: {regulatory: reg, hydrological: hyd, empirical: emp},
    composite, tier, floorApplied,
  };
}

// Backward-compat shim: places that called computeScore() now read .tier.
function computeScore(ev) { return computeComposite(ev).tier; }

function renderHeader(ev) {
  const geo = ev.geocode || {};
  $("#reportAddr").textContent = geo.address || "(unresolved)";
  $("#reportBoro").textContent = geo.borough || "—";
  $("#reportBbl").textContent  = geo.bbl || "—";
  $("#reportTs").textContent   = new Date().toISOString().slice(0,10);
}

function renderTier(ev) {
  const c = computeComposite(ev);
  const m = tierMeta(c.tier);
  const badge = $("#tierBadge");
  badge.className = "tier-badge t-" + m.tier;
  $("#tierNum").textContent = m.tier;
  const floor = c.floorApplied ? " · empirical floor" : "";
  $("#tierLabel").textContent = `Tier ${m.tier} — ${m.label}${floor}`;
  $("#tierHelp").textContent  = m.help;
}

function renderKeyFindings(ev) {
  const dl = $("#keyFindings");
  dl.innerHTML = "";
  const rows = [];

  rows.push(["Sandy 2012 zone",
    ev.sandy ? "INSIDE" : "outside",
    ev.sandy ? "hit" : "miss"]);

  const dep = ev.dep || {};
  const dHit = Object.entries(dep).find(([_, v]) => (v.depth_class || 0) > 0);
  if (dHit) {
    const [scen, v] = dHit;
    const lbl = scen.replace("dep_", "").replace(/_/g, " ").toUpperCase();
    rows.push(["DEP scenario", `${lbl} — ${v.depth_label}`, "hit"]);
  } else {
    rows.push(["DEP scenarios", "outside all 3", "miss"]);
  }

  const mt = ev.microtopo;
  if (mt) {
    rows.push(["Elevation",
      `${mt.point_elev_m} m above sea level`, ""]);
    if (mt.hand_m != null) {
      rows.push(["Height Above Drainage", `${mt.hand_m} m  (HAND)`, ""]);
    }
    if (mt.twi != null) {
      rows.push(["Topographic Wetness Index",
        `${mt.twi}  (${mt.twi >= 14 ? "very high" : mt.twi >= 10 ? "high" : mt.twi >= 6 ? "moderate" : "low"})`, ""]);
    }
  }

  const fn = ev.floodnet;
  if (fn && fn.n_sensors > 0) {
    rows.push(["FloodNet (3 yr)",
      `${fn.n_flood_events_3y} events across ${fn.n_sensors} sensors`,
      fn.n_flood_events_3y > 0 ? "hit" : ""]);
  }

  const ida = ev.ida_hwm;
  if (ida && ida.n_within_radius > 0) {
    const ht = ida.max_height_above_gnd_ft != null
      ? `, max ${ida.max_height_above_gnd_ft} ft above ground` : "";
    rows.push(["Hurricane Ida 2021 HWMs",
      `${ida.n_within_radius} within ${ida.radius_m} m${ht}`, "hit"]);
  }

  const pw = ev.prithvi_water;
  if (pw && pw.nearest_distance_m != null) {
    rows.push(["Prithvi-EO Ida 2021",
      pw.inside_water_polygon
        ? "INSIDE inundation polygon"
        : `${pw.nearest_distance_m} m to nearest inundation polygon`,
      pw.inside_water_polygon ? "hit" : ""]);
  }

  const c311 = ev.nyc311;
  if (c311 && c311.n > 0) {
    rows.push(["311 flood complaints",
      `${c311.n} within ${c311.radius_m} m, last ${c311.years} yr`,
      c311.n >= 5 ? "hit" : ""]);
  }

  dl.innerHTML = rows.map(([k, v, cls]) =>
    `<dt>${k}</dt><dd${cls ? ` class="${cls}"` : ""}>${v}</dd>`
  ).join("");
}

function evCard({key, title, flag, rows, sourceText, sourceUrl, vintage, collapsed}) {
  // flag: "hit" | "note" | "miss"
  const inner = rows.map(([k, v]) =>
    `<dt>${k}</dt><dd>${v}</dd>`).join("");
  const foot = sourceUrl
    ? `<a href="${sourceUrl}" target="_blank">${sourceText}</a>${vintage ? " · " + vintage : ""}`
    : `${sourceText}${vintage ? " · " + vintage : ""}`;
  const cls = "ec" + (collapsed ? " collapsed" : "");
  return `<div class="${cls}" data-key="${key}">
    <div class="ec-head" onclick="this.parentElement.classList.toggle('collapsed')">
      <div class="ec-title"><span class="ec-flag ${flag}"></span>${title}</div>
      <div class="ec-toggle">▾</div>
    </div>
    <div class="ec-body"><dl>${inner}</dl></div>
    <div class="ec-foot">${foot}</div>
  </div>`;
}

function renderEvidence(ev) {
  const cards = [];

  if (ev.sandy != null) {
    cards.push(evCard({
      key: "sandy", title: "Sandy 2012 inundation",
      flag: ev.sandy ? "hit" : "miss",
      rows: [
        ["Inside extent", ev.sandy ? "yes" : "no"],
        ["Reference event", "Hurricane Sandy, 29-30 Oct 2012"],
      ],
      sourceText: "NYC OpenData 5xsi-dfpx",
      sourceUrl: "https://data.cityofnewyork.us/Environment/Sandy-Inundation-Zone/uyj8-7rv5",
      vintage: "empirical 2012 extent",
      collapsed: !ev.sandy,
    }));
  }

  const dep = ev.dep || {};
  const depRows = [];
  for (const [k, v] of Object.entries(dep)) {
    const label = k.replace("dep_", "").replace(/_/g, " ");
    depRows.push([label,
      v.depth_class > 0 ? `${v.depth_label}` : "outside"]);
  }
  if (depRows.length) {
    const anyHit = Object.values(dep).some(v => (v.depth_class || 0) > 0);
    cards.push(evCard({
      key: "dep", title: "DEP Stormwater scenarios",
      flag: anyHit ? "hit" : "miss",
      rows: depRows,
      sourceText: "NYC DEP via NYC OpenData 9i7c-xyvv",
      sourceUrl: "https://data.cityofnewyork.us/Environment/NYC-Stormwater-Flood-Maps/9i7c-xyvv",
      vintage: "modeled, 2021 release",
      collapsed: !anyHit,
    }));
  }

  const fn = ev.floodnet;
  if (fn && fn.n_sensors > 0) {
    const peak = fn.peak_event;
    const rows = [
      ["Sensors within 600 m", String(fn.n_sensors)],
      ["Flood events, last 3 yr", String(fn.n_flood_events_3y)],
    ];
    if (peak && peak.max_depth_mm) {
      rows.push(["Peak event", `${peak.max_depth_mm} mm depth at ${peak.deployment_id}`]);
      rows.push(["Peak date", (peak.start_time || "").slice(0, 10)]);
    }
    cards.push(evCard({
      key: "floodnet", title: "FloodNet sensor network",
      flag: fn.n_flood_events_3y > 0 ? "hit" : "note",
      rows,
      sourceText: "FloodNet NYC (NYU/CUNY/MOCEJ)",
      sourceUrl: "https://www.floodnet.nyc/",
      vintage: "live, queried per request",
      collapsed: false,
    }));
  }

  const ida = ev.ida_hwm;
  if (ida && ida.n_within_radius > 0) {
    const rows = [
      ["HWMs within 800 m", String(ida.n_within_radius)],
    ];
    if (ida.max_height_above_gnd_ft != null)
      rows.push(["Max above-ground height", `${ida.max_height_above_gnd_ft} ft`]);
    if (ida.max_elev_ft != null)
      rows.push(["Max HWM elevation", `${ida.max_elev_ft} ft`]);
    if (ida.nearest_dist_m != null)
      rows.push(["Nearest HWM site", `${ida.nearest_site || "—"} (${ida.nearest_dist_m} m)`]);
    cards.push(evCard({
      key: "ida_hwm", title: "Hurricane Ida 2021 high-water marks",
      flag: "hit", rows,
      sourceText: "USGS Short-Term Network, Event 312 (NY)",
      sourceUrl: "https://stn.wim.usgs.gov/",
      vintage: "post-event survey, Sep 2021",
      collapsed: false,
    }));
  }

  const mt = ev.microtopo;
  if (mt) {
    const rows = [
      ["Elevation", `${mt.point_elev_m} m`],
      ["Lower than (200 m)", `${mt.rel_elev_pct_200m}% of cells`],
      ["Lower than (750 m)", `${mt.rel_elev_pct_750m}% of cells`],
      ["Basin relief (750 m)", `${mt.basin_relief_m} m`],
    ];
    if (mt.hand_m != null) rows.push(["HAND", `${mt.hand_m} m`]);
    if (mt.twi != null)    rows.push(["TWI", String(mt.twi)]);
    cards.push(evCard({
      key: "microtopo", title: "LiDAR-derived terrain (DEM + TWI + HAND)",
      flag: "note", rows,
      sourceText: "USGS 3DEP DEM via py3dep · whitebox-workflows hydrology",
      sourceUrl: "https://www.usgs.gov/3d-elevation-program",
      vintage: "DEM 30 m, hydro-conditioned",
      collapsed: false,
    }));
  }

  const pw = ev.prithvi_water;
  if (pw && pw.nearest_distance_m != null) {
    const rows = [
      ["Inside Ida-attributable polygon", pw.inside_water_polygon ? "yes" : "no"],
      ["Nearest inundation polygon", `${pw.nearest_distance_m} m`],
      ["Inundation polygons within 500 m", String(pw.n_polygons_within_500m)],
      ["Pre-event scene", "HLS T18TWK 2021-08-25 (3% cloud)"],
      ["Post-event scene", "HLS T18TWK 2021-09-02 (1% cloud, ~12 h after Ida peak)"],
    ];
    cards.push(evCard({
      key: "prithvi_water",
      title: "Prithvi-EO 2.0 — Hurricane Ida flood inundation",
      flag: pw.inside_water_polygon ? "hit" : "note", rows,
      sourceText: "NASA / IBM Prithvi-EO-2.0-300M-TL-Sen1Floods11 (Apache-2.0, 300M params, run via TerraTorch on HLS Sentinel-2)",
      sourceUrl: "https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11",
      vintage: "Polygons = post-event water minus pre-event water. Sub-surface flooding (subway / basement) not visible to optical satellites.",
      collapsed: false,
    }));
  }

  const c311 = ev.nyc311;
  if (c311 && c311.n > 0) {
    const rows = [
      ["Total complaints", String(c311.n)],
      ["Buffer", `${c311.radius_m} m`],
      ["Window", `${c311.years} years`],
    ];
    if (c311.by_descriptor) {
      const top = Object.entries(c311.by_descriptor).slice(0, 3)
        .map(([k, v]) => `${v}× ${k.replace(/\s*\(.+?\)\s*$/, "").replace(/\s*\(SA\d?\)?$/, "")}`)
        .join("; ");
      if (top) rows.push(["Top descriptors", top]);
    }
    if (c311.by_year) {
      const yrs = Object.entries(c311.by_year).map(([y, n]) => `${y}: ${n}`).join(", ");
      rows.push(["By year", yrs]);
    }
    cards.push(evCard({
      key: "nyc311", title: "NYC 311 flood complaints",
      flag: c311.n >= 5 ? "hit" : "note", rows,
      sourceText: "NYC 311 (Socrata erm2-nwe9)",
      sourceUrl: "https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9",
      vintage: "live, last 5 years",
      collapsed: false,
    }));
  }

  // Live signals — refresh every query, may produce nothing on a calm day.
  const tides = ev.noaa_tides;
  if (tides && tides.observed_ft_mllw != null) {
    const rows = [
      ["Gauge", `${tides.station_name} (${tides.station_id})`],
      ["Distance to gauge", `${tides.distance_km} km`],
      ["Observed", `${tides.observed_ft_mllw} ft above MLLW`],
    ];
    if (tides.predicted_ft_mllw != null)
      rows.push(["Predicted (astro tide)", `${tides.predicted_ft_mllw} ft`]);
    if (tides.residual_ft != null)
      rows.push(["Residual (obs − pred)", `${tides.residual_ft >= 0 ? "+" : ""}${tides.residual_ft} ft`]);
    if (tides.obs_time)
      rows.push(["Observation time", tides.obs_time]);
    const flag = (tides.residual_ft != null && tides.residual_ft >= 1.0) ? "hit" : "note";
    cards.push(evCard({
      key: "noaa_tides",
      title: "NOAA Tides & Currents — live coastal water level",
      flag, rows,
      sourceText: "NOAA CO-OPS API (api.tidesandcurrents.noaa.gov)",
      sourceUrl: `https://tidesandcurrents.noaa.gov/stationhome.html?id=${tides.station_id}`,
      vintage: "live, 6-min cadence; residual ≈ surge",
      collapsed: false,
    }));
  }

  const al = ev.nws_alerts;
  if (al && al.n_active > 0) {
    const rows = [["Active flood-relevant alerts", String(al.n_active)]];
    (al.alerts || []).slice(0, 3).forEach((a, i) => {
      rows.push([
        `Alert ${i + 1}`,
        `${a.event} (${a.severity || "?"} / ${a.urgency || "?"}) — expires ${
          (a.expires || "").slice(0, 16)
        }`,
      ]);
    });
    cards.push(evCard({
      key: "nws_alerts",
      title: "NWS — active flood alerts at this point",
      flag: "hit", rows,
      sourceText: "NWS Public Alerts API (api.weather.gov)",
      sourceUrl: "https://www.weather.gov/documentation/services-web-api",
      vintage: "live, push-cadence (refresh on event)",
      collapsed: false,
    }));
  }

  const obs = ev.nws_obs;
  if (obs && obs.station_id && !obs.error && (
        obs.precip_last_hour_mm != null ||
        obs.precip_last_6h_mm != null)) {
    const rows = [
      ["Nearest ASOS station", `${obs.station_name} (${obs.station_id})`],
      ["Distance", `${obs.distance_km} km`],
    ];
    if (obs.precip_last_hour_mm != null)
      rows.push(["Precip last 1 h", `${obs.precip_last_hour_mm} mm`]);
    if (obs.precip_last_3h_mm != null)
      rows.push(["Precip last 3 h", `${obs.precip_last_3h_mm} mm`]);
    if (obs.precip_last_6h_mm != null)
      rows.push(["Precip last 6 h", `${obs.precip_last_6h_mm} mm`]);
    if (obs.obs_time)
      rows.push(["Observation time", obs.obs_time]);
    const heavy = (obs.precip_last_hour_mm || 0) >= 10 ||
                  (obs.precip_last_6h_mm || 0) >= 25;
    cards.push(evCard({
      key: "nws_obs",
      title: "NWS hourly METAR — recent precipitation",
      flag: heavy ? "hit" : "note", rows,
      sourceText: "NWS station observations API",
      sourceUrl: `https://www.weather.gov/wrh/timeseries?site=${obs.station_id}`,
      vintage: "live, ~hourly",
      collapsed: false,
    }));
  }

  const ttm = ev.ttm_forecast;
  if (ttm && ttm.available) {
    const peak = ttm.forecast_peak_ft;
    const rows = [
      ["Gauge", `${ttm.station_name} (NOAA ${ttm.station_id})`],
      ["Recent residual", `${ttm.history_recent_ft} ft`],
      ["Recent peak |residual|", `${ttm.history_peak_abs_ft} ft (last ~51 h)`],
      ["Forecast peak residual", `${peak >= 0 ? "+" : ""}${peak} ft`],
      ["Forecast peak time", `~${ttm.forecast_peak_minutes_ahead} min ahead (${(ttm.forecast_peak_time_utc || "").slice(11, 16)} UTC)`],
      ["Threshold", `±${ttm.threshold_ft} ft (gate for emission)`],
    ];
    const flag = ttm.interesting ? (Math.abs(peak) >= 0.5 ? "hit" : "note") : "miss";
    cards.push(evCard({
      key: "ttm_forecast",
      title: "Granite TimeSeries TTM r2 — surge nowcast",
      flag, rows,
      sourceText: "IBM Granite TimeSeries TTM r2 (Ekambaram et al. 2024, NeurIPS)",
      sourceUrl: "https://huggingface.co/ibm-granite/granite-timeseries-ttm-r2",
      vintage: "zero-shot multivariate forecaster, ~1.5M params; runs on CPU",
      collapsed: !ttm.interesting,
    }));
  }

  $("#evidenceCards").innerHTML = cards.join("");
}

function renderPolicy(ev) {
  const policy = $("#policySection");
  const rag = ev.rag || [];
  if (!rag.length) { policy.classList.add("hidden"); return; }
  policy.classList.remove("hidden");
  const items = rag.map(h => `<li>
    <div class="policy-title">${h.title || h.doc_id}</div>
    <div class="policy-quote">${(h.text || "").replace(/^"|"$/g, "").trim()}</div>
    <div class="policy-cite">${h.citation || ""}${h.page ? " · p. " + h.page : ""}</div>
  </li>`);
  $("#policyList").innerHTML = items.join("");
}

function renderEnergy(ev) {
  const en = ev.energy;
  if (!en) return;
  $("#energyLocal").textContent = `${en.local_mwh} mWh`;
  $("#energyCloud").textContent = `~${en.cloud_mwh} mWh`;
  $("#energyRatio").textContent = en.ratio_cloud_over_local
    ? `${en.ratio_cloud_over_local}×`
    : "—";
}

function renderEnergy(ev) {
  const en = ev.energy;
  if (!en) return;
  const $$ = (id) => document.getElementById(id);
  $$("energyLocal").textContent = `${en.local_mwh} mWh`;
  $$("energyCloud").textContent = `~${en.cloud_mwh} mWh`;
  $$("energyRatio").textContent = en.ratio_cloud_over_local
    ? `${en.ratio_cloud_over_local}×`
    : "—";
  const m = en.method || {};
  $$("energyMethod").innerHTML =
    `Local: ${m.local} (q4_K_M, package power; ${m.local_source}). ` +
    `Cloud: ${m.cloud} (${m.cloud_source}).`;
}

function renderNumberedSources() {
  // Render the methodology footer's <ol> in CITE_INDEX order so the [n]
  // superscripts in the lede paragraph match. CITE_INDEX is populated
  // by rewriteCitations() during renderParagraph().
  const ol = $("#sources");
  if (!ol) return;
  const entries = Object.entries(CITE_INDEX).sort((a, b) => a[1] - b[1]);
  ol.innerHTML = entries.map(([doc_id, n]) =>
    `<li value="${n}">${SOURCE_LABELS[doc_id] || doc_id} <code>[${doc_id}]</code></li>`
  ).join("");
}

function renderAddress(g) {
  const dl = $("#addr");
  dl.innerHTML = "";
  const rows = [
    ["address", g.address],
    ["borough", g.borough || ""],
    ["lat / lon", `${g.lat.toFixed(5)}, ${g.lon.toFixed(5)}`],
    ["BBL", g.bbl || ""],
    ["BIN", g.bin || ""],
  ];
  for (const [k, v] of rows) {
    if (!v) continue;
    const dt = document.createElement("dt"); dt.textContent = k;
    const dd = document.createElement("dd"); dd.textContent = v;
    dl.appendChild(dt); dl.appendChild(dd);
  }
}

// Suggested-address chips fill the input and submit
document.querySelectorAll(".chip[data-q]").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    $("#q").value = btn.getAttribute("data-q");
    $("#qform").requestSubmit();
  });
});

$("#qform").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = $("#q").value.trim();
  if (!q) return;
  if (evtSrc) evtSrc.close();
  resetUI(q);
  $("#go").disabled = true;
  evtSrc = new EventSource("/api/stream?q=" + encodeURIComponent(q));

  evtSrc.addEventListener("step", (msg) => {
    const ev = JSON.parse(msg.data);
    markStep(ev.step, ev);
  });
  evtSrc.addEventListener("final", (msg) => {
    const ev = JSON.parse(msg.data);
    $("#report").classList.remove("hidden");
    $("#meta").classList.remove("hidden");
    $("#map-card").classList.remove("hidden");
    // Reset citation index for this query before any citation rewriting
    CITE_INDEX = {};
    if (ev.geocode) {
      renderAddress(ev.geocode);
      updateMapForResult(ev.geocode);
    }
    renderHeader(ev);
    renderTier(ev);
    if (ev.paragraph) renderParagraph(ev.paragraph);
    renderKeyFindings(ev);
    renderEvidence(ev);
    renderPolicy(ev);
    renderEnergy(ev);
    renderNumberedSources();
  });
  evtSrc.addEventListener("done", () => {
    $("#go").disabled = false;
    evtSrc.close();
  });
  evtSrc.addEventListener("error", (msg) => {
    console.error("SSE error", msg);
    $("#go").disabled = false;
    evtSrc.close();
  });
});
