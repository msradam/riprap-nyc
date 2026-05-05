/* Riprap v0.4.4 · Findings region.
   Card grammar: a small set of body variants any Stone's specialists render into.
   Variants: tabular, headline, visualization, raster-thumbnail, time-series,
             composite-register (novel), comparison (novel · EMP vs SYN), text-headline.
   Common chrome: header (source badge + tier glyph + vintage) → title → body → footer (source ID + tier badge).
*/

const { useState: useFi, useMemo: useFiMemo } = React;

/* ─── Card data ─── */

const CARDS_BY_QUERY = {
  redhook: {
    cornerstone: ["fc-fema", "fc-hwm", "fc-stormwater"],
    keystone:    ["fc-register-rh"],
    touchstone:  ["fc-floodnet", "fc-311", "fc-nws", "fc-terramind-lulc", "fc-prithvi-pluvial"],
    lodestone:   ["fc-ttm-surge", "fc-ttm-surge-ft", "fc-npcc4"],
    capstone:    ["fc-mellea-meta"],
  },
  bronx: {
    cornerstone: ["fc-fema-x", "fc-stormwater-bx"],
    keystone:    ["fc-register-bx"],
    touchstone:  ["fc-311-bx", "fc-nws"],
    lodestone:   [],   /* full-Stone silence: address is inland, no Battery surge relevance */
    capstone:    ["fc-mellea-meta-bx"],
  },
};

const CARDS = {
  /* ── Cornerstone ── */
  "fc-fema": {
    stone: "cornerstone", tier: "modeled", variant: "headline",
    source: "FEMA", agency: "Federal Emergency Management Agency",
    title: "Preliminary FIRM, panel 36047C0207G",
    headline: "Zone AE", subhead: "BFE 11 ft NAVD88 · freeboard +4.8 ft",
    body: "Address sits within the regulatory 1% annual-chance floodplain. Base Flood Elevation 11.0 ft NAVD88; first floor must be at or above this datum for NFIP rating.",
    docId: "FEMA-FIRM-36047C0207G", vintage: "2024-09", citeId: "c4",
    mapKey: "fema-ae",
  },
  "fc-hwm": {
    stone: "cornerstone", tier: "empirical", variant: "tabular",
    source: "USGS", agency: "U.S. Geological Survey",
    title: "Post-Sandy high-water marks within 500 ft",
    columns: ["id", "elev.", "dist."],
    rows: [
      ["HWM-NY-3081", "7.4 ft NAVD88", "0.18 mi"],
      ["HWM-NY-3082", "8.1 ft NAVD88", "0.22 mi"],
      ["HWM-NY-3105", "6.8 ft NAVD88", "0.31 mi"],
    ],
    sub: "3 marks · max 8.1 ft · surveyed Nov 2012",
    docId: "USGS-OFR-2013-1234", vintage: "2013-05", citeId: "c1",
    mapKey: "hwm",
  },
  "fc-stormwater": {
    stone: "cornerstone", tier: "modeled", variant: "raster",
    source: "NYC DEP", agency: "NYC Dept. of Environmental Protection",
    title: "Stormwater Flood Map · moderate scenario",
    rasterKind: "stormwater",
    sub: "2.13 in/hr · ponding ≥4 in W half of lot · routed toward Imlay St",
    docId: "NYCDEP-SWFM-2024", vintage: "2024-06", citeId: "c5",
    mapKey: "stormwater",
  },
  "fc-fema-x": {
    stone: "cornerstone", tier: "modeled", variant: "headline",
    source: "FEMA", agency: "Federal Emergency Management Agency",
    title: "Preliminary FIRM, panel 36005C0152F",
    headline: "Zone X", subhead: "outside the 1% annual-chance floodplain",
    body: "Address is in Zone X, the unshaded 0.2% annual-chance area or higher ground. NFIP coverage optional; insurance not mandated.",
    docId: "FEMA-FIRM-36005C0152F", vintage: "2024-09", citeId: "cx1",
    mapKey: "fema-x",
  },
  "fc-stormwater-bx": {
    stone: "cornerstone", tier: "modeled", variant: "raster",
    source: "NYC DEP", agency: "NYC Dept. of Environmental Protection",
    title: "Stormwater Flood Map · moderate scenario",
    rasterKind: "stormwater-dry",
    sub: "2.13 in/hr · no ponding ≥4 in within parcel · upslope grade 3.4%",
    docId: "NYCDEP-SWFM-2024", vintage: "2024-06", citeId: "cx2",
    mapKey: "stormwater",
  },

  /* ── Keystone (composite register) ── */
  "fc-register-rh": {
    stone: "keystone", tier: "empirical", variant: "register",
    source: "NYC OpenData", agency: "NYC OpenData · multi-agency join",
    title: "Nearby exposed assets",
    registers: [
      { reg: "MTA",   tier: "empirical", label: null, detail: null, sourceId: null, vintage: null, note: "no entrances within radius" },
      { reg: "NYCHA", tier: "empirical", label: null, detail: null, sourceId: null, vintage: null, note: "no NYCHA developments within 1.0 mi" },
      { reg: "DOE",   tier: "empirical", label: null, detail: null, sourceId: null, vintage: null, note: "no DOE schools within 1.0 mi" },
      { reg: "DOH",   tier: "empirical", label: null, detail: null, sourceId: null, vintage: null, note: "no acute-care hospitals within 1.0 mi" },
      { reg: "PLUTO", tier: "empirical", label: null, detail: null, sourceId: null, vintage: null, note: "PLUTO join skipped: queried address not in NYC PLUTO dataset" },
    ],
    sub: "5 specialists · 5 silent_by_design · 0 cards landed (full inventory shown)",
    docId: "RIPRAP-EXP-RH80", vintage: "2026-05", citeId: "c-reg-rh",
    mapKey: "registers",
  },
  "fc-register-bx": {
    stone: "keystone", tier: "empirical", variant: "register",
    source: "NYC OpenData", agency: "NYC OpenData · multi-agency join",
    title: "Nearby exposed assets",
    registers: [
      { reg: "MTA",   tier: "empirical", label: "Pelham Pkwy 5 station",       detail: "0.18 mi · 5",          sourceId: "MTA-ENT-N122",  vintage: "2025-11", note: null },
      { reg: "NYCHA", tier: "empirical", label: null,                            detail: null,                   sourceId: null,             vintage: null,       note: "no NYCHA developments within 1.0 mi (silent)" },
      { reg: "DOE",   tier: "empirical", label: "PS 89 Cinco Estrellas",       detail: "0.22 mi · 612 K-5",    sourceId: "DOE-X089",      vintage: "2024-25", note: null },
      { reg: "DOH",   tier: "empirical", label: "Jacobi Medical Center",       detail: "0.51 mi · 457 beds",   sourceId: "DOH-JMC",        vintage: "2025-Q1", note: null },
      { reg: "PLUTO", tier: "empirical", label: "Lot 36005 / 4382 / 18",       detail: "BIN 2098441 · R5",     sourceId: "PLUTO-2024v2",   vintage: "2024-12", note: null },
    ],
    sub: "4 of 5 registers fired · 1 silent · joined within 1.0 mi",
    docId: "RIPRAP-EXP-BX12", vintage: "2026-05", citeId: "cx-reg",
    mapKey: "registers",
  },

  /* ── Touchstone ── */
  "fc-floodnet": {
    stone: "touchstone", tier: "empirical", variant: "spark",
    source: "FloodNet", agency: "FloodNet NYC sensor network",
    title: "Sensor BK-RH-002, monthly above-curb events",
    headline: "7 events", subhead: "Jun 2024 → Apr 2026 · peak 14.3 cm",
    spark: [0,0,1,0,2,1,0,0,3,0,1,0,0,0,2,1,0,0,1,0,2,4,1,1],
    sparkSub: "Sensor located 0.21 mi N at Coffey & Van Brunt. Above-curb depth in cm; events ≥2 cm.",
    docId: "FN-BK-RH-002", vintage: "2026-04", citeId: "c3",
    mapKey: "floodnet",
  },
  "fc-311": {
    stone: "touchstone", tier: "proxy", variant: "histogram",
    source: "NYC 311", agency: "NYC 311 service requests",
    title: "Recent 311 flood complaints, BK CB6",
    headline: "89 calls", subhead: "2019–2025 · seasonal cluster Aug–Oct",
    histogram: [3,2,1,0,1,4,7,12,18,11,5,3,4,2,1,0,2,3,8,9,4,2,1,0],
    sparkSub: "Filtered to complaint types: Sewer (Backup), Street Flooding, Catch Basin Clogged. Within 200 m of address.",
    docId: "NYC311-FLD-CB6", vintage: "2025-12", citeId: "c7",
    mapKey: "complaints",
  },
  "fc-311-bx": {
    stone: "touchstone", tier: "proxy", variant: "histogram",
    source: "NYC 311", agency: "NYC 311 service requests",
    title: "Recent 311 flood complaints, BX CB11",
    headline: "12 calls", subhead: "2019–2025 · sparse · no seasonal cluster",
    histogram: [0,0,1,0,0,1,0,1,2,0,0,0,1,0,0,0,1,0,2,1,1,0,0,1],
    sparkSub: "Filtered to complaint types: Sewer (Backup), Street Flooding, Catch Basin Clogged. Within 200 m of address.",
    docId: "NYC311-FLD-CB11", vintage: "2025-12", citeId: "cx7",
    mapKey: "complaints",
  },
  "fc-prithvi-pluvial": {
    stone: "touchstone", tier: "modeled", variant: "raster-pred",
    source: "Prithvi-NYC-Pluvial", agency: "NASA-IBM Prithvi v2 · NYC fine-tune",
    title: "Pluvial flood prediction · Prithvi-NYC-Pluvial",
    rasterKind: "prithvi",
    headline: "0.3% flooded", subhead: "no flooding apparent · scene 2026-05-02",
    sub: "Model interpretation of imagery, not real-time observation. Confidence-mean 0.84 across non-flooded pixels.",
    docId: "PRITHVI-NYC-PLUV-V2-20260502", vintage: "2026-05-02 · Sentinel-2",
    illustrative: true, citeId: "c-prithvi",
    mapKey: "prithvi-pluvial",
  },
  "fc-terramind-lulc": {
    stone: "touchstone", tier: "synthetic", variant: "lulc",
    source: "TerraMind v1.2", agency: "IBM TerraMind v1.2 · Sentinel-2 inputs",
    title: "Land use / land cover · TerraMind v1.2",
    rasterKind: "lulc",
    classMix: [
      { k: "urban",      pct: 62, color: "#C66" },
      { k: "water",      pct: 18, color: "#5B7FB4" },
      { k: "vegetation", pct: 12, color: "#5B8A4A" },
      { k: "barren",     pct:  6, color: "#A89A78" },
      { k: "wetland",    pct:  2, color: "#D9C75A" },
    ],
    sub: "Synthetic prior. LULC palette is a layer convention, not a tier signal.",
    docId: "TERRAMIND-LULC-20240918", vintage: "Sentinel-2 · 2024-09-18",
    citeId: "c-tm-lulc",
    mapKey: "terramind-lulc",
  },
  "fc-nws": {
    stone: "touchstone", tier: "empirical", variant: "scalars",
    source: "NWS KNYC", agency: "NOAA · National Weather Service",
    title: "Current weather, station KNYC",
    scalars: [
      { value: "0.02 in", label: "precip · last 24h" },
      { value: "67°F",    label: "temp · current" },
      { value: "PC", label: "conditions" },
    ],
    sub: "Observation timestamp 2026-05-05 14:18 ET. Central Park station; not point-of-query.",
    docId: "NWS-KNYC", vintage: "2026-05-05", citeId: "c-nws",
    mapKey: "nws",
  },

  /* ── Lodestone ── */
  "fc-ttm-surge": {
    stone: "lodestone", tier: "modeled", variant: "timeseries",
    source: "Granite TTM r2 (zero-shot)", agency: "IBM Granite-TimeSeries · regional",
    title: "Storm surge nowcast at The Battery — 9.6 h horizon (regional)",
    timeseries: { hours: 96, peak: { x: 38, y: 47 }, peakLabel: "+47 cm @ +38h" },
    headline: "+47 cm", subhead: "peak surge residual · 9.6h horizon · 6-min cadence",
    sub: "Regional disclosure. Nowcast applies city-wide via NOAA station 8518750. Distinct from the fine-tuned Battery surge nowcast.",
    docId: "ttm_battery_surge_zeroshot", vintage: "2026-05-05 12:00 ET",
    spatialNote: "regional · The Battery, not point-of-query",
    citeId: "c-ttm",
    mapKey: null,
  },
  "fc-ttm-surge-ft": {
    stone: "lodestone", tier: "modeled", variant: "timeseries-ft",
    source: "msradam/Granite-TTM-r2-Battery-Surge", agency: "Granite TTM r2 · NYC-specialized fine-tune",
    title: "Storm surge nowcast at The Battery — 96 h horizon (NYC-specialized fine-tune)",
    timeseries: { hours: 96, peak: { x: 38, y: 53 }, peakLabel: "+53 cm @ +38h" },
    headline: "+53 cm", subhead: "peak surge · 96h horizon · hourly cadence",
    sub: "Fine-tuned on NYC tide-gauge history. Trained on AMD MI300X.",
    docId: "ttm_battery_surge_finetune", vintage: "2026-05-05 12:00 ET",
    spatialNote: "regional · The Battery, not point-of-query",
    hfModelCard: "huggingface.co/msradam/Granite-TTM-r2-Battery-Surge",
    rmse: "0.157 m",
    skillVsPersistence: "−35% vs persistence",
    hardwareBadge: "MI300X",
    citeId: "c-ttm-ft",
    mapKey: null,
  },
  "fc-npcc4": {
    stone: "lodestone", tier: "modeled", variant: "forecast",
    source: "NPCC4", agency: "NYC Panel on Climate Change, 4th Assessment",
    title: "Sea-level rise projections, Lower NY Harbor",
    forecast: [
      { year: 2030, low: 4,  mid: 6,  high: 9   },
      { year: 2050, low: 13, mid: 22, high: 30  },
      { year: 2080, low: 28, mid: 49, high: 75  },
      { year: 2100, low: 38, mid: 71, high: 114 },
    ],
    sub: "inches MSL · 17th–83rd %ile range, median line. Battery tide-gauge baseline.",
    docId: "NPCC4-Ch3-Tbl3.2", vintage: "2024-03", citeId: "c6",
    mapKey: null,
  },

  /* ── Capstone meta ── */
  "fc-mellea-meta": {
    stone: "capstone", tier: "modeled", variant: "meta",
    source: "Mellea", agency: "Capstone synthesis · grounding check",
    title: "Briefing reconciliation",
    metaRows: [
      { k: "Mellea reroll",      v: "1 reroll" },
      { k: "Grounding checks",   v: "4 / 4 passed" },
      { k: "Citations resolved", v: "4" },
      { k: "Wall-clock",         v: "24.0 s" },
    ],
    sub: "Capstone produces prose, not cards. This meta-card summarizes the reconciler chain that wrote the four-section briefing above.",
    docId: "RIPRAP-CAP-RH80", vintage: "2026-05-05 14:22 ET", citeId: null,
    mapKey: null,
  },
  "fc-mellea-meta-bx": {
    stone: "capstone", tier: "modeled", variant: "meta",
    source: "Mellea", agency: "Capstone synthesis · grounding check",
    title: "Briefing reconciliation",
    metaRows: [
      { k: "Mellea reroll",     v: "1 attempt" },
      { k: "Grounding checks",  v: "4 / 4 passed" },
      { k: "Citations resolved",v: "6 / 6" },
      { k: "RAG → GLiNER",      v: "5 entities · 0 unresolved" },
    ],
    sub: "Capstone produces prose, not cards. This meta-card summarizes the reconciler chain.",
    docId: "RIPRAP-CAP-BX12", vintage: "2026-05-05 14:24 ET", citeId: null,
    mapKey: null,
  },
};

/* Comparison card · only included when "showComparison" is on (novel variant the brief flags as v1.1 idea). */
const COMPARISON_CARD = {
  stone: "keystone", tier: "synthetic", variant: "comparison",
  source: "TerraMind × DOITT", agency: "TerraMind v1.2 Buildings × NYC DOITT footprints",
  title: "Building footprint · documented vs. interpreted",
  left:  { tier: "empirical",  label: "DOITT (documented)",   value: "31.4%", aux: "112 building polygons in chip" },
  right: { tier: "synthetic",  label: "TerraMind (interpreted)", value: "36.2%", aux: "126 components · Sentinel-2 2026-05-02" },
  delta: "+4.8 pp · model sees ~14 unrecorded structures",
  sub: "Difference layer. v1.1 idea: surface where the foundation model sees buildings the catalogue doesn't, or vice versa. Illustrative — not part of v0.4.4 production output.",
  docId: "RIPRAP-CMP-RH80-BLDG", vintage: "2026-05-02", citeId: null,
  illustrative: true, mapKey: "buildings",
};

/* ─── Stone metadata ─── */

const STONE_META = {
  cornerstone: { name: "Cornerstone", role: "the hazard reader",  tag: "what NYC's ground remembers" },
  keystone:    { name: "Keystone",    role: "the asset register", tag: "what's exposed" },
  touchstone:  { name: "Touchstone",  role: "the live observer",  tag: "what's happening now" },
  lodestone:   { name: "Lodestone",   role: "the projector",      tag: "what's coming" },
  capstone:    { name: "Capstone",    role: "the synthesizer",    tag: "writes it all down with citations" },
};

const STONE_ORDER = ["cornerstone", "keystone", "touchstone", "lodestone", "capstone"];

/* ─── Tier badge (footer) ─── */

const FiTierBadge = ({ tier }) => {
  const map = { empirical: "EMP", modeled: "MOD", proxy: "PRX", synthetic: "SYN" };
  return (
    <span className={`fc-tier-badge fc-tier-badge-${tier}`} aria-label={`epistemic tier ${map[tier]}`}>
      <window.TierGlyph tier={tier} size={9}/>
      <span>{map[tier]}</span>
    </span>
  );
};

/* ─── Body variants ─── */

const BodyHeadline = ({ c }) => (
  <div className="fc-body fc-body-headline">
    <div className="fc-headline" style={{ color: `var(--tier-${c.tier})` }}>{c.headline}</div>
    <div className="fc-subhead">{c.subhead}</div>
    {c.body && <p className="fc-body-prose">{c.body}</p>}
  </div>
);

const BodyTabular = ({ c }) => (
  <div className="fc-body fc-body-tabular">
    <table className="fc-table">
      <thead><tr>{c.columns.map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
      <tbody>
        {c.rows.map((row, i) => (
          <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>
        ))}
      </tbody>
    </table>
    {c.sub && <div className="fc-body-sub">{c.sub}</div>}
  </div>
);

const BodySpark = ({ c }) => {
  const data = c.spark || c.histogram;
  const max = Math.max(...data, 1);
  const w = 240, h = 38, n = data.length;
  return (
    <div className="fc-body fc-body-spark">
      <div className="fc-headline" style={{ color: `var(--tier-${c.tier})` }}>{c.headline}</div>
      <div className="fc-subhead">{c.subhead}</div>
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} preserveAspectRatio="none" aria-hidden="true">
        {data.map((v, i) => (
          <rect
            key={i}
            x={(i / n) * w + 0.5}
            y={h - (v / max) * h}
            width={Math.max(2, w / n - 1.5)}
            height={(v / max) * h}
            fill={`var(--tier-${c.tier})`}
          />
        ))}
      </svg>
      {c.sparkSub && <div className="fc-body-sub">{c.sparkSub}</div>}
    </div>
  );
};

const BodyForecast = ({ c }) => {
  const data = c.forecast;
  const w = 240, h = 88, pad = 6;
  const xs = data.map((_, i) => pad + (i / (data.length - 1)) * (w - pad * 2));
  const max = Math.max(...data.map(d => d.high));
  const y = (v) => h - pad - (v / max) * (h - pad * 2 - 12);
  const path = (key) => xs.map((x, i) => `${i ? "L" : "M"} ${x} ${y(data[i][key])}`).join(" ");
  const range = xs.map((x, i) => ({ x, lo: y(data[i].low), hi: y(data[i].high) }));
  const areaD = `M ${range.map(r => `${r.x} ${r.lo}`).join(" L ")} L ${[...range].reverse().map(r => `${r.x} ${r.hi}`).join(" L ")} Z`;
  const color = `var(--tier-${c.tier})`;
  return (
    <div className="fc-body fc-body-forecast">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} aria-hidden="true">
        <path d={areaD} fill={color} fillOpacity="0.18"/>
        <path d={path("mid")} fill="none" stroke={color} strokeWidth="1.5"/>
        {data.map((d, i) => (
          <g key={i}>
            <circle cx={xs[i]} cy={y(d.mid)} r="2.2" fill={color}/>
            <text x={xs[i]} y={h - 1} fontSize="9" fontFamily="IBM Plex Mono" textAnchor="middle" fill="#6B6B6B">{d.year}</text>
          </g>
        ))}
      </svg>
      {c.sub && <div className="fc-body-sub">{c.sub}</div>}
    </div>
  );
};

const BodyTimeseries = ({ c }) => {
  const w = 240, h = 84, pad = 6;
  const hours = c.timeseries.hours;
  /* Synthetic surge curve: harmonic baseline + storm pulse around peak */
  const points = Array.from({ length: hours + 1 }, (_, i) => {
    const t = i;
    const harmonic = 6 * Math.sin((t / 12.42) * Math.PI * 2);
    const pulse = 38 * Math.exp(-Math.pow((t - c.timeseries.peak.x) / 12, 2));
    return { x: t, y: harmonic + pulse + 4 };
  });
  const maxY = Math.max(...points.map(p => p.y), c.timeseries.peak.y);
  const minY = Math.min(...points.map(p => p.y), -10);
  const sx = (t) => pad + (t / hours) * (w - pad * 2);
  const sy = (v) => h - pad - 14 - ((v - minY) / (maxY - minY)) * (h - pad * 2 - 14);
  const pathD = points.map((p, i) => `${i ? "L" : "M"} ${sx(p.x)} ${sy(p.y)}`).join(" ");
  const color = `var(--tier-${c.tier})`;
  return (
    <div className="fc-body fc-body-timeseries">
      <div className="fc-ts-header">
        <span className="fc-headline" style={{ color }}>{c.headline}</span>
        <span className="fc-subhead">{c.subhead}</span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} aria-hidden="true">
        <line x1={pad} y1={sy(0)} x2={w - pad} y2={sy(0)} stroke="#C9C9C5" strokeWidth="0.5" strokeDasharray="2 2"/>
        <path d={pathD} fill="none" stroke={color} strokeWidth="1.4"/>
        <circle cx={sx(c.timeseries.peak.x)} cy={sy(c.timeseries.peak.y)} r="3" fill={color}/>
        <text x={sx(c.timeseries.peak.x)} y={sy(c.timeseries.peak.y) - 6} fontSize="9" fontFamily="IBM Plex Mono" textAnchor="middle" fill={color}>{c.timeseries.peakLabel}</text>
        <text x={pad} y={h - 2} fontSize="8" fontFamily="IBM Plex Mono" fill="#6B6B6B">now</text>
        <text x={w - pad} y={h - 2} fontSize="8" fontFamily="IBM Plex Mono" textAnchor="end" fill="#6B6B6B">+96h</text>
      </svg>
      <div className="fc-body-sub">
        <span className="fc-spatial-note">{c.spatialNote}</span>
        <span>{c.sub}</span>
      </div>
    </div>
  );
};

const BodyScalars = ({ c }) => (
  <div className="fc-body fc-body-scalars">
    <div className="fc-scalars-row">
      {c.scalars.map((s, i) => (
        <div key={i} className="fc-scalar-cell">
          <div className="fc-scalar-value" style={{ color: `var(--tier-${c.tier})` }}>{s.value}</div>
          <div className="fc-scalar-label">{s.label}</div>
        </div>
      ))}
    </div>
    {c.sub && <div className="fc-body-sub">{c.sub}</div>}
  </div>
);

/* Raster thumbnail · hand-drawn SVG approximations using each layer's conventional palette. */
const RasterThumb = ({ kind }) => {
  const w = 240, h = 120;
  if (kind === "stormwater") {
    return (
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} aria-hidden="true" style={{ display: "block" }}>
        <rect width={w} height={h} fill="#F2F2EE"/>
        {/* street grid */}
        <g stroke="#D9D6CC" strokeWidth="0.6">
          <line x1="0" y1="40" x2={w} y2="40"/><line x1="0" y1="80" x2={w} y2="80"/>
          <line x1="60" y1="0" x2="60" y2={h}/><line x1="160" y1="0" x2="160" y2={h}/>
        </g>
        {/* ponding */}
        <path d="M20 50 Q 60 38 90 56 Q 120 76 150 64 Q 180 50 180 86 Q 130 100 70 96 Q 30 92 20 76 Z" fill="rgba(42,111,168,0.32)" stroke="#2A6FA8" strokeWidth="0.7"/>
        <path d="M40 60 Q 80 54 110 70 Q 140 84 160 78 Q 165 90 130 92 Q 80 90 50 82 Z" fill="rgba(11,83,148,0.36)" stroke="#0B5394" strokeWidth="0.6"/>
        <circle cx="120" cy="74" r="3.2" fill="#D17C00" stroke="#FAFAF7" strokeWidth="1.3"/>
        <text x={w - 6} y={h - 5} fontSize="8" fontFamily="IBM Plex Mono" textAnchor="end" fill="#6B6B6B">2.13 in/hr · MOD</text>
      </svg>
    );
  }
  if (kind === "stormwater-dry") {
    return (
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} aria-hidden="true" style={{ display: "block" }}>
        <rect width={w} height={h} fill="#F2F2EE"/>
        <g stroke="#D9D6CC" strokeWidth="0.6">
          <line x1="0" y1="40" x2={w} y2="40"/><line x1="0" y1="80" x2={w} y2="80"/>
          <line x1="60" y1="0" x2="60" y2={h}/><line x1="160" y1="0" x2="160" y2={h}/>
        </g>
        <path d="M180 92 Q 200 88 215 96 Q 220 105 200 104 Q 185 102 180 96 Z" fill="rgba(42,111,168,0.18)" stroke="#2A6FA8" strokeWidth="0.5" strokeDasharray="2 2"/>
        <circle cx="120" cy="60" r="3.2" fill="#D17C00" stroke="#FAFAF7" strokeWidth="1.3"/>
        <text x={w - 6} y={h - 5} fontSize="8" fontFamily="IBM Plex Mono" textAnchor="end" fill="#6B6B6B">no ponding · MOD</text>
      </svg>
    );
  }
  if (kind === "prithvi") {
    /* Prithvi: 50% Sentinel RGB · 50% pluvial mask. Mostly dry → speckle, no flood polygons. */
    return (
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} aria-hidden="true" style={{ display: "block" }}>
        <defs>
          <pattern id="s2-rgb" x="0" y="0" width="6" height="6" patternUnits="userSpaceOnUse">
            <rect width="6" height="6" fill="#7A8E6A"/>
            <rect x="0" y="0" width="3" height="3" fill="#8D9C7A"/>
            <rect x="3" y="3" width="3" height="3" fill="#69795D"/>
          </pattern>
        </defs>
        <rect width={w} height={h} fill="url(#s2-rgb)"/>
        {/* roads / impervious */}
        <rect x="0" y="55" width={w} height="6" fill="#A8A496"/>
        <rect x="115" y="0" width="8" height={h} fill="#A8A496"/>
        {/* tiny flood blob (0.3%) */}
        <ellipse cx="50" cy="92" rx="6" ry="3" fill="#2A6FA8" fillOpacity="0.65"/>
        <text x="6" y="14" fontSize="9" fontFamily="IBM Plex Mono" fill="#FAFAF7">PRITHVI · 0.3%</text>
        <text x={w - 6} y={h - 5} fontSize="8" fontFamily="IBM Plex Mono" textAnchor="end" fill="#FAFAF7">scene 2026-05-02</text>
      </svg>
    );
  }
  if (kind === "lulc") {
    return (
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} aria-hidden="true" style={{ display: "block" }}>
        <rect width={w} height={h} fill="#F2F2EE"/>
        {/* developed (red) blocks */}
        <rect x="0" y="0" width="80" height="60" fill="#C66"/>
        <rect x="80" y="0" width="60" height="60" fill="#C66"/>
        <rect x="140" y="0" width="100" height="38" fill="#C66"/>
        {/* water */}
        <rect x="140" y="38" width="100" height="22" fill="#5B7FB4"/>
        {/* developed lower */}
        <rect x="0" y="60" width="100" height="60" fill="#C66"/>
        {/* forest patch */}
        <rect x="100" y="60" width="50" height="40" fill="#5B8A4A"/>
        {/* herbaceous */}
        <rect x="150" y="60" width="50" height="60" fill="#D9C75A"/>
        <rect x="200" y="60" width="40" height="60" fill="#C66"/>
        <rect x="100" y="100" width="50" height="20" fill="#A89A78"/>
        <text x="6" y="14" fontSize="9" fontFamily="IBM Plex Mono" fill="#FAFAF7">LULC · TerraMind</text>
        <text x={w - 6} y={h - 5} fontSize="8" fontFamily="IBM Plex Mono" textAnchor="end" fill="#FAFAF7">scene 2026-05-02</text>
      </svg>
    );
  }
  if (kind === "buildings") {
    return (
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} aria-hidden="true" style={{ display: "block" }}>
        <rect width={w} height={h} fill="#3A3A38"/>
        {/* building polygons */}
        {[
          [10,10,28,18],[42,10,30,16],[78,10,40,22],[124,10,32,18],[162,10,30,18],[198,10,32,18],
          [10,32,28,16],[42,30,30,18],[124,32,32,16],[162,32,30,16],[198,32,32,16],
          [10,55,28,18],[42,55,30,18],[78,55,40,18],[124,55,32,18],[162,55,30,18],[198,55,32,18],
          [10,80,28,16],[42,80,30,16],[78,80,40,16],[124,80,32,16],[162,80,30,16],
          [10,100,28,12],[42,100,30,12],[78,100,40,12],
        ].map(([x,y,bw,bh], i) => (
          <rect key={i} x={x} y={y} width={bw} height={bh} fill="rgba(42,111,168,0.55)" stroke="#2A6FA8" strokeWidth="0.4"/>
        ))}
        <text x="6" y="14" fontSize="9" fontFamily="IBM Plex Mono" fill="#FAFAF7">BLDG · TerraMind</text>
        <text x={w - 6} y={h - 5} fontSize="8" fontFamily="IBM Plex Mono" textAnchor="end" fill="#FAFAF7">36.2% built</text>
      </svg>
    );
  }
  return <div className="fc-thumb-placeholder">raster preview</div>;
};

const BodyRaster = ({ c }) => (
  <div className="fc-body fc-body-raster">
    <div className="fc-raster-frame">
      <RasterThumb kind={c.rasterKind}/>
      {c.illustrative && <span className="fc-illustrative" title="Illustrative rendering, not source pixels">illustrative</span>}
    </div>
    {c.headline && <div className="fc-raster-headline"><span style={{ color: `var(--tier-${c.tier})` }}>{c.headline}</span> · {c.subhead}</div>}
    {c.sub && <div className="fc-body-sub">{c.sub}</div>}
  </div>
);

const BodyRegister = ({ c, density }) => (
  <div className="fc-body fc-body-register">
    <ul className="fc-reg-list">
      {c.registers.map((r, i) => (
        <li key={i} className={`fc-reg-row ${r.label ? "" : "is-silent"}`}>
          <span className="fc-reg-tag">{r.reg}</span>
          {r.label ? (
            <>
              <span className="fc-reg-label" title={r.detail ? `${r.label} , ${r.detail}` : r.label}>{r.label}</span>
              <span className="fc-reg-source">{r.sourceId}</span>
            </>
          ) : (
            <span className="fc-reg-silent">{r.note}</span>
          )}
        </li>
      ))}
    </ul>
    {c.sub && <div className="fc-body-sub">{c.sub}</div>}
  </div>
);

/* ─── Card-grammar reference: one stub per variant ─── */
const GRAMMAR_STUBS = [
  { variant: "headline",    tier: "modeled",    source: "FEMA",          title: "Single big number, scenario-tagged",      headline: "Zone AE", subhead: "preliminary FIRM, panel ID", sub: "Use when the answer is one categorical state.",                  docId: "DS-HEADLINE",   vintage: "spec" },
  { variant: "tabular",     tier: "empirical",  source: "USGS",          title: "Small table of observations",             columns: ["id", "value", "dist."], rows: [["ROW-001", "1.2 m", "0.18 mi"], ["ROW-002", "0.9 m", "0.32 mi"], ["ROW-003", "0.7 m", "0.41 mi"]], sub: "Use when 3,8 records each carry the same fields.", docId: "DS-TABULAR",    vintage: "spec" },
  { variant: "scalars",     tier: "empirical",  source: "NWS",           title: "Trio of scalar readings",                 scalars: [{ value: "0.02 in", label: "precip · 24h" }, { value: "11 mph", label: "wind" }, { value: "63°F", label: "temp" }], sub: "Use for current-state dashboards.", docId: "DS-SCALARS", vintage: "spec" },
  { variant: "spark",       tier: "empirical",  source: "FloodNet",      title: "Sparkline of recent events",              headline: "n events", subhead: "window · peak", spark: [1,2,4,3,7,12,8,5,3,2,4,9,6], docId: "DS-SPARK", vintage: "spec" },
  { variant: "histogram",   tier: "proxy",      source: "NYC 311",       title: "Histogram of binned counts",              headline: "n calls",  subhead: "window · seasonal note", histogram: [3,2,1,0,1,4,7,12,18,11,5,3,4,2,1,0,2,3,8,9,4,2,1,0], docId: "DS-HIST", vintage: "spec" },
  { variant: "timeseries",  tier: "modeled",    source: "Granite TTM",   title: "Forecast curve with horizon",             headline: "+0.41 m peak", subhead: "+38h · 90% CI", timeseries: { hours: 96, peak: { x: 38, y: 41 }, peakLabel: "+0.41 m" }, spatialNote: "regional", sub: "Spatial-index callout when station ≠ point-of-query.", docId: "DS-TS", vintage: "spec" },
  { variant: "forecast",    tier: "modeled",    source: "NPCC4",         title: "Long-horizon scenario projections",       forecast: [{ year: 2030, low: 4, mid: 6, high: 9 }, { year: 2050, low: 13, mid: 22, high: 30 }, { year: 2100, low: 38, mid: 71, high: 114 }], sub: "Use for decadal+ uncertainty cones.", docId: "DS-FCST", vintage: "spec" },
  { variant: "raster",      tier: "modeled",    source: "NYC DEP",       title: "Raster snapshot, mapped layer",           rasterKind: "stormwater", headline: "ponding", subhead: "scenario · pixel summary", sub: "Use for any 2D model output.", docId: "DS-RASTER", vintage: "spec" },
  { variant: "raster-pred", tier: "modeled",    source: "Prithvi-NYC",   title: "Raster prediction, illustrative",         rasterKind: "prithvi", headline: "n% flooded", subhead: "model · scene id", illustrative: true, sub: "Same chrome as raster + illustrative tag.", docId: "DS-RASTERPRED", vintage: "spec" },
  { variant: "register",    tier: "empirical",  source: "NYC OpenData",  title: "Composite register list",                 registers: [
    { reg: "MTA",   tier: "empirical", label: "Station entrance",     sourceId: "MTA-X",  note: null },
    { reg: "NYCHA", tier: "empirical", label: "Development",          sourceId: "NYCHA-Y", note: null },
    { reg: "DOH",   tier: "empirical", label: null,                   sourceId: null,      note: "no acute-care hospital within 1.0 mi" },
  ], sub: "Use when many specialists join into one Stone.", docId: "DS-REGISTER", vintage: "spec" },
  { variant: "comparison",  tier: "synthetic",  source: "EMP × SYN",     title: "Documented vs. interpreted",              left: { tier: "empirical", label: "documented", value: "31.4%", aux: "n polygons" }, right: { tier: "synthetic", label: "interpreted", value: "29.8%", aux: "n polygons" }, delta: "Δ = , 1.6 pp · agreement strong", sub: "Use to surface model , ground-truth deltas.", docId: "DS-CMP", vintage: "spec" },
  { variant: "meta",        tier: "modeled",    source: "Mellea",        title: "Capstone reconciliation",                 metaRows: [{ k: "claims", v: "12 / 12 grounded" }, { k: "tier mix", v: "EMP 5 · MOD 4 · PRX 2 · SYN 1" }, { k: "tier-1 freshness", v: "median 38 d" }, { k: "warnings", v: "0" }], sub: "Use to expose the synthesis layer's audit.", docId: "DS-META", vintage: "spec" },
];

const CardGrammarReference = ({ density }) => (
  <section className="f-region f-region-grammar" aria-label="Card grammar reference">
    <header className="f-region-head">
      <div className="f-region-head-left">
        <span className="f-region-num">SPEC</span>
        <h3 className="f-region-name">Card grammar</h3>
        <span className="f-region-role">every body variant in the system</span>
        <span className="f-region-tag">stubs, not findings</span>
      </div>
      <span className="f-tally"><span className="f-tally-strong">{GRAMMAR_STUBS.length}</span> variants</span>
    </header>
    <div className="f-rail">
      {GRAMMAR_STUBS.map((c) => (
        <article key={c.variant} className={`fc fc-${c.variant} fc-tier-${c.tier} ${density === "compact" ? "is-compact" : ""}`}>
          <header className="fc-head">
            <div className="fc-head-source">
              <window.TierGlyph tier={c.tier} size={11}/>
              <span className="fc-head-source-label">{c.source}</span>
            </div>
            <span className="fc-head-vintage">{c.variant}</span>
          </header>
          <h4 className="fc-title">{c.title}</h4>
          {renderBody(c, density)}
          <footer className="fc-foot">
            <span className="fc-foot-docid fc-foot-docid-mute">{c.docId}</span>
            <FiTierBadge tier={c.tier}/>
          </footer>
        </article>
      ))}
    </div>
  </section>
);

Object.assign(window, { CardGrammarReference });

const BodyComparison = ({ c }) => (
  <div className="fc-body fc-body-comparison">
    <div className="fc-cmp-grid">
      <div className="fc-cmp-cell">
        <div className="fc-cmp-cell-tier">
          <window.TierGlyph tier={c.left.tier} size={10}/>
          <span className="fc-cmp-cell-label">{c.left.label}</span>
        </div>
        <div className="fc-cmp-cell-value" style={{ color: `var(--tier-${c.left.tier})` }}>{c.left.value}</div>
        <div className="fc-cmp-cell-aux">{c.left.aux}</div>
      </div>
      <div className="fc-cmp-divider" aria-hidden="true">vs</div>
      <div className="fc-cmp-cell">
        <div className="fc-cmp-cell-tier">
          <window.TierGlyph tier={c.right.tier} size={10}/>
          <span className="fc-cmp-cell-label">{c.right.label}</span>
        </div>
        <div className="fc-cmp-cell-value" style={{ color: `var(--tier-${c.right.tier})` }}>{c.right.value}</div>
        <div className="fc-cmp-cell-aux">{c.right.aux}</div>
      </div>
    </div>
    <div className="fc-cmp-delta">{c.delta}</div>
    {c.sub && <div className="fc-body-sub">{c.sub}</div>}
  </div>
);

const BodyMeta = ({ c }) => (
  <div className="fc-body fc-body-meta">
    <dl className="fc-meta-list">
      {c.metaRows.map((r, i) => (
        <div key={i} className="fc-meta-row">
          <dt>{r.k}</dt>
          <dd>{r.v}</dd>
        </div>
      ))}
    </dl>
    {c.sub && <div className="fc-body-sub">{c.sub}</div>}
  </div>
);

const renderBody = (c, density) => {
  switch (c.variant) {
    case "headline":    return <BodyHeadline c={c}/>;
    case "tabular":     return <BodyTabular c={c}/>;
    case "spark":       return <BodySpark c={c}/>;
    case "histogram":   return <BodySpark c={c}/>;
    case "forecast":    return <BodyForecast c={c}/>;
    case "timeseries":  return <BodyTimeseries c={c}/>;
    case "scalars":     return <BodyScalars c={c}/>;
    case "raster":      return <BodyRaster c={c}/>;
    case "raster-pred": return <BodyRaster c={c}/>;
    case "register":    return <BodyRegister c={c} density={density}/>;
    case "comparison":  return <BodyComparison c={c}/>;
    case "meta":        return <BodyMeta c={c}/>;
    default: return null;
  }
};

/* ─── Card frame ─── */

const FindingCard = ({ c, density, onCite, onHover, onClick, isLinked }) => {
  return (
    <article
      className={`fc fc-${c.variant} fc-tier-${c.tier} ${density === "compact" ? "is-compact" : ""} ${isLinked ? "is-linked" : ""}`}
      aria-labelledby={`fc-${c.docId}-title`}
      onMouseEnter={() => onHover?.(c.mapKey)}
      onMouseLeave={() => onHover?.(null)}
      onClick={() => onClick?.(c)}
    >
      <header className="fc-head">
        <div className="fc-head-source">
          <window.TierGlyph tier={c.tier} size={11}/>
          <span className="fc-head-source-label" title={c.agency}>{c.source}</span>
        </div>
        <span className="fc-head-vintage">v. {c.vintage}</span>
      </header>
      <h4 id={`fc-${c.docId}-title`} className="fc-title">{c.title}</h4>
      {renderBody(c, density)}
      <footer className="fc-foot">
        {c.citeId ? (
          <button type="button" className="fc-foot-cite" onClick={(e) => { e.stopPropagation(); onCite?.(c.citeId); }} title={`Open ${c.docId} in citation drawer`}>
            <span className="fc-foot-docid">{c.docId}</span>
            <span className="fc-foot-arrow" aria-hidden="true">→</span>
          </button>
        ) : (
          <span className="fc-foot-docid fc-foot-docid-mute">{c.docId}</span>
        )}
        <FiTierBadge tier={c.tier}/>
      </footer>
    </article>
  );
};

/* ─── Stone region ─── */

const flatten = (members) => members.flatMap((m) => (m.children ? [m, ...flatten(m.children)] : [m]));

const StoneTally44 = ({ cardCount, members }) => {
  const flat = flatten(members);
  const fired = flat.filter((m) => m.status === "fired" || m.status === "warned").length;
  const silent = flat.filter((m) => m.status === "silent_by_design").length;
  const warn = flat.filter((m) => m.status === "warned").length;
  const error = flat.filter((m) => m.status === "errored").length;
  const notInvoked = flat.filter((m) => m.status === "not_invoked").length;
  const ms = members.reduce((acc, m) => Math.max(acc, m.ms || 0), 0);
  const fmtMs = (x) => (x === 0 ? "—" : x < 1000 ? x + "ms" : (x / 1000).toFixed(1) + "s");
  return (
    <span className="f-tally">
      <span className="f-tally-cards">{cardCount} card{cardCount === 1 ? "" : "s"}</span>
      <span className="f-tally-sep">·</span>
      <span className="f-tally-fired"><span className="f-tally-strong">{fired}</span> fired</span>
      {silent > 0 && <><span className="f-tally-sep">·</span><span className="f-tally-silent"><span className="f-tally-strong">{silent}</span> silent</span></>}
      {warn > 0 && <><span className="f-tally-sep">·</span><span className="f-tally-warn"><span className="f-tally-strong">{warn}</span> warn</span></>}
      {error > 0 && <><span className="f-tally-sep">·</span><span className="f-tally-err"><span className="f-tally-strong">{error}</span> errored</span></>}
      {notInvoked > 0 && <><span className="f-tally-sep">·</span><span className="f-tally-notinvoked"><span className="f-tally-strong">{notInvoked}</span> not invoked</span></>}
      <span className="f-tally-sep">·</span>
      <span className="f-tally-ms"><span className="f-tally-strong">{fmtMs(ms)}</span></span>
    </span>
  );
};

const StoneRegion = ({ stone, cardIds, density, provenanceMode, onCite, onHover, linkedKey }) => {
  const meta = STONE_META[stone.key];
  const cards = cardIds.map((id) => CARDS[id]).filter(Boolean);
  const traceCount = flatten(stone.members).length;
  const flat = flatten(stone.members);
  const hasError = flat.some((m) => m.status === "errored");
  const hasWarn = flat.some((m) => m.status === "warned");
  const defaultOpen =
    provenanceMode === "all-expanded" ? true :
    provenanceMode === "all-collapsed" ? false :
    /* smart */ hasError || hasWarn;
  const [traceOpen, setTraceOpen] = useFi(defaultOpen);
  /* Re-sync if user toggles tweak */
  useFiMemo(() => setTraceOpen(defaultOpen), [provenanceMode]);

  const isCapstone = stone.key === "capstone";

  return (
    <section className={`f-region f-region-${stone.key}`} aria-labelledby={`f-h-${stone.key}`} data-stone={stone.key}>
      <header className="f-region-head">
        <div className="f-region-head-left">
          <span className="f-region-num">{(STONE_ORDER.indexOf(stone.key) + 1).toString().padStart(2, "0")}</span>
          <h3 id={`f-h-${stone.key}`} className="f-region-name">{meta.name}</h3>
          <span className="f-region-role">· {meta.role}</span>
          <span className="f-region-tag">{meta.tag}</span>
        </div>
        <StoneTally44 cardCount={cards.length} members={stone.members}/>
      </header>

      {/* Findings · primary surface */}
      {cards.length === 0 ? (
        <div className="f-silent">
          <span className="f-silent-tag">silent</span>
          <p className="f-silent-prose">
            {stone.key === "lodestone"
              ? "No projection cards landed for this query. The address is inland (Pelham Pkwy, Bronx); NPCC4 SLR and TTM Battery surge are coastal projections and do not localize here. Atomic functions still ran (see provenance) and returned silence rather than confabulation."
              : "No cards for this Stone on this query."}
          </p>
        </div>
      ) : (
        <div className={`f-rail ${isCapstone ? "f-rail-capstone" : ""}`}>
          {cards.map((c) => (
            <FindingCard
              key={c.docId}
              c={c}
              density={density}
              onCite={onCite}
              onHover={onHover}
              onClick={(card) => onHover?.(card.mapKey, true)}
              isLinked={linkedKey && c.mapKey === linkedKey}
            />
          ))}
        </div>
      )}

      {/* Provenance */}
      <div className="f-prov">
        <button
          type="button"
          className="f-prov-toggle"
          aria-expanded={traceOpen}
          onClick={() => setTraceOpen((o) => !o)}
        >
          <span className="f-prov-caret" aria-hidden="true">{traceOpen ? "▾" : "▸"}</span>
          <span className="f-prov-label">{traceOpen ? "Hide" : "Show"} provenance</span>
          <span className="f-prov-meta">· {traceCount} function{traceCount === 1 ? "" : "s"}{hasError ? " · errored" : hasWarn ? " · warned" : ""}</span>
        </button>
        {traceOpen && (
          <div className="f-prov-body">
            {stone.members.map((m) => <window.TraceRow key={m.id} m={m}/>)}
          </div>
        )}
      </div>
    </section>
  );
};

/* ─── Run-health strip ─── */

const RunHealth44 = ({ totalCards }) => {
  const all = window.STONES.flatMap((s) => flatten(s.members));
  const fired = all.filter((m) => m.status === "fired" || m.status === "warned").length;
  const total = all.length;
  const silent = all.filter((m) => m.status === "silent_by_design").length;
  const warn = all.filter((m) => m.status === "warned").length;
  const error = all.filter((m) => m.status === "errored").length;
  return (
    <div className="f-runhealth">
      <span className="f-rh-item"><strong>5</strong> Stones</span>
      <span className="f-rh-sep">·</span>
      <span className="f-rh-item"><strong>{fired}/{total}</strong> functions fired</span>
      <span className="f-rh-sep">·</span>
      <span className="f-rh-item"><strong>{totalCards}</strong> evidence cards</span>
      <span className="f-rh-sep">·</span>
      <span className="f-rh-item"><strong>24.0s</strong> wall-clock</span>
      {silent > 0 && <><span className="f-rh-sep">·</span><span className="f-rh-item f-rh-silent">{silent} silent</span></>}
      {warn > 0 && <><span className="f-rh-sep">·</span><span className="f-rh-item f-rh-warn">{warn} warned</span></>}
      {error > 0 && <><span className="f-rh-sep">·</span><span className="f-rh-item f-rh-err">{error} errored</span></>}
    </div>
  );
};

/* ─── Findings region ─── */

const FindingsRegion = ({ density, provenanceMode, queryKey, showComparison, showGrammar, onCite, onHover, linkedKey }) => {
  const map = CARDS_BY_QUERY[queryKey] || CARDS_BY_QUERY.redhook;
  /* Inject the comparison card into Keystone after the register card if showComparison is on */
  const adjusted = useFiMemo(() => {
    if (!showComparison) return map;
    if (queryKey !== "redhook") return map;
    /* Add a synthetic ID reference to the in-memory comparison card */
    return { ...map, keystone: [...(map.keystone || []), "__comparison__"] };
  }, [map, showComparison, queryKey]);

  const totalCards = STONE_ORDER.reduce((n, k) => n + (adjusted[k] || []).length, 0);

  return (
    <section className="findings" aria-label="Findings, grouped by Stone">
      <header className="findings-head">
        <h2 className="findings-h2">Findings · grouped by Stone</h2>
        <span className="findings-tagline">cards = what each Stone found · provenance collapses below</span>
      </header>
      <RunHealth44 totalCards={totalCards}/>
      {STONE_ORDER.map((key) => {
        const stone = window.STONES.find((s) => s.key === key);
        const ids = adjusted[key] || [];
        return (
          <StoneRegion
            key={key}
            stone={stone}
            cardIds={ids}
            density={density}
            provenanceMode={provenanceMode}
            onCite={onCite}
            onHover={onHover}
            linkedKey={linkedKey}
          />
        );
      })}
      {showGrammar && <CardGrammarReference density={density}/>}
    </section>
  );
};

/* Fold the comparison card into CARDS lookup at module load */
CARDS["__comparison__"] = COMPARISON_CARD;

Object.assign(window, { FindingsRegion, CARDS, CARDS_BY_QUERY });
