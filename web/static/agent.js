// Riprap agent client — three-panel UI with live SSE streaming, intent-
// dispatched map, and structured report rendering.

const $ = (s) => document.querySelector(s);

const STEP_LABELS = {
  // single_address chain (linear FSM)
  geocode:                ["Geocode (DCP Geosearch)",          "address → lat/lon, BBL"],
  sandy_inundation:       ["Sandy Inundation (NYC OD)",        "empirical 2012 extent"],
  dep_stormwater:         ["DEP Stormwater Maps",              "pluvial scenarios + 2080 SLR"],
  floodnet:               ["FloodNet sensor network",          "live ultrasonic depth sensors"],
  nyc311:                 ["NYC 311 archive",                  "flood complaints in 200m"],
  noaa_tides:             ["NOAA Tides & Currents (live)",     "Battery / Kings Pt / Sandy Hook"],
  nws_alerts:             ["NWS Public Alerts (live)",         "active flood-relevant alerts"],
  nws_obs:                ["NWS METAR observation (live)",     "nearest ASOS recent precipitation"],
  ttm_forecast:           ["Granite TTM r2 — surge nowcast",   "9.6h forecast at the closest of Battery / Kings Pt / Sandy Hook"],
  ttm_311_forecast:       ["Granite TTM r2 — 311 forecast",    "4-week per-address flood-complaint forecast (52w history)"],
  floodnet_forecast:      ["Granite TTM r2 — FloodNet forecast", "flood-event recurrence forecast at nearest FloodNet sensor"],
  ttm_battery_surge:      ["Granite TTM r2 — Battery surge (NYC fine-tune)", "96 h hourly surge nowcast at NOAA Battery (msradam/Granite-TTM-r2-Battery-Surge)"],
  mta_entrance_exposure:  ["MTA subway entrances",              "subway-entrance exposure (point-in-polygon Sandy + DEP)"],
  nycha_development_exposure: ["NYCHA developments",            "NYCHA campus footprint × Sandy + DEP overlap %"],
  doe_school_exposure:    ["NYC DOE schools",                   "school-point exposure (Sandy + DEP)"],
  doh_hospital_exposure:  ["NYS DOH hospitals",                 "Article-28 hospital exposure (Sandy + DEP)"],
  microtopo_lidar:        ["LiDAR terrain (DEM + TWI + HAND)", "USGS 3DEP DEM + whitebox-workflows"],
  ida_hwm_2021:           ["Ida 2021 high-water marks",        "USGS empirical post-event extent"],
  prithvi_eo_v2:          ["Prithvi-EO 2.0 (NASA/IBM)",        "Sen1Floods11 satellite segmentation"],
  prithvi_eo_live:        ["Prithvi-EO 2.0 — live segmentation","fresh Sentinel-2 water mask at this address"],
  terramind_synthesis:    ["TerraMind 1.0 base — synthetic LULC",   "DEM → ESRI Land Cover, any-to-any generative synthesis (IBM/ESA)"],
  eo_chip_fetch:          ["EO chip fetch (S2L2A + S1RTC + DEM)",   "single-chip cache for the TerraMind-NYC LoRA family"],
  terramind_lulc:         ["TerraMind-NYC — LULC (live)",           "5-class macro land-cover LoRA (msradam/TerraMind-NYC-Adapters)"],
  terramind_buildings:    ["TerraMind-NYC — Buildings (live)",      "binary building-footprint LoRA (msradam/TerraMind-NYC-Adapters)"],
  rag_granite_embedding:  ["Granite Embedding 278M (RAG)",     "policy corpus retrieval (+ Granite Reranker R2 if enabled)"],
  gliner_extract:         ["GLiNER typed extraction",          "agencies, dollar amounts, projects, locations"],
  reconcile_granite41:    ["Granite 4.1 reconcile (local)",    "document-grounded synthesis"],
  // neighborhood + dev_check
  nta_resolve:            ["NTA polygon resolve",              "name → NYC NTA 2020 polygon"],
  sandy_nta:              ["Sandy 2012, polygon-aggregated",   "% of NTA inside 2012 inundation"],
  dep_extreme_2080_nta:   ["DEP Extreme-2080, polygon",        "% of NTA in modeled flooding"],
  dep_moderate_2050_nta:  ["DEP Moderate-2050, polygon",       "% of NTA in modeled flooding"],
  dep_moderate_current_nta:["DEP Moderate-current, polygon",   "% of NTA in modeled flooding"],
  nyc311_nta:             ["NYC 311, polygon-aggregated",      "complaints inside polygon"],
  microtopo_nta:          ["LiDAR terrain, polygon",           "median HAND/TWI + flood bands"],
  rag_nta:                ["Granite Embedding RAG (NTA)",      "policy retrieval for the place"],
  reconcile_neighborhood: ["Granite 4.1 reconcile (NTA)",      "polygon-flavored briefing"],
  // dev_check
  dob_permits_nta:        ["NYC DOB permits in polygon",       "active NB / A1 / DM jobs ↔ flood layers"],
  rag_dev:                ["Granite Embedding RAG (dev)",      "policy on new construction in flood zones"],
  reconcile_development:  ["Granite 4.1 reconcile (dev)",      "flagged-projects briefing"],
  // live_now
  reconcile_live_now:     ["Granite 4.1 reconcile (live)",     "current-conditions briefing"],
};

const SOURCE_LABELS = {
  geocode: "NYC DCP Geosearch",
  nta_resolve: "NYC DCP Neighborhood Tabulation Areas 2020",
  sandy: "NYC OD 5xsi-dfpx — Sandy 2012 inundation",
  sandy_nta: "Sandy 2012 inundation, polygon-aggregated",
  dep_extreme_2080: "NYC DEP Stormwater — Extreme-2080",
  dep_moderate_2050: "NYC DEP Stormwater — Moderate-2050",
  dep_moderate_current: "NYC DEP Stormwater — Moderate-current",
  dep_extreme_2080_nta: "NYC DEP Extreme-2080, polygon-aggregated",
  dep_moderate_2050_nta: "NYC DEP Moderate-2050, polygon-aggregated",
  dep_moderate_current_nta: "NYC DEP Moderate-current, polygon-aggregated",
  floodnet: "FloodNet NYC",
  nyc311: "NYC 311 (erm2-nwe9)",
  nyc311_nta: "NYC 311, polygon-aggregated",
  microtopo: "USGS 3DEP DEM",
  microtopo_nta: "USGS 3DEP DEM, polygon-aggregated",
  ida_hwm: "USGS Hurricane Ida 2021 HWMs",
  prithvi_water: "Prithvi-EO 2.0 — Hurricane Ida 2021 polygons",
  prithvi_live:  "Prithvi-EO 2.0 NYC-Pluvial v2 — live Sentinel-2 water segmentation (msradam/Prithvi-EO-2.0-NYC-Pluvial)",
  terramind_synthetic: "TerraMind 1.0 base — synthetic LULC (DEM→ESRI Land Cover)",
  tm_lulc:        "TerraMind-NYC LULC LoRA (msradam/TerraMind-NYC-Adapters)",
  tm_buildings:   "TerraMind-NYC Buildings LoRA (msradam/TerraMind-NYC-Adapters)",
  gliner_comptroller: "GLiNER over Comptroller report",
  gliner_dep_2013:    "GLiNER over DEP wastewater plan",
  gliner_nycha:       "GLiNER over NYCHA Lessons Learned",
  gliner_mta:         "GLiNER over MTA Climate Resilience Roadmap",
  gliner_coned:       "GLiNER over Con Edison Climate Resilience",
  noaa_tides: "NOAA CO-OPS Tides & Currents",
  nws_alerts: "NWS Public Alerts",
  nws_obs: "NWS Station Observations",
  ttm_forecast: "Granite TimeSeries TTM r2 — surge residual nowcast",
  ttm_311_forecast: "Granite TimeSeries TTM r2 — per-address 311 weekly forecast",
  floodnet_forecast: "Granite TimeSeries TTM r2 — FloodNet sensor recurrence forecast",
  ttm_battery: "Granite TTM r2 NYC fine-tune — 96 h Battery surge nowcast (msradam/Granite-TTM-r2-Battery-Surge)",
  dob_permits: "NYC DOB Permit Issuance (Socrata ipu4-2q9a)",
  live_target: "Riprap planner — live target",
  rag_comptroller: 'NYC Comptroller — "Is NYC Ready for Rain?" (2024)',
  rag_npcc4: "NPCC4 (2024)",
  rag_mta: "MTA Climate Resilience Roadmap",
  rag_nycha: "NYCHA Flood Resilience: Lessons Learned",
  rag_coned: "Con Edison Climate Resilience Plan",
  // Register-specialist family labels — chip lookups for dynamic
  // doc_ids (mta_entrance_<id>, nycha_dev_<tds>, doe_school_<loc>,
  // nyc_hospital_<fac>) fall through to these via family-prefix match.
  mta_entrance: "MTA subway-entrance exposure (Open Data)",
  nycha_dev:    "NYCHA development exposure (NYC OD phvi-damg)",
  doe_school:   "NYC DOE school exposure",
  nyc_hospital: "NYS DOH hospital exposure (vn5v-hh5r)",
};

// Canonical URL per doc_id — clicking a source row opens the underlying
// dataset / API / report in a new tab so users can verify provenance.
const SOURCE_URLS = {
  geocode:                "https://geosearch.planninglabs.nyc/",
  nta_resolve:            "https://www.nyc.gov/site/planning/data-maps/open-data/dwn-nynta.page",
  sandy:                  "https://data.cityofnewyork.us/Environment/Sandy-Inundation-Zone/uyj8-7rv5",
  sandy_nta:              "https://data.cityofnewyork.us/Environment/Sandy-Inundation-Zone/uyj8-7rv5",
  dep_extreme_2080:       "https://data.cityofnewyork.us/Environment/NYC-Stormwater-Flood-Map-Extreme-Flood-with-Curren/w8eg-8ha6",
  dep_moderate_2050:      "https://data.cityofnewyork.us/Environment/NYC-Stormwater-Flood-Map-Moderate-Flood-with-Curre/9i7c-xyvv",
  dep_moderate_current:   "https://data.cityofnewyork.us/Environment/NYC-Stormwater-Flood-Map-Moderate-Flood/5rzh-cyqd",
  dep_extreme_2080_nta:   "https://data.cityofnewyork.us/Environment/NYC-Stormwater-Flood-Map-Extreme-Flood-with-Curren/w8eg-8ha6",
  dep_moderate_2050_nta:  "https://data.cityofnewyork.us/Environment/NYC-Stormwater-Flood-Map-Moderate-Flood-with-Curre/9i7c-xyvv",
  dep_moderate_current_nta: "https://data.cityofnewyork.us/Environment/NYC-Stormwater-Flood-Map-Moderate-Flood/5rzh-cyqd",
  floodnet:               "https://www.floodnet.nyc/",
  nyc311:                 "https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9",
  nyc311_nta:             "https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9",
  microtopo:              "https://www.usgs.gov/3d-elevation-program",
  microtopo_nta:          "https://www.usgs.gov/3d-elevation-program",
  ida_hwm:                "https://stn.wim.usgs.gov/STNDataPortal/",
  prithvi_water:          "https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11",
  prithvi_live:           "https://huggingface.co/msradam/Prithvi-EO-2.0-NYC-Pluvial",
  terramind_synthetic:    "https://huggingface.co/ibm-esa-geospatial/TerraMind-1.0-base",
  tm_lulc:                "https://huggingface.co/msradam/TerraMind-NYC-Adapters",
  tm_buildings:           "https://huggingface.co/msradam/TerraMind-NYC-Adapters",
  gliner_comptroller:     "https://huggingface.co/urchade/gliner_medium-v2.1",
  gliner_dep_2013:        "https://huggingface.co/urchade/gliner_medium-v2.1",
  gliner_nycha:           "https://huggingface.co/urchade/gliner_medium-v2.1",
  gliner_mta:             "https://huggingface.co/urchade/gliner_medium-v2.1",
  gliner_coned:           "https://huggingface.co/urchade/gliner_medium-v2.1",
  noaa_tides:             "https://tidesandcurrents.noaa.gov/",
  nws_alerts:             "https://www.weather.gov/documentation/services-web-api",
  nws_obs:                "https://www.weather.gov/documentation/services-web-api",
  ttm_forecast:           "https://huggingface.co/ibm-granite/granite-timeseries-ttm-r2",
  ttm_311_forecast:       "https://huggingface.co/ibm-granite/granite-timeseries-ttm-r2",
  floodnet_forecast:      "https://huggingface.co/ibm-granite/granite-timeseries-ttm-r2",
  ttm_battery:            "https://huggingface.co/msradam/Granite-TTM-r2-Battery-Surge",
  dob_permits:            "https://data.cityofnewyork.us/Housing-Development/DOB-Permit-Issuance/ipu4-2q9a",
  rag_comptroller:        "https://comptroller.nyc.gov/reports/is-new-york-city-ready-for-rain/",
  rag_npcc4:              "https://nyaspubs.onlinelibrary.wiley.com/toc/17496632/2024/1539/1",
  rag_mta:                "https://new.mta.info/sustainability/climate-resilience",
  rag_nycha:              "https://www.nyc.gov/site/nycha/about/sustainability.page",
  rag_coned:              "https://www.coned.com/en/our-energy-future/climate-change-resilience",
  mta_entrance:           "https://data.ny.gov/Transportation/MTA-Subway-Entrances-and-Exits-2024/i9wp-a4ja",
  nycha_dev:              "https://data.cityofnewyork.us/Housing-Development/Map-of-NYCHA-Developments/i9rv-hdr5",
  doe_school:             "https://data.cityofnewyork.us/Education/School-Locations/jfju-ynrr",
  nyc_hospital:           "https://health.data.ny.gov/Health/Health-Facility-Certification-Information/2g9y-7kqm",
};

// Per-source vintage / "as of" — what date the underlying data represents.
// For live sources, the answer is "live; observation timestamps in payload".
// For archival sources, this is the dataset publication or extent date.
const SOURCE_VINTAGES = {
  geocode:                "live (NYC DCP Geosearch v2)",
  nta_resolve:            "NYC NTA 2020 boundaries (DCP, Sept 2022 release)",
  sandy:                  "Sandy 2012 inundation extent (NYC OEM survey, dataset published 2013)",
  sandy_nta:              "Sandy 2012 inundation extent (polygon-aggregated)",
  dep_extreme_2080:       "NYC DEP Stormwater Flood Map — Extreme + 2080 SLR (2021 release)",
  dep_moderate_2050:      "NYC DEP Stormwater Flood Map — Moderate + 2050 SLR (2021 release)",
  dep_moderate_current:   "NYC DEP Stormwater Flood Map — Moderate, current SLR (2021 release)",
  dep_extreme_2080_nta:   "NYC DEP Extreme-2080 (2021 release; polygon-aggregated)",
  dep_moderate_2050_nta:  "NYC DEP Moderate-2050 (2021 release; polygon-aggregated)",
  dep_moderate_current_nta: "NYC DEP Moderate-current (2021 release; polygon-aggregated)",
  floodnet:               "live FloodNet sensor stream (per-event timestamps in payload)",
  nyc311:                 "live NYC 311 archive, trailing 5-year window (latest record in payload)",
  nyc311_nta:             "live NYC 311 archive, trailing 3-year window (polygon-aggregated)",
  microtopo:              "USGS 3DEP DEM (NYC LiDAR collect, ~2018) + derived HAND/TWI",
  microtopo_nta:          "USGS 3DEP DEM (NYC ~2018) — polygon-aggregated stats",
  ida_hwm:                "USGS Short-Term Network Event 312 — Hurricane Ida 2021 high-water marks (Sept 1-2 2021 survey)",
  prithvi_water:          "Prithvi-EO 2.0 satellite segmentation, scenes 2021-08-25 (pre) & 2021-09-02 (post Ida)",
  prithvi_live:           "live Sentinel-2 L2A scene from Microsoft Planetary Computer (acquisition timestamp in payload), segmented by the NYC-Pluvial v2 fine-tune of Prithvi-EO 2.0 (test flood IoU 0.5979)",
  terramind_synthetic:    "synthetic prior — TerraMind 1.0 base generated a plausible categorical land-cover map from the LiDAR terrain at this point (deterministic seed, 10 diffusion steps; class fractions cite-able; not a measurement)",
  tm_lulc:                "live empirical observation — TerraMind-NYC LULC LoRA (msradam/TerraMind-NYC-Adapters, fine-tuned on NYC chips on AMD MI300X) over the per-query Sentinel-2/1/DEM chip; 5-class macro land cover with class fractions cite-able",
  tm_buildings:           "live empirical observation — TerraMind-NYC Buildings LoRA (msradam/TerraMind-NYC-Adapters, fine-tuned on NYC chips on AMD MI300X) over the per-query Sentinel-2/1/DEM chip; binary building-footprint mask + connected-component count",
  gliner_comptroller:     "GLiNER typed extraction over the Comptroller PDF (per-paragraph)",
  gliner_dep_2013:        "GLiNER typed extraction over the DEP wastewater plan",
  gliner_nycha:           "GLiNER typed extraction over the NYCHA Lessons Learned PDF",
  gliner_mta:             "GLiNER typed extraction over the MTA Resilience Roadmap",
  gliner_coned:           "GLiNER typed extraction over the Con Edison Climate Resilience plan",
  noaa_tides:             "live NOAA CO-OPS, 6-min cadence (observation time in payload)",
  nws_alerts:             "live NWS Public Alerts API (effective/expires in payload)",
  nws_obs:                "live NWS hourly METAR observation (observation time in payload)",
  ttm_forecast:           "live TTM forecast based on trailing 51 h at the closest NOAA gauge to this address (Battery / Kings Pt / Sandy Hook)",
  ttm_311_forecast:       "live TTM forecast based on trailing 52 weeks of NYC 311 flood complaints within 200 m of this address",
  floodnet_forecast:      "live TTM forecast based on the 512-day daily flood-event series at the nearest FloodNet sensor",
  ttm_battery:            "live NYC fine-tuned TTM forecast based on the trailing 1024 hours (~43 days) of hourly surge residual at the Battery; 96 h horizon",
  dob_permits:            "live NYC DOB Permit Issuance, trailing 18-month window (per-permit issuance dates in payload)",
  rag_comptroller:        "NYC Comptroller report 'Is NYC Ready for Rain?' (2024)",
  rag_npcc4:              "NPCC4 — NYC Climate Assessment 4th edition, Annals NYAS vol. 1539 (2024)",
  rag_mta:                "MTA Climate Resilience Roadmap, October 2025 update",
  rag_nycha:              "NYCHA Flood Resilience: Lessons Learned (post-Sandy)",
  rag_coned:              "Con Edison Climate Change Resilience Plan, NY PSC Case 22-E-0222 (2023)",
  scope_note:             "Riprap planner — geographic scope guard (this query)",
  live_target:            "Riprap planner — live target (this query)",
  mta_entrance:           "MTA Open Data subway-entrance geometry (refreshed monthly) joined to Sandy 2012 + DEP scenarios + USGS 3DEP DEM",
  nycha_dev:              "NYC Open Data NYCHA Developments (phvi-damg) joined to Sandy 2012 + DEP scenarios + USGS 3DEP DEM",
  doe_school:             "NYC DOE Locations Points (1992 schools) joined to Sandy 2012 + DEP scenarios + USGS 3DEP DEM",
  nyc_hospital:           "NYS DOH Health Facility Certification (vn5v-hh5r, NYC counties + fac_desc_short=HOSP) joined to Sandy 2012 + DEP scenarios + USGS 3DEP DEM",
};

const INTENT_PILL_CLASS = {
  development_check: "dev",
  live_now: "live",
  neighborhood: "nbhd",
  single_address: "addr",
};

// ---------------------------------------------------------------------------
// MAP
// ---------------------------------------------------------------------------

let map = null;
let mapInit = false;

function ensureMap() {
  if (mapInit) return;
  mapInit = true;
  map = new maplibregl.Map({
    container: "map",
    style: {
      version: 8,
      // CARTO Voyager — more editorial typography + softer palette than
      // Positron, no API key required. Retina (@2x) tiles for crisp type.
      sources: {
        basemap: {
          type: "raster",
          tiles: [
            "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png",
            "https://b.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png",
            "https://c.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png",
            "https://d.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png",
          ],
          tileSize: 256,
          attribution: "© OpenStreetMap contributors © CARTO",
        },
      },
      layers: [
        { id: "bg",      type: "background", paint: { "background-color": "#f3f5f8" } },
        { id: "basemap", type: "raster",     source: "basemap" },
      ],
    },
    center: [-74.0, 40.72],
    zoom: 10,
    attributionControl: { compact: true },
    // Required for map.getCanvas().toDataURL() to work on the report-export
    // path. Otherwise the WebGL drawing buffer is cleared after each frame
    // and snapshots come back blank.
    preserveDrawingBuffer: true,
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "top-right");
  map.on("load", initMapSources);
}

function initMapSources() {
  // Sandy + DEP overlays (used for nbhd / dev_check)
  map.addSource("sandy",   { type: "geojson", data: empty() });
  map.addLayer({ id: "sandy-fill", type: "fill", source: "sandy",
    paint: { "fill-color": "#fc5d52", "fill-opacity": 0.25 } });
  map.addLayer({ id: "sandy-line", type: "line", source: "sandy",
    paint: { "line-color": "#fc5d52", "line-width": 0.5, "line-opacity": 0.7 } });

  map.addSource("dep",     { type: "geojson", data: empty() });
  map.addLayer({ id: "dep-fill", type: "fill", source: "dep",
    paint: {
      "fill-color": ["match", ["get", "Flooding_Category"],
        1, "#568adf", 2, "#1642DF", 3, "#031553", "#568adf"],
      "fill-opacity": 0.32 } });

  // Prithvi-EO 2.0 live water-segmentation polygons. Cyan to differ
  // visually from Sandy (red) and DEP (blue) — this is *observed today*
  // water from the latest cloud-free Sentinel-2 scene, not a modeled
  // scenario. We outline + fill so even sliver geometries (river edges,
  // canal banks) show up at street zoom.
  map.addSource("prithvi_live", { type: "geojson", data: empty() });
  map.addLayer({ id: "prithvi-live-fill", type: "fill", source: "prithvi_live",
    paint: { "fill-color": "#48c6eb", "fill-opacity": 0.45 } });
  map.addLayer({ id: "prithvi-live-line", type: "line", source: "prithvi_live",
    paint: { "line-color": "#1aa3c8", "line-width": 1.2, "line-opacity": 0.85 } });

  // TerraMind synthesised LULC polygons — *synthetic-prior* tier
  // (4th epistemic class). Per-feature fill_color carried from the
  // server side so the legend stays in one place. Dashed outline so
  // it visually reads as "synthesized, not observed".
  map.addSource("terramind_lulc", { type: "geojson", data: empty() });
  map.addLayer({ id: "terramind-lulc-fill", type: "fill",
    source: "terramind_lulc",
    paint: {
      "fill-color": ["coalesce", ["get", "fill_color"], "#9ca3af"],
      "fill-opacity": 0.30,
    },
  });
  map.addLayer({ id: "terramind-lulc-line", type: "line",
    source: "terramind_lulc",
    paint: {
      "line-color": ["coalesce", ["get", "fill_color"], "#9ca3af"],
      "line-width": 1.0,
      "line-dasharray": [2, 2],
      "line-opacity": 0.65,
    },
  });
  map.on("click", "terramind-lulc-fill", (e) => {
    const f = e.features[0]; const p = f.properties;
    new maplibregl.Popup().setLngLat(e.lngLat)
      .setHTML(`<b>TerraMind synthetic land-cover</b><br>` +
               `Class: ${escapeHtml(p.label || "")} (tentative)<br>` +
               `<i>Synthesised from LiDAR DEM, not observed.</i>`)
      .addTo(map);
  });

  // NTA polygon outline
  map.addSource("nta", { type: "geojson", data: empty() });
  map.addLayer({ id: "nta-line", type: "line", source: "nta",
    paint: { "line-color": "#0b3b6b", "line-width": 2.4, "line-opacity": 0.9 } });
  map.addLayer({ id: "nta-fill", type: "fill", source: "nta",
    paint: { "fill-color": "#0b3b6b", "fill-opacity": 0.04 } });

  // DOB permit pins
  map.addSource("permits", { type: "geojson", data: empty() });
  map.addLayer({ id: "permits-circles", type: "circle", source: "permits",
    paint: {
      "circle-radius": ["case", ["get", "any_flood"], 6, 4],
      "circle-color": [
        "case",
        ["get", "in_sandy"], "#fc5d52",
        [">=", ["get", "dep_max_class"], 2], "#1642DF",
        [">", ["get", "dep_max_class"], 0], "#568adf",
        "#1a8754",
      ],
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 1.4,
      "circle-opacity": 0.95,
    } });
  map.on("click", "permits-circles", (e) => {
    const f = e.features[0]; const p = f.properties;
    new maplibregl.Popup()
      .setLngLat(f.geometry.coordinates)
      .setHTML(
        `<b>${escapeHtml(p.address || "(unknown)")}</b><br>` +
        `${p.job_type} · ${p.in_sandy === 'true' ? 'Sandy zone' : 'outside Sandy'}<br>` +
        `DEP class: ${p.dep_max_class}`)
      .addTo(map);
  });

  // Address pin (single_address intent)
  map.addSource("addr", { type: "geojson", data: empty() });
  map.addLayer({ id: "addr-pin", type: "circle", source: "addr",
    paint: { "circle-radius": 10, "circle-color": "#0b3b6b",
      "circle-stroke-color": "#fff", "circle-stroke-width": 3 } });

  // Search-radius circles (200 m / 600 m / 800 m). Visualizes the
  // spatial scope each specialist is reading from. Drawn as a thin
  // line so the underlying point data is readable through them.
  map.addSource("scope", { type: "geojson", data: empty() });
  map.addLayer({ id: "scope-line", type: "line", source: "scope",
    paint: { "line-color": "#0b3b6b", "line-width": 1.0,
             "line-opacity": 0.55, "line-dasharray": [3, 3] } });

  // NYC 311 flood complaint pins — coloured by descriptor.
  map.addSource("nyc311_pts", { type: "geojson", data: empty() });
  map.addLayer({ id: "nyc311-circles", type: "circle", source: "nyc311_pts",
    paint: {
      "circle-radius": 4.5,
      "circle-color": ["match", ["get", "descriptor"],
        "Sewer Backup (Use Comments) (SA)",          "#fc5d52",
        "Catch Basin Clogged/Flooding (Use Comments) (SC)", "#f59e0b",
        "Street Flooding (SJ)",                       "#1642DF",
        "Manhole Overflow (Use Comments) (SA1)",     "#8b5cf6",
        "#6b7280",
      ],
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 1.0,
      "circle-opacity": 0.85,
    },
  });
  map.on("click", "nyc311-circles", (e) => {
    const f = e.features[0]; const p = f.properties;
    new maplibregl.Popup().setLngLat(f.geometry.coordinates)
      .setHTML(`<b>311 complaint</b><br>${escapeHtml(p.descriptor || "")}<br>` +
               `${escapeHtml(p.date || "")}<br>${escapeHtml(p.address || "")}`)
      .addTo(map);
  });

  // FloodNet sensors — triangles via SDF circle stand-in (cyan,
  // larger if the sensor has triggered events).
  map.addSource("floodnet_pts", { type: "geojson", data: empty() });
  map.addLayer({ id: "floodnet-circles", type: "circle", source: "floodnet_pts",
    paint: {
      "circle-radius": 7,
      "circle-color": "#48c6eb",
      "circle-stroke-color": "#1aa3c8",
      "circle-stroke-width": 2.0,
      "circle-opacity": 0.95,
    },
  });
  map.on("click", "floodnet-circles", (e) => {
    const f = e.features[0]; const p = f.properties;
    new maplibregl.Popup().setLngLat(f.geometry.coordinates)
      .setHTML(`<b>FloodNet sensor</b><br>${escapeHtml(p.name || p.deployment_id || "")}`)
      .addTo(map);
  });

  // USGS Hurricane Ida 2021 high-water marks — hot orange, sized by height.
  map.addSource("ida_hwm_pts", { type: "geojson", data: empty() });
  map.addLayer({ id: "ida-hwm-circles", type: "circle", source: "ida_hwm_pts",
    paint: {
      "circle-radius": ["interpolate", ["linear"],
        ["coalesce", ["get", "height_above_gnd_ft"], 0],
        0, 4, 3, 7, 6, 11],
      "circle-color": "#ea580c",
      "circle-stroke-color": "#7c2d12",
      "circle-stroke-width": 1.4,
      "circle-opacity": 0.92,
    },
  });
  map.on("click", "ida-hwm-circles", (e) => {
    const f = e.features[0]; const p = f.properties;
    new maplibregl.Popup().setLngLat(f.geometry.coordinates)
      .setHTML(`<b>USGS Ida 2021 high-water mark</b><br>` +
               `${escapeHtml(p.site || "(unnamed)")}<br>` +
               `Elevation: ${p.elev_ft ?? "?"} ft<br>` +
               `Height above ground: ${p.height_above_gnd_ft ?? "?"} ft`)
      .addTo(map);
  });

  // NOAA tide gauge marker — shows which of the 3 gauges is active.
  map.addSource("noaa_gauge", { type: "geojson", data: empty() });
  map.addLayer({ id: "noaa-gauge-marker", type: "circle", source: "noaa_gauge",
    paint: {
      "circle-radius": 9,
      "circle-color": "#0ea5e9",
      "circle-stroke-color": "#fff",
      "circle-stroke-width": 2.5,
    },
  });
  map.on("click", "noaa-gauge-marker", (e) => {
    const f = e.features[0]; const p = f.properties;
    new maplibregl.Popup().setLngLat(f.geometry.coordinates)
      .setHTML(`<b>NOAA tide gauge</b><br>${escapeHtml(p.name || "")}<br>` +
               `Observed water level: ${p.observed_ft ?? "?"} ft MLLW<br>` +
               `Residual (≈ surge): ${p.residual_ft ?? "?"} ft`)
      .addTo(map);
  });
}

// ~3 m/° latitude × cos(lat) for longitude. Build a circle polygon
// approximating a fixed-radius (meters) buffer around (lat, lon).
function metersBuffer(lat, lon, meters, steps = 64) {
  const dLat = meters / 111_000.0;
  const dLon = meters / (111_000.0 * Math.cos(lat * Math.PI / 180));
  const ring = [];
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * 2 * Math.PI;
    ring.push([lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)]);
  }
  return { type: "Polygon", coordinates: [ring] };
}

function empty() { return { type: "FeatureCollection", features: [] }; }

function clearMap() {
  if (!map || !map.getSource) return;
  for (const id of ["sandy", "dep", "nta", "permits", "addr", "prithvi_live",
                    "terramind_lulc",
                    "scope", "nyc311_pts", "floodnet_pts", "ida_hwm_pts",
                    "noaa_gauge"]) {
    const s = map.getSource(id);
    if (s) s.setData(empty());
  }
}

async function fillMapForFinal(d) {
  if (!map || !map.loaded()) {
    map.once("load", () => fillMapForFinal(d));
    return;
  }
  clearMap();
  const intent = d.intent;
  if (intent === "single_address") return fillMapAddress(d);
  if (intent === "neighborhood")   return fillMapNeighborhood(d);
  if (intent === "development_check") return fillMapDevelopment(d);
  if (intent === "live_now")       return fillMapLive(d);
}

async function fillMapAddress(d) {
  const geo = d.geocode;
  if (!geo || !geo.lat) return;
  map.flyTo({ center: [geo.lon, geo.lat], zoom: 15.5, duration: 700 });
  map.getSource("addr").setData({ type: "FeatureCollection",
    features: [{ type: "Feature",
      geometry: { type: "Point", coordinates: [geo.lon, geo.lat] }, properties: {} }] });
  // Fetch Sandy + DEP layers clipped to address
  try {
    const r = await fetch(`/api/layers/sandy?lat=${geo.lat}&lon=${geo.lon}&r=1500`);
    map.getSource("sandy").setData(await r.json());
  } catch {}
  try {
    const r = await fetch(`/api/layers/dep_extreme_2080?lat=${geo.lat}&lon=${geo.lon}&r=1500`);
    map.getSource("dep").setData(await r.json());
  } catch {}
  // Prithvi-EO live water mask comes inlined in the SSE final event,
  // not via a separate /api/layers fetch — it's per-query, not corpus.
  const live = d.prithvi_live;
  if (live && live.ok && live.polygons_geojson && map.getSource("prithvi_live")) {
    map.getSource("prithvi_live").setData(live.polygons_geojson);
  }

  // TerraMind synthesised LULC polygons — same per-query pattern.
  const tm = d.terramind;
  if (tm && tm.ok && tm.polygons_geojson && map.getSource("terramind_lulc")) {
    map.getSource("terramind_lulc").setData(tm.polygons_geojson);
  }

  // ---- search-radius scope rings (200 m / 600 m / 800 m) ----
  // Three rings matching the buffers each specialist actually reads:
  // 200 m for 311, 600 m for FloodNet sensors, 800 m for Ida HWMs.
  if (map.getSource("scope")) {
    map.getSource("scope").setData({
      type: "FeatureCollection",
      features: [200, 600, 800].map(r => ({
        type: "Feature",
        geometry: metersBuffer(geo.lat, geo.lon, r),
        properties: { radius_m: r },
      })),
    });
  }

  // ---- NYC 311 flood complaint pins ----
  const c311 = d.nyc311 || {};
  const c311Pts = c311.points || [];
  if (map.getSource("nyc311_pts")) {
    map.getSource("nyc311_pts").setData({
      type: "FeatureCollection",
      features: c311Pts.filter(p => p.lat && p.lon).map(p => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [p.lon, p.lat] },
        properties: {
          descriptor: p.descriptor || "",
          date: p.date || "",
          address: p.address || "",
        },
      })),
    });
  }

  // ---- FloodNet sensors ----
  const fn = d.floodnet || {};
  const fnSensors = fn.sensors || [];
  if (map.getSource("floodnet_pts")) {
    map.getSource("floodnet_pts").setData({
      type: "FeatureCollection",
      features: fnSensors.filter(s => s.lat && s.lon).map(s => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [s.lon, s.lat] },
        properties: {
          name: s.name || s.deployment_id || "",
          deployment_id: s.deployment_id || "",
        },
      })),
    });
  }

  // ---- USGS Ida 2021 HWMs ----
  const hwm = d.ida_hwm || {};
  const hwmPts = hwm.points || [];
  if (map.getSource("ida_hwm_pts")) {
    map.getSource("ida_hwm_pts").setData({
      type: "FeatureCollection",
      features: hwmPts.filter(p => p.lat && p.lon).map(p => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [p.lon, p.lat] },
        properties: {
          site: p.site || "",
          elev_ft: p.elev_ft,
          height_above_gnd_ft: p.height_above_gnd_ft,
        },
      })),
    });
  }

  // ---- NOAA tide gauge marker ----
  const tides = d.noaa_tides || {};
  if (tides.station_id && tides.station_lat && tides.station_lon &&
      map.getSource("noaa_gauge")) {
    map.getSource("noaa_gauge").setData({
      type: "FeatureCollection",
      features: [{
        type: "Feature",
        geometry: { type: "Point",
                    coordinates: [tides.station_lon, tides.station_lat] },
        properties: {
          name: tides.station_name || tides.station_id,
          observed_ft: tides.observed_ft_mllw,
          residual_ft: tides.residual_ft,
        },
      }],
    });
  }
}

async function fillMapNeighborhood(d) {
  const t = d.target;
  if (!t || !t.bbox || !t.nta_code) return;
  const [minx, miny, maxx, maxy] = t.bbox;
  map.fitBounds([[minx, miny], [maxx, maxy]], { padding: 32, duration: 700 });
  const [r1, r2, r3] = await Promise.all([
    fetch(`/api/layers/nta?code=${t.nta_code}`).then(r => r.json()),
    fetch(`/api/layers/sandy_clipped?code=${t.nta_code}`).then(r => r.json()).catch(() => empty()),
    fetch(`/api/layers/dep_clipped?code=${t.nta_code}&scenario=dep_extreme_2080`).then(r => r.json()).catch(() => empty()),
  ]);
  map.getSource("nta").setData(r1);
  map.getSource("sandy").setData(r2);
  map.getSource("dep").setData(r3);
  // Prithvi-EO live water mask (NTA centroid) — same per-query GeoJSON
  // as the single_address path; clipped visually to the NTA polygon by
  // the basemap zoom.
  const live = d.prithvi_live;
  if (live && live.ok && live.polygons_geojson && map.getSource("prithvi_live")) {
    map.getSource("prithvi_live").setData(live.polygons_geojson);
  }
  // TerraMind synthesised LULC at NTA centroid.
  const tm = d.terramind;
  if (tm && tm.ok && tm.polygons_geojson && map.getSource("terramind_lulc")) {
    map.getSource("terramind_lulc").setData(tm.polygons_geojson);
  }
}

async function fillMapDevelopment(d) {
  await fillMapNeighborhood(d);  // same NTA + Sandy + DEP overlays
  const pins = ((d.dob_summary || {}).all_pins) || [];
  const fc = {
    type: "FeatureCollection",
    features: pins.filter(p => p.lat && p.lon).map(p => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.lon, p.lat] },
      properties: {
        address: p.address, job_type: p.job_type,
        in_sandy: !!p.in_sandy, any_flood: !!p.any_flood,
        dep_max_class: p.dep_max_class || 0,
      },
    })),
  };
  map.getSource("permits").setData(fc);
}

function fillMapLive(d) {
  // NYC overview with the 3 NOAA gauges
  map.flyTo({ center: [-74.0, 40.7], zoom: 10, duration: 700 });
}

// Fire as each FSM step completes, so the map updates progressively
// instead of waiting for the `final` event. Each branch is idempotent —
// it's safe if `final` later overwrites with the same data.
async function incrementallyFillMap(step) {
  if (!map || !map.loaded()) {
    map.once("load", () => incrementallyFillMap(step));
    return;
  }
  const r = step.result || {};
  // Address mode — geocode just resolved
  if (step.step === "geocode" && r.lat != null && r.lon != null) {
    map.flyTo({ center: [r.lon, r.lat], zoom: 15.5, duration: 700 });
    map.getSource("addr").setData({ type: "FeatureCollection",
      features: [{ type: "Feature",
        geometry: { type: "Point", coordinates: [r.lon, r.lat] }, properties: {} }] });
    Promise.all([
      fetch(`/api/layers/sandy?lat=${r.lat}&lon=${r.lon}&r=1500`).then(x => x.json()).catch(() => empty()),
      fetch(`/api/layers/dep_extreme_2080?lat=${r.lat}&lon=${r.lon}&r=1500`).then(x => x.json()).catch(() => empty()),
    ]).then(([s, d]) => {
      map.getSource("sandy").setData(s);
      map.getSource("dep").setData(d);
    });
    return;
  }
  // Neighborhood / dev_check — NTA polygon resolved
  if (step.step === "nta_resolve" && r.nta_code && r.bbox) {
    const [minx, miny, maxx, maxy] = r.bbox;
    map.fitBounds([[minx, miny], [maxx, maxy]], { padding: 32, duration: 700 });
    Promise.all([
      fetch(`/api/layers/nta?code=${r.nta_code}`).then(x => x.json()).catch(() => empty()),
      fetch(`/api/layers/sandy_clipped?code=${r.nta_code}`).then(x => x.json()).catch(() => empty()),
      fetch(`/api/layers/dep_clipped?code=${r.nta_code}&scenario=dep_extreme_2080`).then(x => x.json()).catch(() => empty()),
    ]).then(([n, s, d]) => {
      map.getSource("nta").setData(n);
      map.getSource("sandy").setData(s);
      map.getSource("dep").setData(d);
    });
    return;
  }
  // Dev_check — DOB permits arrived; pin them now
  if (step.step === "dob_permits_nta" && Array.isArray(r.all_pins)) {
    const fc = { type: "FeatureCollection",
      features: r.all_pins.filter(p => p.lat && p.lon).map(p => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [p.lon, p.lat] },
        properties: {
          address: p.address, job_type: p.job_type,
          in_sandy: !!p.in_sandy, any_flood: !!p.any_flood,
          dep_max_class: p.dep_max_class || 0,
        },
      })) };
    map.getSource("permits").setData(fc);
    return;
  }
}

// ---------------------------------------------------------------------------
// REPORT (paragraph) RENDERING
// ---------------------------------------------------------------------------

function escapeHtml(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

let CITE_INDEX = {};
// Resolve a doc_id to its source-label family. Register specialists emit
// per-asset doc_ids like `mta_entrance_54` / `nycha_dev_004` — for those
// we strip the trailing `_<id>` and look up the family key.
const _FAMILY_PREFIXES = ["mta_entrance", "nycha_dev", "doe_school", "nyc_hospital"];
function _docIdFamily(norm) {
  for (const fam of _FAMILY_PREFIXES) {
    if (norm.startsWith(fam + "_")) return fam;
  }
  return null;
}
function _resolveSourceLabel(norm) {
  if (SOURCE_LABELS[norm]) return SOURCE_LABELS[norm];
  const fam = _docIdFamily(norm);
  return fam ? SOURCE_LABELS[fam] : norm;
}
function rewriteCitations(html) {
  return html.replace(/\[([a-z0-9_]+)\]/gi, (_, id) => {
    const norm = id.toLowerCase();
    if (CITE_INDEX[norm] == null) CITE_INDEX[norm] = Object.keys(CITE_INDEX).length + 1;
    const n = CITE_INDEX[norm];
    return `<span class="cite" data-src-id="${norm}" data-src-n="${n}" title="${_resolveSourceLabel(norm)} — click to highlight in Sources">${n}</span>`;
  });
}

// Sources footer is a Lit web component (<r-sources-footer>) — driven
// by the citeIndex signal in /static/components/signals.js. We feed
// it the labels/urls/vintages once at boot and update the signal as
// the briefing markdown is rendered.
async function renderSources() {
  const el = document.getElementById("sourcesFooter");
  if (!el) return;
  // Module is loaded async; wait for define() then push fresh data.
  await customElements.whenDefined("r-sources-footer");
  el.labels = SOURCE_LABELS;
  el.urls = SOURCE_URLS;
  el.vintages = SOURCE_VINTAGES;
  // Push the citation index into the shared signal — the component
  // re-renders reactively.
  const { citeIndex } = await import("/static/components/signals.js");
  citeIndex.set({ ...CITE_INDEX });
}

function renderMarkdown(text) {
  // Block recognizer:
  //   `**Header.**`     (own line)  →  <h4>
  //   lines starting `- ` or `* `   →  bullet items collected into <ul>
  //   anything else                 →  <p>
  // Inline `**foo**` → <strong>
  const lines = text.split("\n");
  const out = [];
  let para = []; let bullets = [];
  const flushPara = () => {
    if (!para.length) return;
    const safe = escapeHtml(para.join(" ").trim()).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    if (safe) out.push(`<p class="rsum-p">${safe}</p>`);
    para = [];
  };
  const flushBullets = () => {
    if (!bullets.length) return;
    const items = bullets.map(b => {
      const safe = escapeHtml(b.trim()).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
      return `<li>${safe}</li>`;
    }).join("");
    out.push(`<ul class="rsum-list">${items}</ul>`);
    bullets = [];
  };
  // Granite sometimes runs all bullets onto one line separated by " - ";
  // pre-split those so each becomes its own bullet.
  const expanded = [];
  for (const line of lines) {
    if (line.trim().startsWith("- ") && line.includes(" - ", 2)) {
      // split into bullets
      const parts = line.split(/(?:^|(?<=\.\s))\s*-\s+/g).filter(p => p.trim());
      for (const p of parts) expanded.push("- " + p.trim());
    } else {
      expanded.push(line);
    }
  }
  for (const line of expanded) {
    const m = line.match(/^\s*\*\*([A-Z][A-Za-z\s/]+)\.\*\*\s*$/);
    if (m) {
      flushPara(); flushBullets();
      out.push(`<h4 class="rsum-h">${escapeHtml(m[1])}</h4>`);
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      flushPara();
      bullets.push(line.replace(/^\s*[-*]\s+/, ""));
    } else {
      flushBullets();
      para.push(line);
    }
  }
  flushPara(); flushBullets();
  return out.join("");
}

// Briefing is now the Lit <r-briefing> web component. It owns markdown
// rendering, citation chip binding, and pushing CITE_INDEX into the
// shared signal — agent.js just feeds it `.text` + `.sourceLabels`.
async function setBriefingText(text) {
  const el = document.getElementById("paragraph");
  if (!el) return;
  await customElements.whenDefined("r-briefing");
  el.sourceLabels = SOURCE_LABELS;
  el.text = text || "";
}
function renderParagraph(text) { setBriefingText(text); }

// ---------------------------------------------------------------------------
// FACTS PANEL — intent-specific quick-look stats below the map
// ---------------------------------------------------------------------------

function renderFacts(d) {
  const intent = d.intent;
  const panel = $("#factsPanel");
  const body = $("#factsBody");
  panel.style.display = "";
  if (intent === "neighborhood")        renderNbhdFacts(d, body);
  else if (intent === "development_check") renderDevFacts(d, body);
  else if (intent === "live_now")       renderLiveFacts(d, body);
  else if (intent === "single_address") renderAddressFacts(d, body);
}

function renderNbhdFacts(d, body) {
  $("#factsTitle").textContent = `Findings — ${d.target?.nta_name || ""}`;
  const s = d.sandy_nta || {}; const dep = d.dep_nta || {};
  const m = d.microtopo_nta || {}; const c = d.nyc311_nta || {};
  const sandyPct = s.fraction != null ? (s.fraction * 100).toFixed(1) + "%" : "—";
  const dep80 = (dep.dep_extreme_2080 || {}).fraction_any;
  const dep50 = (dep.dep_moderate_2050 || {}).fraction_any;
  body.innerHTML = `
    <div class="headline-stat">${sandyPct}</div>
    <div class="headline-sub">of the neighborhood is inside the 2012 Sandy Inundation Zone</div>
    <dl class="facts-grid">
      <dt>DEP Extreme 2080</dt><dd>${dep80!=null ? (dep80*100).toFixed(1)+"%" : "—"}</dd>
      <dt>DEP Moderate 2050</dt><dd>${dep50!=null ? (dep50*100).toFixed(1)+"%" : "—"}</dd>
      <dt>311 (3 yr)</dt><dd>${c.n ?? "—"} flood complaints</dd>
      <dt>HAND median</dt><dd>${m.hand_median_m != null ? m.hand_median_m+" m" : "—"}</dd>
      <dt>HAND &lt; 1 m fraction</dt><dd>${m.frac_hand_lt1 != null ? (m.frac_hand_lt1*100).toFixed(0)+"%" : "—"}</dd>
      <dt>TWI median</dt><dd>${m.twi_median ?? "—"}</dd>
    </dl>`;
}

function renderDevFacts(d, body) {
  $("#factsTitle").textContent = `Active construction — ${d.target?.nta_name || ""}`;
  const ds = d.dob_summary || {};
  body.innerHTML = `
    <div class="headline-stat">${ds.n_in_sandy ?? 0} <span style="color:var(--text-muted); font-size:18px; font-weight:400;">/ ${ds.n_total ?? 0}</span></div>
    <div class="headline-sub">active projects inside the Sandy zone</div>
    <dl class="facts-grid">
      <dt>Total active</dt><dd>${ds.n_total ?? 0}</dd>
      <dt>In any DEP scenario</dt><dd>${ds.n_in_dep_any ?? 0}</dd>
      <dt>In severe DEP (≥1 ft)</dt><dd>${ds.n_in_dep_severe ?? 0}</dd>
      <dt>By job type</dt><dd>${Object.entries(ds.by_job_type || {}).map(([k,v]) => `${v} ${k}`).join(", ")}</dd>
    </dl>`;
}

function renderLiveFacts(d, body) {
  $("#factsTitle").textContent = `Live conditions — ${d.place || "NYC"}`;
  const t = d.noaa_tides || {}; const a = d.nws_alerts || {}; const o = d.nws_obs || {};
  const ttm = d.ttm_forecast || {};
  const r = t.residual_ft;
  body.innerHTML = `
    <div class="headline-stat">${a.n_active ?? 0} alerts</div>
    <div class="headline-sub">active flood-relevant NWS alerts at this point</div>
    <dl class="facts-grid">
      <dt>Tide gauge</dt><dd>${t.station_name || "—"}</dd>
      <dt>Observed</dt><dd>${t.observed_ft_mllw != null ? t.observed_ft_mllw+" ft MLLW" : "—"}</dd>
      <dt>Residual</dt><dd>${r != null ? (r >= 0 ? "+" : "")+r+" ft" : "—"}</dd>
      <dt>Nearest ASOS</dt><dd>${o.station_id || "—"}</dd>
      <dt>Precip 1h</dt><dd>${o.precip_last_hour_mm != null ? o.precip_last_hour_mm+" mm" : "—"}</dd>
      <dt>TTM peak (next 9.6h)</dt><dd>${ttm.forecast_peak_ft != null ? ttm.forecast_peak_ft+" ft" : "—"}</dd>
    </dl>`;
}

function renderAddressFacts(d, body) {
  $("#factsTitle").textContent = "Findings";
  const geo = d.geocode || {};
  const dep = d.dep || {}; const e80 = (dep.dep_extreme_2080 || {});
  const m = d.microtopo || {};
  body.innerHTML = `
    <div class="headline-sub">${geo.address || "—"}</div>
    <dl class="facts-grid">
      <dt>Sandy zone</dt><dd>${d.sandy ? "INSIDE" : "outside"}</dd>
      <dt>DEP Extreme 2080</dt><dd>${e80.depth_label || "—"}</dd>
      <dt>HAND</dt><dd>${m.hand_m != null ? m.hand_m+" m" : "—"}</dd>
      <dt>TWI</dt><dd>${m.twi ?? "—"}</dd>
      <dt>Elev pct (200m)</dt><dd>${m.rel_elev_pct_200m ?? "—"}</dd>
      <dt>311 (5y, 200m)</dt><dd>${(d.nyc311 || {}).n ?? "—"}</dd>
    </dl>`;
}

// ---------------------------------------------------------------------------
// TRACE PANEL
// ---------------------------------------------------------------------------

// Trace list is a Lit web component (<r-trace>); pushTraceStep delegates
// once the component is registered. STEP_LABELS is set on the element
// at boot.
async function pushTraceStep(step) {
  const el = document.getElementById("steps");
  if (!el) return;
  await customElements.whenDefined("r-trace");
  if (!el.stepLabels || !Object.keys(el.stepLabels).length) {
    el.stepLabels = STEP_LABELS;
  }
  el.pushStep(step);
}

async function clearTrace() {
  const el = document.getElementById("steps");
  if (el) {
    await customElements.whenDefined("r-trace");
    el.clear();
  }
  $("#traceMeta").textContent = "";
}

// --------------------------------------------------------------------------
// Loading-state and chrome helpers
// --------------------------------------------------------------------------

function setMapLoading(text) {
  const el = $("#mapLoading");
  if (!el) return;
  if (text) {
    el.style.display = "";
    $("#mapLoadingText").textContent = text;
  } else {
    el.style.display = "none";
  }
}

function setLegend(intent) {
  const el = $("#mapLegend");
  if (!el) return;
  // Reusable legend rows shared across intents.
  const empirical = `
      <div class="legend-row"><span class="legend-swatch fill" style="background:#fc5d52; opacity:0.4"></span>Sandy 2012 extent</div>
      <div class="legend-row"><span class="legend-swatch fill" style="background:#1642DF; opacity:0.4"></span>DEP Extreme-2080</div>`;
  const points = `
      <div class="legend-row"><span class="legend-swatch" style="background:#fc5d52; border-radius:50%"></span>311 — sewer backup</div>
      <div class="legend-row"><span class="legend-swatch" style="background:#f59e0b; border-radius:50%"></span>311 — catch basin</div>
      <div class="legend-row"><span class="legend-swatch" style="background:#1642DF; border-radius:50%"></span>311 — street flooding</div>
      <div class="legend-row"><span class="legend-swatch" style="background:#48c6eb; border:2px solid #1aa3c8; border-radius:50%"></span>FloodNet sensor</div>
      <div class="legend-row"><span class="legend-swatch" style="background:#ea580c; border:1px solid #7c2d12; border-radius:50%"></span>Ida 2021 high-water mark</div>
      <div class="legend-row"><span class="legend-swatch" style="background:#0ea5e9; border:2px solid #fff; border-radius:50%; outline:1px solid #ccc"></span>NOAA tide gauge</div>`;
  // Synthetic-prior tier — distinct visual idiom (dashed) so users
  // immediately read it as "generated, not observed".
  const synthetic = `
      <div style="font-weight:700; font-size:9.5px; text-transform:uppercase; letter-spacing:0.06em; color:var(--text-muted); margin-top:6px; margin-bottom:2px">Synthetic priors (not observed)</div>
      <div class="legend-row"><span class="legend-swatch fill" style="background:#48c6eb; opacity:0.45"></span>Prithvi-EO 2.0 — live water mask</div>
      <div class="legend-row"><span class="legend-swatch fill" style="background:#16a34a; opacity:0.30; border:1px dashed #16a34a"></span>TerraMind — synthetic LULC (DEM→ESRI Land Cover, dashed = generated)</div>`;

  if (intent === "development_check") {
    el.innerHTML = `
      <div style="font-weight:700; font-size:9.5px; text-transform:uppercase; letter-spacing:0.06em; color:var(--text-muted); margin-bottom:4px">Active permits</div>
      <div class="legend-row"><span class="legend-swatch" style="background:#fc5d52"></span>Inside Sandy zone</div>
      <div class="legend-row"><span class="legend-swatch" style="background:#1642DF"></span>DEP deep band (≥1 ft)</div>
      <div class="legend-row"><span class="legend-swatch" style="background:#568adf"></span>DEP nuisance band</div>
      <div class="legend-row"><span class="legend-swatch" style="background:#1a8754"></span>No flood layer</div>
      <div class="legend-row" style="margin-top:6px">${empirical}</div>${synthetic}`;
    el.style.display = "";
  } else if (intent === "neighborhood") {
    el.innerHTML = `${empirical}
      <div class="legend-row"><span class="legend-swatch fill" style="background:transparent; border:2px solid #0b3b6b"></span>NTA boundary</div>${synthetic}`;
    el.style.display = "";
  } else if (intent === "single_address") {
    el.innerHTML = `
      <div class="legend-row"><span class="legend-swatch" style="background:#0b3b6b"></span>Address</div>${empirical}${points}${synthetic}`;
    el.style.display = "";
  } else {
    el.style.display = "none";
  }
}

// Mirrors app/score.py.composite() — see ARCHITECTURE.md / METHODOLOGY.md.
// Used only for the single_address intent badge; neighborhood and
// development_check have their own headline stats in the facts panel.
const REG_W = { fema_1pct: 1.0, fema_02pct: 0.5,
  dep_moderate_2050: 0.75, dep_extreme_2080: 0.50, dep_tidal_2050: 0.75 };
const HYD_W = { hand_band: 1.0, twi_quartile: 0.5,
  elev_pct_200m_inv: 0.5, elev_pct_750m_inv: 0.5, basin_relief_band: 0.25 };
const EMP_W = { sandy: 1.0, ida_hwm_within_100m: 1.0, ida_hwm_within_800m: 0.5,
  prithvi_polygon: 0.75, complaints_band: 0.75, floodnet_trigger: 0.75 };
const handBand   = h => h == null ? 0 : (h < 1 ? 1 : h < 3 ? 0.66 : h < 10 ? 0.33 : 0);
const pctInvBand = p => p == null ? 0 : (p < 10 ? 1 : p < 25 ? 0.66 : p < 50 ? 0.33 : 0);
const twiBand    = t => t == null ? 0 : (t >= 12 ? 1 : t >= 10 ? 0.66 : t >= 8 ? 0.33 : 0);
const reliefBand = r => r == null ? 0 : (r >= 8 ? 1 : r >= 4 ? 0.66 : r >= 2 ? 0.33 : 0);
const complBand  = n => !n ? 0 : (n >= 10 ? 1 : n >= 3 ? 0.66 : 0.33);
const sumW = w => Object.values(w).reduce((a, b) => a + b, 0);

function computeComposite(ev) {
  const dep = ev.dep || {}, mt = ev.microtopo || {}, ida = ev.ida_hwm || {}, pw = ev.prithvi_water || {};
  const s = {
    fema_1pct: false, fema_02pct: false,
    dep_moderate_2050: (dep.dep_moderate_2050?.depth_class || 0) > 0,
    dep_extreme_2080:  (dep.dep_extreme_2080?.depth_class || 0) > 0,
    dep_tidal_2050:    false,
    hand_m: mt.hand_m, twi: mt.twi,
    rel_elev_pct_200m: mt.rel_elev_pct_200m,
    rel_elev_pct_750m: mt.rel_elev_pct_750m,
    basin_relief_m: mt.basin_relief_m,
    sandy: !!ev.sandy,
    ida_hwm_within_100m: (ida.nearest_dist_m != null && ida.nearest_dist_m < 100),
    ida_hwm_within_800m: (ida.n_within_radius || 0) > 0,
    prithvi_polygon: !!pw.inside_water_polygon,
    complaints_count: ev.nyc311?.n || 0,
    floodnet_trigger: (ev.floodnet?.n_flood_events_3y || 0) > 0,
  };
  let regRaw = 0; for (const [k, w] of Object.entries(REG_W)) regRaw += s[k] ? w : 0;
  const reg = regRaw / sumW(REG_W);
  const hb = { hand_band: handBand(s.hand_m), twi_quartile: twiBand(s.twi),
    elev_pct_200m_inv: pctInvBand(s.rel_elev_pct_200m),
    elev_pct_750m_inv: pctInvBand(s.rel_elev_pct_750m),
    basin_relief_band: reliefBand(s.basin_relief_m) };
  let hydRaw = 0; for (const [k, w] of Object.entries(HYD_W)) hydRaw += w * hb[k];
  const hyd = hydRaw / sumW(HYD_W);
  const ev2 = { sandy: s.sandy ? 1 : 0,
    ida_hwm_within_100m: s.ida_hwm_within_100m ? 1 : 0,
    ida_hwm_within_800m: s.ida_hwm_within_800m ? 1 : 0,
    prithvi_polygon: s.prithvi_polygon ? 1 : 0,
    complaints_band: complBand(s.complaints_count),
    floodnet_trigger: s.floodnet_trigger ? 1 : 0 };
  let empRaw = 0; for (const [k, w] of Object.entries(EMP_W)) empRaw += w * ev2[k];
  const emp = empRaw / sumW(EMP_W);
  const composite = reg + hyd + emp;
  let tier = 0;
  if (composite >= 1.50) tier = 1;
  else if (composite >= 1.00) tier = 2;
  else if (composite >= 0.50) tier = 3;
  else if (composite >= 0.01) tier = 4;
  const floorApplied = !!(s.sandy || s.ida_hwm_within_100m);
  if (floorApplied && (tier === 0 || tier > 2)) tier = 2;
  return { tier, composite, floorApplied,
           sub: { regulatory: reg, hydrological: hyd, empirical: emp } };
}

function tierMeta(tier) {
  if (tier === 1) return { tier, label: "High exposure",
    help: "Multiple sub-indices saturated. Not a damage probability." };
  if (tier === 2) return { tier, label: "Elevated exposure",
    help: "At least one sub-index near saturation. Not a damage probability." };
  if (tier === 3) return { tier, label: "Moderate exposure",
    help: "Partial signals across categories. Not a damage probability." };
  if (tier === 4) return { tier, label: "Limited exposure",
    help: "A single contextual signal." };
  return { tier: 0, label: "No flagged exposure",
    help: "No positive flood signal across the assessed sources." };
}

function renderBriefHead(d) {
  const intent = d.intent;
  const place = (d.target && d.target.nta_name)
    || (d.geocode && d.geocode.address)
    || d.place || "—";
  const meta = [];
  const eyebrowMap = {
    single_address:    "Flood-exposure briefing — address",
    neighborhood:      "Flood-exposure briefing — neighborhood",
    development_check: "Active development × flood exposure",
    live_now:          "Current conditions — NYC",
  };
  $("#briefEyebrow").textContent = eyebrowMap[intent] || "Briefing";
  $("#briefTitle").innerHTML = escapeHtml(place);

  // For single_address intent, append the tier badge inline with the title
  // — same idiom as the legacy /single page.
  if (intent === "single_address") {
    const c = computeComposite(d);
    const m = tierMeta(c.tier);
    const titleEl = $("#briefTitle");
    const floor = c.floorApplied ? ' <span class="tier-floor">empirical floor</span>' : "";
    titleEl.innerHTML += ` <span class="tier-chip t-${m.tier}" title="${escapeHtml(m.help)}">
        Tier ${m.tier} · ${escapeHtml(m.label)}${floor}
      </span>`;
  }

  // Mellea compliance badge — present iff strict mode ran and produced
  // metadata. Color reflects pass ratio: green for full, amber partial,
  // red none.
  if (d.mellea) {
    const m = d.mellea;
    const passed = (m.requirements_passed || []).length;
    const total = m.requirements_total || 0;
    const cls = passed === total ? "full"
              : passed > 0       ? "partial"
              :                    "none";
    const tip = `Mellea (IBM Research) ran ${m.n_attempts} attempt${m.n_attempts === 1 ? "" : "s"}` +
                ` (${m.rerolls} reroll${m.rerolls === 1 ? "" : "s"}). ` +
                `Requirements passed: ${(m.requirements_passed || []).join(", ") || "none"}. ` +
                (m.requirements_failed?.length
                  ? `Failed: ${m.requirements_failed.join(", ")}.` : "");
    $("#briefTitle").innerHTML +=
      ` <span class="mellea-badge ${cls}" title="${escapeHtml(tip)}">` +
      `<span class="ico">✓</span>Mellea ${passed}/${total}` +
      (m.rerolls > 0 ? ` · ${m.rerolls} reroll${m.rerolls === 1 ? "" : "s"}` : "") +
      `</span>`;
  }
  if (intent === "single_address" && d.geocode) {
    if (d.geocode.borough) meta.push(`<span class="brief-meta-k">borough</span> <span class="brief-meta-v">${escapeHtml(d.geocode.borough)}</span>`);
    if (d.geocode.bbl)     meta.push(`<span class="brief-meta-k">bbl</span> <span class="brief-meta-v">${escapeHtml(d.geocode.bbl)}</span>`);
  } else if (d.target && d.target.borough) {
    meta.push(`<span class="brief-meta-k">borough</span> <span class="brief-meta-v">${escapeHtml(d.target.borough)}</span>`);
    if (d.target.nta_code) meta.push(`<span class="brief-meta-k">nta</span> <span class="brief-meta-v">${escapeHtml(d.target.nta_code)}</span>`);
  }
  if (d.total_s != null) meta.push(`<span class="brief-meta-k">runtime</span> <span class="brief-meta-v">${d.total_s}s</span>`);
  meta.push(`<span class="brief-meta-k">assessed</span> <span class="brief-meta-v">${new Date().toISOString().slice(0,16).replace("T"," ")}</span>`);
  $("#briefMeta").innerHTML = meta.join('<span style="color:var(--text-faint)">·</span>');
}

// ---------------------------------------------------------------------------
// PLANNER ROW
// ---------------------------------------------------------------------------

function renderPlan(p) {
  const pillCls = INTENT_PILL_CLASS[p.intent] || "";
  $("#plannerRow").innerHTML = `
    <div class="planner-box">
      <div class="planner-key">Planner</div>
      <div><span class="intent-pill ${pillCls}">${escapeHtml(p.intent)}</span></div>
      <div class="planner-key">Targets</div>
      <div class="planner-val">${(p.targets || []).map(t => escapeHtml(t.type) + ":" + escapeHtml(t.text)).join(", ") || "(none)"}</div>
      <div class="planner-key">Specialists</div>
      <div class="planner-val">${(p.specialists || []).join(", ")}</div>
      <div class="planner-rationale">"${escapeHtml(p.rationale || "")}"</div>
    </div>`;
}

// ---------------------------------------------------------------------------
// SSE driver
// ---------------------------------------------------------------------------

let currentEs = null;
// Buffers for the report-export feature — capture the full plan, trace,
// and final result during streaming so the report page can render the
// complete evidence package without re-running the agent.
let LAST_RESULT = null;
let LAST_TRACE = [];
let LAST_PLAN = null;
let LAST_PLAN_OBJ = null;
let TRACE_BUF = [];

function ask(q) {
  ensureMap();
  clearTrace(); clearMap();
  $("#plannerRow").innerHTML = "";
  setBriefingText("");
  $("#paragraph").classList.remove("streaming");
  const banner = $("#melleaBanner");
  if (banner) { banner.style.display = "none"; banner.innerHTML = ""; }
  $("#reportPanel").style.display = "none";
  $("#factsPanel").style.display = "none";
  $("#reportSkel").style.display = "";
  $("#traceSkel").style.display = "";
  $("#mapLegend").style.display = "none";
  setMapLoading("Granite is planning the query…");
  $("#goBtn").disabled = true;
  $("#traceMeta").textContent = "…";

  if (currentEs) currentEs.close();
  const es = new EventSource("/api/agent/stream?q=" + encodeURIComponent(q));
  currentEs = es;
  const t0 = Date.now();
  let streamBuf = "";
  let streamTimer = null;
  let planStreamBuf = "";
  let planStreamTimer = null;
  const ensurePlannerStream = () => {
    let el = $("#plannerRow .planner-streaming");
    if (!el) {
      $("#plannerRow").innerHTML = `<div class="planner-streaming"></div>`;
      el = $("#plannerRow .planner-streaming");
    }
    return el;
  };
  const repaintPlanner = () => {
    const el = $("#plannerRow .planner-streaming");
    if (el) el.textContent = planStreamBuf;
  };
  const schedulePlannerRepaint = () => {
    if (planStreamTimer) return;
    planStreamTimer = setTimeout(() => { planStreamTimer = null; repaintPlanner(); }, 60);
  };
  // Re-render the partial markdown on every token, but at most every 80 ms
  // so the browser isn't murdered by a token-stream that arrives in bursts.
  // Build the Sources footer alongside so it grows as new doc_ids appear.
  // Briefing component owns citation indexing + chip binding via shared
  // signals; we just feed it the latest text. Sources footer reacts to
  // the citeIndex signal that <r-briefing> updates each render.
  const repaint = () => {
    setBriefingText(streamBuf);
    renderSources();
  };
  const scheduleRepaint = () => {
    if (streamTimer) return;
    streamTimer = setTimeout(() => { streamTimer = null; repaint(); }, 80);
  };

  es.addEventListener("plan_token", (e) => {
    ensurePlannerStream();
    const d = JSON.parse(e.data);
    planStreamBuf += d.delta || "";
    schedulePlannerRepaint();
  });
  es.addEventListener("plan",  (e) => {
    if (planStreamTimer) { clearTimeout(planStreamTimer); planStreamTimer = null; }
    const planObj = JSON.parse(e.data);
    LAST_PLAN_OBJ = planObj;
    renderPlan(planObj);
    setLegend(planObj.intent);
    setMapLoading(planObj.intent === "live_now" ? null : "Resolving location…");
    $("#traceSkel").style.display = "none";
    TRACE_BUF = [];
    $("#reportBtn").classList.remove("ready");
  });
  es.addEventListener("step", (e) => {
    const step = JSON.parse(e.data);
    TRACE_BUF.push(step);
    incrementallyFillMap(step);
    if (step.step === "geocode" || step.step === "nta_resolve") setMapLoading(null);
  });
  es.addEventListener("step",  (e) => { pushTraceStep(JSON.parse(e.data)); });

  // Stones envelope — `stone_start` and `stone_done` events bracket
  // the contiguous step events of each Stone group. The current
  // `<r-trace>` Svelte build doesn't yet render parent/child rows;
  // we accumulate Stone markers in TRACE_BUF for the auditable report,
  // and surface a lightweight badge on the trace component so users
  // can see Cornerstone / Keystone / Touchstone / Lodestone / Capstone
  // lighting up sequentially. The full collapsible parent-row UI
  // lands once the trace component is rebuilt against this event
  // vocabulary.
  es.addEventListener("stone_start", (e) => {
    const stone = JSON.parse(e.data);
    TRACE_BUF.push({ _stone: "start", ...stone });
    const trace = $("#trace");
    if (trace && typeof trace.markStoneStart === "function") {
      trace.markStoneStart(stone);
    }
  });
  es.addEventListener("stone_done", (e) => {
    const stone = JSON.parse(e.data);
    TRACE_BUF.push({ _stone: "done", ...stone });
    const trace = $("#trace");
    if (trace && typeof trace.markStoneDone === "function") {
      trace.markStoneDone(stone);
    }
  });
  let currentAttempt = 0;
  es.addEventListener("token", (e) => {
    const d = JSON.parse(e.data);
    if (!streamBuf || (d.attempt != null && d.attempt !== currentAttempt)) {
      // First token of a (possibly new) attempt → reveal panel, reset
      // buffer if Mellea moved to a reroll.
      if (d.attempt != null && d.attempt !== currentAttempt) {
        currentAttempt = d.attempt;
        streamBuf = "";
      }
      $("#reportSkel").style.display = "none";
      $("#reportPanel").style.display = "";
      $("#paragraph").classList.add("streaming");
    }
    streamBuf += d.delta || "";
    scheduleRepaint();
  });
  // Mellea per-attempt outcome — render a small banner above the briefing
  // when a reroll is about to start so the user knows the model is
  // self-correcting (and what failed).
  es.addEventListener("mellea_attempt", (e) => {
    const d = JSON.parse(e.data);
    const banner = $("#melleaBanner");
    if (!banner) return;
    if (d.failed && d.failed.length) {
      banner.className = "mellea-banner reroll";
      banner.innerHTML = `<strong>↻ Mellea reroll</strong> — attempt ${(d.attempt|0)+1} failed: <code>${d.failed.join(", ")}</code>. Re-drafting…`;
      banner.style.display = "";
    } else {
      banner.className = "mellea-banner pass";
      banner.innerHTML = `<strong>✓ Mellea</strong> — all 4 grounding requirements satisfied`;
      banner.style.display = "";
    }
  });
  es.addEventListener("final", (e) => {
    const d = JSON.parse(e.data);
    const dt = ((Date.now() - t0) / 1000).toFixed(1);
    $("#traceMeta").textContent = `${dt}s`;
    setMapLoading(null);
    $("#reportSkel").style.display = "none";
    $("#paragraph").classList.remove("streaming");
    if (d.paragraph) {
      $("#reportPanel").style.display = "";
      streamBuf = d.paragraph;
      if (streamTimer) { clearTimeout(streamTimer); streamTimer = null; }
      repaint();
      renderBriefHead(d);
    }
    renderFacts(d);
    fillMapForFinal(d);
    // Stash everything needed for the auditable-report page.
    LAST_RESULT = { query: q, finishedAt: new Date().toISOString(),
                    wallSeconds: Number(dt), result: d };
    LAST_TRACE = TRACE_BUF.slice();
    LAST_PLAN = LAST_PLAN_OBJ;
    $("#reportBtn").classList.add("ready");
  });
  es.addEventListener("error", () => {});
  es.addEventListener("done", () => { es.close(); $("#goBtn").disabled = false; });
}

// ---------------------------------------------------------------------------
// wire
// ---------------------------------------------------------------------------

// Bind form/sample handlers FIRST so a throw in ensureMap() (e.g. a
// WebGL init failure) can't strand the user with a dead "Ask" button.
$("#agentForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = $("#q").value.trim();
  if (q) ask(q);
});
document.querySelectorAll(".sample-btn").forEach(b => {
  b.addEventListener("click", () => { $("#q").value = b.dataset.q; ask(b.dataset.q); });
});
try { ensureMap(); } catch (e) { console.error("ensureMap failed:", e); }

// Backend hardware pill: fetches /api/backend, renders "<HW> · <ENGINE>"
// and a state color (green=primary up, amber=fallback active, red=down).
// Refreshes every 60s so a flipped droplet shows up without a page reload.
async function refreshBackendPill() {
  const pill = document.getElementById("backendPill");
  const text = document.getElementById("backendPillText");
  if (!pill || !text) return;
  try {
    const r = await fetch("/api/backend", { cache: "no-store" });
    if (!r.ok) throw new Error("status " + r.status);
    const info = await r.json();
    const onFallback = info.reachable === false && !!info.fallback_engine;
    const engine = onFallback ? info.fallback_engine : info.engine;
    const hw = onFallback ? "fallback" : info.hardware;
    text.textContent = `${hw} · Granite 4.1 / ${engine}`;
    pill.dataset.state =
      info.reachable ? "ok" :
      onFallback ? "fallback" : "down";
    const detail = info.vllm_base_url
      ? `Primary: ${info.engine} @ ${info.vllm_base_url}`
      : `Engine: ${info.engine}`;
    pill.title = info.reachable
      ? `${detail} — reachable. No vendor LLM is contacted.`
      : onFallback
      ? `${detail} unreachable; running on ${info.fallback_engine} fallback.`
      : `${detail} — UNREACHABLE.`;
  } catch (e) {
    text.textContent = "backend unknown";
    pill.dataset.state = "down";
    pill.title = "Could not query /api/backend: " + e.message;
  }
}
refreshBackendPill();
setInterval(refreshBackendPill, 60000);

// Subscribe to the shared highlight signal so vanilla-rendered citation
// chips in the briefing prose mirror the highlight state driven by the
// Lit <r-sources-footer> (and vice versa).
(async () => {
  const { highlightedDocId } = await import("/static/components/signals.js");
  const apply = () => {
    const id = highlightedDocId.get();
    document.querySelectorAll("#paragraph .cite").forEach(c => {
      c.classList.toggle("hl", c.dataset.srcId === id);
    });
  };
  // Lit-labs/signals exposes a subscribe / effect — try both shapes.
  if (typeof highlightedDocId.subscribe === "function") {
    highlightedDocId.subscribe(apply);
  } else {
    // Polyfill: poll on mutation. Cheap; signal updates are rare.
    const orig = highlightedDocId.set.bind(highlightedDocId);
    highlightedDocId.set = (v) => { orig(v); apply(); };
  }
})();

// "Generate auditable report" — snapshots the live map, packs the full
// evidence (query / plan / per-specialist trace / final result / per-source
// vintages / labels / urls), parks it in sessionStorage, opens /report.
$("#reportBtn").addEventListener("click", () => {
  if (!LAST_RESULT) return;
  let mapPng = null;
  try {
    if (map && map.loaded()) {
      // preserveDrawingBuffer:false would force a one-frame render here
      map.triggerRepaint();
      mapPng = map.getCanvas().toDataURL("image/png");
    }
  } catch (e) {
    console.warn("map snapshot failed", e);
  }
  const pkg = {
    ...LAST_RESULT,
    plan: LAST_PLAN,
    trace: LAST_TRACE,
    mapPng,
    sourceLabels: SOURCE_LABELS,
    sourceUrls: SOURCE_URLS,
    sourceVintages: SOURCE_VINTAGES,
    stepLabels: STEP_LABELS,
  };
  try {
    sessionStorage.setItem("riprap_report", JSON.stringify(pkg));
    window.open("/report", "_blank");
  } catch (e) {
    alert("Could not stash report payload (storage may be full): " + e.message);
  }
});
