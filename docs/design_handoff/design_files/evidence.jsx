/* Evidence cards: stack below the map. One card per specialist that fired.
   Each card carries source label, formatted output, tier badge, doc_id,
   and prominent vintage. Mobile: horizontal swipe; desktop: 2-col grid.
*/

const EVIDENCE = [
  {
    id: "e1", citeId: "c1", tier: "empirical",
    source: "USGS",
    title: "Post-Sandy high-water marks within 500ft",
    fmt: "table",
    table: [
      ["HWM-NY-3081", "7.4 ft NAVD88", "0.18 mi"],
      ["HWM-NY-3082", "8.1 ft NAVD88", "0.22 mi"],
      ["HWM-NY-3105", "6.8 ft NAVD88", "0.31 mi"],
    ],
    docId: "USGS-OFR-2013-1234",
    vintage: "2013-05",
  },
  {
    id: "e2", citeId: "c3", tier: "empirical",
    source: "FloodNet NYC",
    title: "Sensor BK-RH-002 ,  monthly above-curb events",
    fmt: "spark",
    spark: [0,0,1,0,2,1,0,0,3,0,1,0,0,0,2,1,0,0,1,0,2,4,1,1],
    headline: "7 events", sub: "Jun 2024 → Apr 2026 · peak 14.3 cm",
    docId: "FN-BK-RH-002",
    vintage: "2026-04",
  },
  {
    id: "e3", citeId: "c4", tier: "modeled",
    source: "FEMA",
    title: "Preliminary FIRM, panel 36047C0207G",
    fmt: "scalar",
    scalar: { value: "Zone AE", unit: "BFE 11 ft NAVD88", aux: "freeboard +4.8 ft" },
    docId: "FEMA-FIRM-36047C0207G",
    vintage: "2024-09",
  },
  {
    id: "e4", citeId: "c5", tier: "modeled",
    source: "NYC DEP",
    title: "Stormwater Flood Map ,  moderate scenario",
    fmt: "thumb",
    thumb: "stormwater",
    sub: "2.13 in/hr · ponding ≥4 in W half of lot · routed toward Imlay St",
    docId: "NYCDEP-SWFM-2024",
    vintage: "2024-06",
  },
  {
    id: "e5", citeId: "c6", tier: "modeled",
    source: "NPCC4",
    title: "Sea-level rise projections for Lower NY Harbor",
    fmt: "forecast",
    forecast: [
      { year: 2030, low: 4, mid: 6, high: 9 },
      { year: 2050, low: 13, mid: 22, high: 30 },
      { year: 2080, low: 28, mid: 49, high: 75 },
      { year: 2100, low: 38, mid: 71, high: 114 },
    ],
    docId: "NPCC4-Ch3-Tbl3.2",
    vintage: "2024-03",
  },
  {
    id: "e6", citeId: "c9", tier: "synthetic",
    source: "TerraMind v1.2",
    title: "Synthetic SAR for 2025-09-14 (Sentinel-1 cloud-occluded)",
    fmt: "thumb",
    thumb: "synthetic",
    sub: "Generated, not observed. Confidence 0.71. Provided as prior for downstream models; do not cite as observation.",
    docId: "RIPRAP-SYN-20250914",
    vintage: "2025-09",
  },
  {
    id: "e7", citeId: "c7", tier: "proxy",
    source: "NYC 311",
    title: "Flood complaints, BK CB6 (2019–2025)",
    fmt: "histogram",
    months: [3,2,1,0,1,4,7,12,18,11,5,3,4,2,1,0,2,3,8,9,4,2,1,0],
    headline: "89 calls", sub: "seasonal cluster Aug–Oct",
    docId: "NYC311-FLD-CB6",
    vintage: "2025-12",
  },
  {
    id: "e8", citeId: "c8", tier: "proxy",
    source: "FEMA NFIP",
    title: "NFIP claims, tract 36047008500",
    fmt: "scalar",
    scalar: { value: "$4.1M", unit: "47 paid losses", aux: "since 2000-01-01" },
    docId: "NFIP-T36047008500",
    vintage: "2024-12",
  },
];

const Spark = ({ data, color }) => {
  const max = Math.max(...data, 1);
  const w = 180, h = 36, n = data.length;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} preserveAspectRatio="none" aria-hidden="true">
      {data.map((v, i) => (
        <rect
          key={i}
          x={(i / n) * w + 0.5}
          y={h - (v / max) * h}
          width={Math.max(2, w / n - 1.5)}
          height={(v / max) * h}
          fill={color}
        />
      ))}
    </svg>
  );
};

const Histogram = ({ data, color }) => (
  <Spark data={data} color={color} />
);

const ForecastChart = ({ data, color }) => {
  const w = 220, h = 80, pad = 4;
  const xs = data.map((d, i) => pad + (i / (data.length - 1)) * (w - pad * 2));
  const max = Math.max(...data.map(d => d.high));
  const y = (v) => h - pad - (v / max) * (h - pad * 2);
  const path = (key) => xs.map((x, i) => `${i ? "L" : "M"} ${x} ${y(data[i][key])}`).join(" ");
  const range = xs.map((x, i) => ({ x, lo: y(data[i].low), hi: y(data[i].high) }));
  const areaD = `M ${range.map(r => `${r.x} ${r.lo}`).join(" L ")} L ${[...range].reverse().map(r => `${r.x} ${r.hi}`).join(" L ")} Z`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} aria-hidden="true">
      <path d={areaD} fill={color} fillOpacity="0.18" />
      <path d={path("mid")} fill="none" stroke={color} strokeWidth="1.5"/>
      {data.map((d, i) => (
        <g key={i}>
          <circle cx={xs[i]} cy={y(d.mid)} r="2" fill={color}/>
          <text x={xs[i]} y={h - 1} fontSize="9" fontFamily="IBM Plex Mono" textAnchor="middle" fill="#6B6B6B">{d.year}</text>
        </g>
      ))}
    </svg>
  );
};

const ThumbStripe = ({ kind }) => (
  <svg viewBox="0 0 220 110" width="100%" height="110" aria-hidden="true" style={{ display: "block", background: "#F2F2EE" }}>
    <defs>
      <pattern id={`thumb-${kind}`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect width="6" height="6" fill={kind === "synthetic" ? "rgba(42,111,168,0.18)" : "rgba(42,111,168,0.30)"}/>
        <line x1="0" y1="0" x2="0" y2="6" stroke={kind === "synthetic" ? "#2A6FA8" : "#0B5394"} strokeWidth="0.8"/>
      </pattern>
    </defs>
    {kind === "stormwater" ? (
      <>
        <rect x="0" y="0" width="220" height="110" fill="#FAFAF7"/>
        <path d="M0 60 L60 55 L120 70 L180 80 L220 78 L220 110 L0 110 Z" fill="rgba(42,111,168,0.30)" stroke="#2A6FA8" strokeWidth="1"/>
        <path d="M0 75 L60 72 L120 85 L180 92 L220 90 L220 110 L0 110 Z" fill="rgba(42,111,168,0.20)" stroke="#2A6FA8" strokeWidth="0.8"/>
        <circle cx="100" cy="68" r="4" fill="#D17C00" stroke="#FAFAF7" strokeWidth="1.5"/>
      </>
    ) : (
      <>
        <rect x="0" y="0" width="220" height="110" fill={`url(#thumb-${kind})`}/>
        <text x="8" y="100" fontFamily="IBM Plex Mono" fontSize="9" fill="#2A6FA8">SYN · 2025-09-14</text>
      </>
    )}
  </svg>
);

const EvidenceCard = ({ ev, onCite }) => {
  const tierColor = `var(--tier-${ev.tier})`;
  return (
    <article className={`evidence-card evidence-card-${ev.tier}`} aria-labelledby={`ec-${ev.id}-title`}>
      <header className="evidence-card-head">
        <div className="evidence-card-source">
          <TierGlyph tier={ev.tier} size={11} color={tierColor} />
          <span className="evidence-card-source-label">{ev.source}</span>
        </div>
        <span className="evidence-card-vintage" title="Data vintage">v. {ev.vintage}</span>
      </header>
      <h4 id={`ec-${ev.id}-title`} className="evidence-card-title">{ev.title}</h4>

      <div className="evidence-card-body">
        {ev.fmt === "scalar" && (
          <div className="evidence-scalar">
            <div className="evidence-scalar-value" style={{ color: tierColor }}>{ev.scalar.value}</div>
            <div className="evidence-scalar-unit">{ev.scalar.unit}</div>
            {ev.scalar.aux && <div className="evidence-scalar-aux">{ev.scalar.aux}</div>}
          </div>
        )}
        {ev.fmt === "table" && (
          <table className="evidence-table">
            <thead><tr><th>id</th><th>elev.</th><th>dist.</th></tr></thead>
            <tbody>
              {ev.table.map((row, i) => (
                <tr key={i}>{row.map((c, j) => <td key={j}>{c}</td>)}</tr>
              ))}
            </tbody>
          </table>
        )}
        {ev.fmt === "spark" && (
          <div className="evidence-spark">
            <div className="evidence-spark-headline" style={{ color: tierColor }}>{ev.headline}</div>
            <Spark data={ev.spark} color={tierColor}/>
            <div className="evidence-scalar-aux">{ev.sub}</div>
          </div>
        )}
        {ev.fmt === "histogram" && (
          <div className="evidence-spark">
            <div className="evidence-spark-headline" style={{ color: tierColor }}>{ev.headline}</div>
            <Histogram data={ev.months} color={tierColor}/>
            <div className="evidence-scalar-aux">{ev.sub}</div>
          </div>
        )}
        {ev.fmt === "forecast" && (
          <div className="evidence-spark">
            <ForecastChart data={ev.forecast} color={tierColor}/>
            <div className="evidence-scalar-aux">inches MSL · 17th–83rd %ile range, median line</div>
          </div>
        )}
        {ev.fmt === "thumb" && (
          <div className="evidence-thumb">
            <ThumbStripe kind={ev.thumb}/>
            <div className="evidence-scalar-aux">{ev.sub}</div>
          </div>
        )}
      </div>

      <footer className="evidence-card-foot">
        <button
          type="button"
          className="evidence-card-cite"
          onClick={() => onCite?.(ev.citeId)}
          title={`Open citation ${ev.citeId} in drawer`}
        >
          <span className="evidence-card-docid">{ev.docId}</span>
          <span className="evidence-card-cite-arrow" aria-hidden="true">→</span>
        </button>
        <TierBadge tier={ev.tier} compact />
      </footer>
    </article>
  );
};

const EvidenceGrid = ({ onCite }) => (
  <section className="evidence-grid" aria-label="Evidence cards">
    <div className="evidence-grid-head">
      <span className="section-label">Evidence · 8 cards</span>
      <span className="evidence-grid-meta">
        <span className="evidence-grid-tally"><TierGlyph tier="empirical" size={9}/> 3</span>
        <span className="evidence-grid-tally"><TierGlyph tier="modeled" size={9}/> 3</span>
        <span className="evidence-grid-tally"><TierGlyph tier="proxy" size={9}/> 2</span>
        <span className="evidence-grid-tally"><TierGlyph tier="synthetic" size={9}/> 1</span>
      </span>
    </div>
    <div className="evidence-grid-rail">
      {EVIDENCE.map((ev) => (
        <EvidenceCard key={ev.id} ev={ev} onCite={onCite}/>
      ))}
    </div>
  </section>
);

Object.assign(window, { EvidenceGrid, EvidenceCard });
