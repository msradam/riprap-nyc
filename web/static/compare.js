// Riprap — Compare mode. Two addresses, parallel FSM runs, shared map.

const STEP_LABELS = {
  geocode:                ["Geocode (DCP Geosearch)",          "address → lat/lon, BBL"],
  sandy_inundation:       ["Sandy Inundation (NYC OD)",        "empirical 2012 extent"],
  dep_stormwater:         ["DEP Stormwater Maps",              "pluvial scenarios + 2080 SLR"],
  floodnet:               ["FloodNet sensor network",          "live ultrasonic depth sensors"],
  nyc311:                 ["NYC 311 archive",                  "flood complaints in buffer"],
  microtopo_lidar:        ["LiDAR terrain (DEM + TWI + HAND)", "USGS 3DEP DEM + whitebox hydrology"],
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
  prithvi_water:          "Prithvi-EO 2.0 (300M, NASA/IBM) Sen1Floods11 — satellite water segmentation",
  rag_dep_2013:           "NYC DEP Wastewater Resiliency Plan (2013)",
  rag_nycha:              "NYCHA — Flood Resilience: Lessons Learned",
  rag_coned:              "Con Edison Climate Change Resilience Plan (Case 22-E-0222)",
  rag_mta:                "MTA Climate Resilience Roadmap (Oct 2025)",
  rag_comptroller:        "NYC Comptroller — \"Is NYC Ready for Rain?\" (2024)",
};

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
  map.on("load", () => {
    for (const sideKey of ["a", "b"]) {
      map.addSource("sandy_" + sideKey, { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({ id: "sandy_" + sideKey + "-fill", type: "fill", source: "sandy_" + sideKey,
        paint: { "fill-color": "#fc5d52", "fill-opacity": 0.22 } });
      map.addSource("dep_" + sideKey, { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({ id: "dep_" + sideKey + "-fill", type: "fill", source: "dep_" + sideKey,
        paint: {
          "fill-color": ["match", ["get", "Flooding_Category"],
            1, "#568adf", 2, "#1642DF", 3, "#031553", "#568adf"],
          "fill-opacity": 0.28 } });
      map.addSource("fn_" + sideKey, { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({ id: "fn_" + sideKey + "-circles", type: "circle", source: "fn_" + sideKey,
        paint: {
          "circle-radius": 5,
          "circle-color": ["case", [">", ["get", "n_events_3y"], 0], "#fc5d52", "#1a8754"],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.5,
        } });
    }
    map.addSource("addr_a", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    map.addLayer({ id: "addr_a-marker", type: "circle", source: "addr_a",
      paint: { "circle-radius": 9, "circle-color": "#1642DF", "circle-stroke-color": "#fff", "circle-stroke-width": 2.5 } });
    map.addSource("addr_b", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    map.addLayer({ id: "addr_b-marker", type: "circle", source: "addr_b",
      paint: { "circle-radius": 9, "circle-color": "#9333ea", "circle-stroke-color": "#fff", "circle-stroke-width": 2.5 } });
  });
}

function resetSide(side) {
  const ul = document.getElementById("steps" + side.toUpperCase());
  ul.innerHTML = "";
  for (const sid of STEPS_ORDER) {
    const [lbl, hint] = STEP_LABELS[sid] || [sid, ""];
    const li = document.createElement("li");
    li.id = `step-${side}-${sid}`;
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
  document.getElementById("step-" + side + "-" + STEPS_ORDER[0]).classList.replace("pending", "running");

  document.getElementById("report" + side.toUpperCase()).classList.add("hidden");
  document.getElementById("paragraph" + side.toUpperCase()).innerHTML = "";
  document.getElementById("glance" + side.toUpperCase()).innerHTML = "";
  document.getElementById("sources" + side.toUpperCase()).innerHTML = "";
}

function markStep(side, stepId, ev) {
  const li = document.getElementById(`step-${side}-${stepId}`);
  if (!li) return;
  li.className = ev.ok ? "ok" : "err";
  li.querySelector(".icon").textContent = ev.ok ? "✓" : "✗";
  if (ev.elapsed_s != null) {
    li.querySelector(".time").textContent = ev.elapsed_s.toFixed(2) + "s";
  }
  if (ev.result) {
    let div = li.querySelector(".result");
    if (!div) {
      div = document.createElement("div"); div.className = "result";
      li.appendChild(div);
    }
    div.textContent = formatResult(ev.result);
  } else if (ev.err) {
    let div = li.querySelector(".result");
    if (!div) {
      div = document.createElement("div"); div.className = "result";
      li.appendChild(div);
    }
    div.textContent = "error: " + ev.err;
  }
  const idx = STEPS_ORDER.indexOf(stepId);
  if (idx >= 0 && idx + 1 < STEPS_ORDER.length) {
    const next = document.getElementById(`step-${side}-${STEPS_ORDER[idx + 1]}`);
    if (next && next.classList.contains("pending")) next.classList.replace("pending", "running");
  }
}

function formatResult(r) {
  if (typeof r !== "object") return String(r);
  return Object.entries(r)
    .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`)
    .join(" · ");
}

function renderParagraph(side, text) {
  const html = (text || "").replace(/\[([a-z0-9_]+)\]/gi, (_, d) =>
    `<span class="cite" title="document id: ${d}">[${d}]</span>`);
  document.getElementById("paragraph" + side.toUpperCase()).innerHTML = html;
}

function renderGlance(side, ev) {
  const ul = document.getElementById("glance" + side.toUpperCase());
  if (!ul) return;
  const rows = [];
  if (ev.sandy) {
    rows.push({c: "hit", mark: "■", html: "Inside <strong>Sandy 2012</strong> inundation extent"});
  } else {
    rows.push({c: "miss", mark: "□", html: "Outside Sandy 2012 inundation extent"});
  }
  const dep = ev.dep || {};
  const depHits = Object.entries(dep).filter(([_, v]) => (v.depth_class || 0) > 0);
  if (depHits.length) {
    for (const [scen, v] of depHits) {
      const lbl = scen.replace("dep_", "").replace(/_/g, " ");
      rows.push({c: "hit", mark: "■", html: `Inside DEP ${lbl} — <strong>${v.depth_label}</strong>`});
    }
  } else {
    rows.push({c: "miss", mark: "□", html: "Outside all DEP stormwater scenarios"});
  }
  const fn = ev.floodnet;
  if (fn && fn.n_sensors) {
    if (fn.n_flood_events_3y > 0) {
      const peak = fn.peak_event;
      const peakStr = peak && peak.max_depth_mm
        ? `, peak <span class="gnum">${peak.max_depth_mm} mm</span>` : '';
      rows.push({c: "hit", mark: "■",
        html: `<span class="gnum">${fn.n_flood_events_3y}</span> FloodNet events (3 yr)${peakStr}`});
    } else {
      rows.push({c: "miss", mark: "□",
        html: `<span class="gnum">${fn.n_sensors}</span> FloodNet sensor(s), no events`});
    }
  }
  const ida = ev.ida_hwm;
  if (ida && ida.n_within_radius > 0) {
    const ht = ida.max_height_above_gnd_ft != null
      ? `up to <span class="gnum">${ida.max_height_above_gnd_ft} ft</span> above ground` : '';
    rows.push({c: "hit", mark: "■",
      html: `<span class="gnum">${ida.n_within_radius}</span> Ida 2021 HWMs ≤${ida.radius_m} m${ht ? ', ' + ht : ''}`});
  }
  const mt = ev.microtopo;
  if (mt) {
    rows.push({c: "note", mark: "◆",
      html: `Elevation <span class="gnum">${mt.point_elev_m} m</span>, lower than <span class="gnum">${mt.rel_elev_pct_200m}%</span> of nearby (200 m)`});
  }
  const c311 = ev.nyc311;
  if (c311 && c311.n > 0) {
    rows.push({c: "note", mark: "◆",
      html: `<span class="gnum">${c311.n}</span> 311 flood complaints ≤${c311.radius_m} m, ${c311.years} yr`});
  }
  ul.innerHTML = rows
    .map(r => `<li class="${r.c}"><span class="gmark">${r.mark}</span><span class="gtext">${r.html}</span></li>`).join("");
}

function renderSources(side, ev, paraText) {
  const fired = new Set([...(paraText || "").matchAll(/\[([a-z0-9_]+)\]/g)].map(m => m[1]));
  const order = [
    "sandy", "dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current",
    "floodnet", "ida_hwm", "microtopo", "nyc311",
    "rag_dep_2013", "rag_nycha", "rag_coned", "rag_mta", "rag_comptroller",
  ];
  const present = new Set();
  if (ev.sandy) present.add("sandy");
  for (const [k, v] of Object.entries(ev.dep || {})) {
    if ((v.depth_class || 0) > 0) present.add(k);
  }
  if (ev.floodnet && ev.floodnet.n_sensors > 0) present.add("floodnet");
  if (ev.ida_hwm && ev.ida_hwm.n_within_radius > 0) present.add("ida_hwm");
  if (ev.microtopo) present.add("microtopo");
  if (ev.nyc311 && ev.nyc311.n > 0) present.add("nyc311");
  if (ev.rag) for (const h of ev.rag) present.add(h.doc_id);

  const ol = document.getElementById("sources" + side.toUpperCase());
  ol.innerHTML = order.filter(d => present.has(d)).map(d => {
    const label = SOURCE_LABELS[d] || d;
    const dim = fired.has(d) ? "" : ' style="opacity:0.5"';
    return `<li${dim}><span class="src-tag">${d}</span><span class="src-cite">${label}</span></li>`;
  }).join("");
}

async function updateMapForSide(side, geo) {
  ensureMap();
  if (!map.loaded()) await new Promise(res => map.once("load", res));
  const sideKey = side.toLowerCase();
  map.getSource("addr_" + sideKey).setData({
    type: "FeatureCollection",
    features: [{ type: "Feature", geometry: { type: "Point", coordinates: [geo.lon, geo.lat] }, properties: {} }],
  });
  const url = (p) => `${p}?lat=${geo.lat}&lon=${geo.lon}&r=1500`;
  const [sandy, dep, fn] = await Promise.all([
    fetch(url("/api/layers/sandy")).then(r => r.json()).catch(() => null),
    fetch(url("/api/layers/dep_extreme_2080")).then(r => r.json()).catch(() => null),
    fetch(`/api/floodnet_near?lat=${geo.lat}&lon=${geo.lon}&r=1000`).then(r => r.json()).catch(() => null),
  ]);
  if (sandy) map.getSource("sandy_" + sideKey).setData(sandy);
  if (dep)   map.getSource("dep_" + sideKey).setData(dep);
  if (fn)    map.getSource("fn_" + sideKey).setData(fn);
}

function fitBoth(ga, gb) {
  if (!ga || !gb || !map.loaded()) return;
  const bounds = new maplibregl.LngLatBounds()
    .extend([ga.lon, ga.lat]).extend([gb.lon, gb.lat]);
  map.fitBounds(bounds, { padding: 80, duration: 800, maxZoom: 13 });
}

let geoA = null, geoB = null;

document.querySelectorAll(".chip[data-a]").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    document.getElementById("qa").value = btn.getAttribute("data-a");
    document.getElementById("qb").value = btn.getAttribute("data-b");
    document.getElementById("cform").requestSubmit();
  });
});

document.getElementById("cform").addEventListener("submit", (e) => {
  e.preventDefault();
  const a = document.getElementById("qa").value.trim();
  const b = document.getElementById("qb").value.trim();
  if (!a || !b) return;
  document.getElementById("aTitle").textContent = a;
  document.getElementById("bTitle").textContent = b;
  resetSide("a"); resetSide("b");
  ensureMap();
  geoA = geoB = null;
  document.getElementById("cgo").disabled = true;
  if (evtSrc) evtSrc.close();
  evtSrc = new EventSource(`/api/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);

  evtSrc.addEventListener("step", (msg) => {
    const ev = JSON.parse(msg.data);
    markStep(ev.side, ev.step, ev);
  });
  evtSrc.addEventListener("final", (msg) => {
    const ev = JSON.parse(msg.data);
    const side = ev.side;
    document.getElementById("report" + side.toUpperCase()).classList.remove("hidden");
    if (ev.geocode) {
      if (side === "a") geoA = ev.geocode; else geoB = ev.geocode;
      updateMapForSide(side, ev.geocode).then(() => fitBoth(geoA, geoB));
    }
    if (ev.paragraph) renderParagraph(side, ev.paragraph);
    renderGlance(side, ev);
    renderSources(side, ev, ev.paragraph || "");
  });
  evtSrc.addEventListener("done", () => {
    document.getElementById("cgo").disabled = false;
    evtSrc.close();
  });
  evtSrc.addEventListener("error", () => {
    document.getElementById("cgo").disabled = false;
  });
});
