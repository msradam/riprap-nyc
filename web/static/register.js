// Riprap — Bulk mode (schools register).

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

let allRows = [];
let filteredRows = [];
let selected = null;
let detailMap = null;

function tierBadge(t) {
  const cls = "tier-badge tier-" + t;
  return `<span class="${cls}">${t}</span>`;
}

function yn(b) { return b ? '<span class="yn yes">●</span>' : '<span class="yn no">○</span>'; }

function renderTable() {
  const tbody = $("#regBody");
  tbody.innerHTML = filteredRows.map((r, i) => {
    const snap = r.snap || {};
    const sandy  = snap.sandy ? yn(true) : yn(false);
    const dep80  = snap.dep && snap.dep.dep_extreme_2080 && snap.dep.dep_extreme_2080.depth_class > 0 ? yn(true) : yn(false);
    const c311   = (snap.nyc311 && snap.nyc311.n) || 0;
    const fnEv   = (snap.floodnet && snap.floodnet.n_flood_events_3y) || 0;
    const idaN   = (snap.ida_hwm && snap.ida_hwm.n_within_radius) || 0;
    return `<tr data-idx="${i}">
      <td>${tierBadge(r.tier)}</td>
      <td class="num">${r.score}</td>
      <td>
        <div class="rname">${r.name}</div>
        <div class="raddr">${r.address || ""}</div>
      </td>
      <td>${r.borough || ""}</td>
      <td class="num">${sandy}</td>
      <td class="num">${dep80}</td>
      <td class="num">${c311 || ""}</td>
      <td class="num">${fnEv || ""}</td>
      <td class="num">${idaN || ""}</td>
    </tr>`;
  }).join("");

  tbody.querySelectorAll("tr").forEach((tr) => {
    tr.addEventListener("click", () => selectRow(parseInt(tr.dataset.idx, 10)));
  });
}

function applyFilters() {
  const q = ($("#filter").value || "").toLowerCase();
  const boro = $("#boroughFilter").value || "";
  filteredRows = allRows.filter((r) => {
    if (boro && r.borough !== boro) return false;
    if (!q) return true;
    return (
      (r.name || "").toLowerCase().includes(q) ||
      (r.address || "").toLowerCase().includes(q) ||
      (r.borough || "").toLowerCase().includes(q) ||
      (r.bbl || "").toString().includes(q)
    );
  });
  renderTable();
}

function selectRow(idx) {
  selected = filteredRows[idx];
  if (!selected) return;
  $("#detailEmpty").classList.add("hidden");
  $("#detailBody").classList.remove("hidden");
  $("#detailHeader").innerHTML = `
    <div class="rname">${selected.name}</div>
    <div class="raddr">${selected.address}, ${selected.borough}</div>
    <div class="rmeta">BBL: ${selected.bbl || "—"} · Tier ${selected.tier} · Score ${selected.score}</div>`;
  renderDetail(selected);
}

function renderDetail(row) {
  const snap = row.snap || {};
  // glance
  const rows = [];
  if (snap.sandy) rows.push({c:"hit", mark:"■", html:"Inside <strong>Sandy 2012</strong> inundation extent"});
  else            rows.push({c:"miss",mark:"□", html:"Outside Sandy 2012 inundation extent"});
  const dep = snap.dep || {};
  const depHits = Object.entries(dep).filter(([_,v]) => (v.depth_class || 0) > 0);
  if (depHits.length) {
    for (const [scen, v] of depHits) {
      const lbl = scen.replace("dep_","").replace(/_/g, " ");
      rows.push({c:"hit", mark:"■", html:`Inside DEP ${lbl} — <strong>${v.depth_label}</strong>`});
    }
  } else {
    rows.push({c:"miss", mark:"□", html:"Outside all DEP stormwater scenarios"});
  }
  const fn = snap.floodnet;
  if (fn && fn.n_sensors) {
    if (fn.n_flood_events_3y > 0) {
      const peak = fn.peak_event;
      const peakStr = peak && peak.max_depth_mm ? `, peak <span class="gnum">${peak.max_depth_mm} mm</span>` : "";
      rows.push({c:"hit", mark:"■", html:`<span class="gnum">${fn.n_flood_events_3y}</span> FloodNet events (3 yr)${peakStr}`});
    }
  }
  const ida = snap.ida_hwm;
  if (ida && ida.n_within_radius > 0) {
    const ht = ida.max_height_above_gnd_ft != null ? `up to <span class="gnum">${ida.max_height_above_gnd_ft} ft</span> above ground` : "";
    rows.push({c:"hit", mark:"■", html:`<span class="gnum">${ida.n_within_radius}</span> Ida HWMs ≤${ida.radius_m} m${ht ? ", " + ht : ""}`});
  }
  const mt = snap.microtopo;
  if (mt) {
    rows.push({c:"note", mark:"◆", html:`Elevation <span class="gnum">${mt.point_elev_m} m</span>; lower than <span class="gnum">${mt.rel_elev_pct_200m}%</span> of nearby (200 m)`});
  }
  const c311 = snap.nyc311;
  if (c311 && c311.n > 0) {
    rows.push({c:"note", mark:"◆", html:`<span class="gnum">${c311.n}</span> 311 flood complaints ≤${c311.radius_m} m, ${c311.years} yr`});
  }
  $("#detailGlance").innerHTML = rows.map(r =>
    `<li class="${r.c}"><span class="gmark">${r.mark}</span><span class="gtext">${r.html}</span></li>`).join("");

  // paragraph
  const para = snap.paragraph;
  const noPara = $("#detailNoPara");
  if (para) {
    $("#detailParagraph").innerHTML = (para || "").replace(/\[([a-z0-9_]+)\]/gi,
      (_, d) => `<span class="cite" title="document id: ${d}">[${d}]</span>`);
    noPara.classList.add("hidden");
  } else {
    $("#detailParagraph").innerHTML = "";
    noPara.classList.remove("hidden");
  }

  // sources
  const fired = new Set([...(para || "").matchAll(/\[([a-z0-9_]+)\]/g)].map(m => m[1]));
  const order = [
    "sandy", "dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current",
    "floodnet", "ida_hwm", "microtopo", "nyc311",
    "rag_dep_2013", "rag_nycha", "rag_coned", "rag_mta", "rag_comptroller",
  ];
  const present = new Set();
  if (snap.sandy) present.add("sandy");
  for (const [k, v] of Object.entries(snap.dep || {})) {
    if ((v.depth_class || 0) > 0) present.add(k);
  }
  if (snap.floodnet && snap.floodnet.n_sensors > 0) present.add("floodnet");
  if (snap.ida_hwm && snap.ida_hwm.n_within_radius > 0) present.add("ida_hwm");
  if (snap.microtopo) present.add("microtopo");
  if (snap.nyc311 && snap.nyc311.n > 0) present.add("nyc311");
  if (snap.rag) for (const h of snap.rag) present.add(h.doc_id);

  $("#detailSources").innerHTML = order.filter(d => present.has(d)).map(d => {
    const dim = fired.has(d) ? "" : ' style="opacity:0.5"';
    return `<li${dim}><span class="src-tag">${d}</span><span class="src-cite">${SOURCE_LABELS[d] || d}</span></li>`;
  }).join("");

  showDetailMap(row);
}

function showDetailMap(row) {
  const div = $("#detailMap");
  if (!detailMap) {
    detailMap = new maplibregl.Map({
      container: "detailMap",
      style: {
        version: 8,
        sources: {
          carto: { type: "raster",
            tiles: ["https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"],
            tileSize: 256, attribution: "© OSM · CARTO" },
        },
        layers: [{ id: "bg", type: "raster", source: "carto" }],
      },
      center: [row.lon, row.lat], zoom: 14, attributionControl: { compact: true },
    });
    detailMap.on("load", () => {
      detailMap.addSource("addr", { type: "geojson", data: { type:"FeatureCollection", features:[] }});
      detailMap.addLayer({ id:"addr-marker", type:"circle", source:"addr",
        paint: { "circle-radius": 9, "circle-color": "#1642DF", "circle-stroke-color":"#fff", "circle-stroke-width": 2.5 }});
    });
  }
  const setMarker = () => {
    detailMap.getSource("addr").setData({ type:"FeatureCollection", features:[
      { type:"Feature", geometry:{ type:"Point", coordinates:[row.lon, row.lat] }, properties:{} }
    ]});
    detailMap.flyTo({ center: [row.lon, row.lat], zoom: 14 });
  };
  if (detailMap.loaded()) setMarker(); else detailMap.once("load", setMarker);
}

async function generateLiveParagraph() {
  if (!selected) return;
  const btn = $("#livePara"); btn.disabled = true; btn.textContent = "Generating…";
  try {
    const u = `/api/stream?q=${encodeURIComponent(selected.address + ", " + selected.borough)}`;
    // collect SSE final event
    const text = await new Promise((resolve, reject) => {
      const es = new EventSource(u);
      es.addEventListener("final", (m) => { resolve(JSON.parse(m.data)); es.close(); });
      es.addEventListener("error", () => { reject(new Error("stream error")); es.close(); });
      setTimeout(() => { reject(new Error("timeout")); es.close(); }, 90000);
    });
    if (text.paragraph) {
      selected.snap.paragraph = text.paragraph;
      selected.snap.rag = text.rag || selected.snap.rag;
      renderDetail(selected);
    }
  } catch (e) {
    btn.textContent = "Failed: " + e.message;
    btn.disabled = false;
  }
}

function exportCsv() {
  const cols = ["tier","score","name","address","borough","bbl","bin",
                "lat","lon","sandy","dep_extreme_2080","floodnet_events_3y",
                "ida_hwms_800m","nyc311_5y"];
  const lines = [cols.join(",")];
  for (const r of filteredRows) {
    const s = r.snap || {};
    const row = [
      r.tier, r.score, JSON.stringify(r.name), JSON.stringify(r.address || ""),
      r.borough || "", r.bbl || "", r.bin || "", r.lat, r.lon,
      s.sandy ? 1 : 0,
      (s.dep && s.dep.dep_extreme_2080 && s.dep.dep_extreme_2080.depth_class) || 0,
      (s.floodnet && s.floodnet.n_flood_events_3y) || 0,
      (s.ida_hwm && s.ida_hwm.n_within_radius) || 0,
      (s.nyc311 && s.nyc311.n) || 0,
    ];
    lines.push(row.join(","));
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  download(blob, "riprap_schools_register.csv");
}

function exportGeojson() {
  const features = filteredRows.map((r) => ({
    type: "Feature",
    geometry: { type: "Point", coordinates: [r.lon, r.lat] },
    properties: {
      tier: r.tier, score: r.score, name: r.name, address: r.address,
      borough: r.borough, bbl: r.bbl, bin: r.bin,
      sandy: !!(r.snap && r.snap.sandy),
      dep_extreme_2080: (r.snap && r.snap.dep && r.snap.dep.dep_extreme_2080 && r.snap.dep.dep_extreme_2080.depth_class) || 0,
    },
  }));
  const blob = new Blob([JSON.stringify({ type: "FeatureCollection", features })],
                        { type: "application/geo+json" });
  download(blob, "riprap_schools_register.geojson");
}

function download(blob, filename) {
  const u = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = u; a.download = filename;
  document.body.appendChild(a); a.click();
  setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(u); }, 200);
}

// Asset class is parsed from URL path: /register/<asset_class>
const ASSET_CLASS = (location.pathname.match(/\/register\/([^\/?]+)/) || [])[1] || "schools";

const ASSET_TITLES = {
  schools:        "NYC public schools — flood exposure register",
  nycha:          "NYCHA developments — flood exposure register",
  mta_entrances:  "MTA subway entrances — flood exposure register",
};
document.title = `Riprap — ${ASSET_TITLES[ASSET_CLASS] || ASSET_CLASS}`;
const tagSpan = document.querySelector(".brand-tag");
if (tagSpan) tagSpan.textContent = ASSET_TITLES[ASSET_CLASS] || ASSET_CLASS;

const classPicker = document.getElementById("classPicker");
if (classPicker) {
  classPicker.value = ASSET_CLASS;
  classPicker.addEventListener("change", () => {
    location.href = `/register/${classPicker.value}`;
  });
}

(async function init() {
  const r = await fetch(`/api/register/${ASSET_CLASS}`);
  if (!r.ok) {
    const script = `python scripts/build_${ASSET_CLASS}_register.py`;
    $("#regBody").innerHTML = `<tr><td colspan="9" style="padding: 20px; color: var(--text-muted);">Register not built. Run <code>${script}</code>.</td></tr>`;
    return;
  }
  const data = await r.json();
  allRows = data.rows || [];
  filteredRows = allRows.slice();

  // tier counts
  $("#totalCount").textContent = allRows.length;
  $("#tier1Count").textContent = allRows.filter(r => r.tier === 1).length;
  $("#tier2Count").textContent = allRows.filter(r => r.tier === 2).length;
  $("#tier3Count").textContent = allRows.filter(r => r.tier === 3).length;

  renderTable();

  $("#filter").addEventListener("input", applyFilters);
  $("#boroughFilter").addEventListener("change", applyFilters);
  $("#exportCsv").addEventListener("click", exportCsv);
  $("#exportGeojson").addEventListener("click", exportGeojson);
  $("#livePara").addEventListener("click", generateLiveParagraph);
})();
