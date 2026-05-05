// HeliOS-NYC web client. Subscribes to SSE, lights up FSM steps.

const STEP_LABELS = {
  geocode:                ["Geocode (DCP Geosearch)",          "address → lat/lon, BBL"],
  sandy_inundation:       ["Sandy Inundation (NYC OD)",        "empirical 2012 extent"],
  dep_stormwater:         ["DEP Stormwater Maps",              "pluvial scenarios + 2080 SLR"],
  floodnet:               ["FloodNet sensor network",          "live ultrasonic depth sensors"],
  nyc311:                 ["NYC 311 archive",                  "flood complaints in buffer"],
  microtopo_lidar:        ["LiDAR terrain (DEM + TWI + HAND)", "USGS 3DEP DEM + whitebox-workflows hydrology"],
  ida_hwm_2021:           ["Ida 2021 high-water marks",        "USGS empirical post-event extent"],
  prithvi_eo_v2:          ["Prithvi-EO 2.0 (300M, NASA/IBM)",  "Sen1Floods11 satellite water segmentation"],
  rag_granite_embedding:  ["Granite Embedding 278M (RAG)",     "policy corpus retrieval"],
  reconcile_granite41:    ["Granite 4.1 reconcile (local)",    "document-grounded synthesis"],
};

const STEPS_ORDER = [
  "geocode", "sandy_inundation", "dep_stormwater", "floodnet", "nyc311",
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

function renderParagraph(text) {
  $("#paragraph").innerHTML = rewriteCitations(text);
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
};

// ----------------------------------------------------------------------
// CIVIC ASSESSMENT REPORT — header strip, tier badge, key findings,
// evidence cards, policy quotes, methodology footer.
// ----------------------------------------------------------------------

function tierMeta(score) {
  // Mirror app/score.py rubric: ≥6 = T1, 4-5 = T2, 2-3 = T3, 1 = T4, 0 = T0.
  if (score >= 6)  return {tier: 1, label: "High exposure",       help: "Multiple positive flood signals — historical inundation and modeled scenarios both indicate substantial risk."};
  if (score >= 4)  return {tier: 2, label: "Elevated exposure",   help: "Significant overlap with at least one empirical or modeled scenario."};
  if (score >= 2)  return {tier: 3, label: "Moderate exposure",   help: "One or two positive signals; localised or scenario-specific risk."};
  if (score >= 1)  return {tier: 4, label: "Limited exposure",    help: "A single contextual signal; no positive scenario hits."};
  return            {tier: 0, label: "No flagged exposure",        help: "No positive flood signal across the assessed sources."};
}

function computeScore(ev) {
  // Mirror server-side rubric so we render consistently.
  let s = 0;
  if (ev.sandy) s += 3;
  const dep = ev.dep || {};
  if ((dep.dep_extreme_2080?.depth_class || 0) > 0) s += 2;
  if ((dep.dep_moderate_2050?.depth_class || 0) > 0) s += 2;
  if ((dep.dep_moderate_current?.depth_class || 0) > 0) s += 1;
  if ((ev.nyc311?.n || 0) >= 3) s += 1;
  if ((ev.floodnet?.n_flood_events_3y || 0) > 0) s += 1;
  if ((ev.rag || []).length) s += 1;
  return s;
}

function renderHeader(ev) {
  const geo = ev.geocode || {};
  $("#reportAddr").textContent = geo.address || "(unresolved)";
  $("#reportBoro").textContent = geo.borough || "—";
  $("#reportBbl").textContent  = geo.bbl || "—";
  $("#reportTs").textContent   = new Date().toISOString().slice(0,10);
}

function renderTier(ev) {
  const score = computeScore(ev);
  const m = tierMeta(score);
  const badge = $("#tierBadge");
  badge.className = "tier-badge t-" + m.tier;
  $("#tierNum").textContent = m.tier;
  $("#tierLabel").textContent = `Tier ${m.tier} — ${m.label}`;
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
