/* Briefing prose with epistemic-tier glyph margin.
   Each <Claim tier=... cite=...> renders the glyph in the left margin
   and a hoverable superscript citation that scrolls the citation drawer.
*/

const { useState, useRef, useEffect, useMemo } = React;

/* ── Citation registry for the sample briefing ───────────────────── */
const CITATIONS = {
  c1: {
    n: 1,
    tier: "empirical",
    source: "USGS",
    title: "Hurricane Sandy storm tide elevations, NY-NJ Harbor",
    docId: "USGS-OFR-2013-1234",
    url: "https://pubs.usgs.gov/of/2013/1234/",
    vintage: "2013-05",
    retrieved: "2026-04-28",
  },
  c2: {
    n: 2,
    tier: "empirical",
    source: "NYC OEM",
    title: "Hurricane Sandy Inundation Zone (2012)",
    docId: "NYCOEM-SIZ-2013",
    url: "https://data.cityofnewyork.us/dataset/sandy-inundation-zone",
    vintage: "2013-01",
    retrieved: "2026-04-28",
  },
  c3: {
    n: 3,
    tier: "empirical",
    source: "FloodNet NYC",
    title: "Sensor BK-RH-002 ,  Coffey Park, monthly exceedance",
    docId: "FN-BK-RH-002",
    url: "https://floodnet.nyc/sensor/BK-RH-002",
    vintage: "2026-04",
    retrieved: "2026-05-02",
  },
  c4: {
    n: 4,
    tier: "modeled",
    source: "FEMA",
    title: "Preliminary Flood Insurance Rate Map, panel 36047C0207G",
    docId: "FEMA-FIRM-36047C0207G",
    url: "https://msc.fema.gov/portal/search",
    vintage: "2024-09",
    retrieved: "2026-04-28",
  },
  c5: {
    n: 5,
    tier: "modeled",
    source: "NYC DEP",
    title: "Stormwater Flood Map ,  Moderate Stormwater Scenario",
    docId: "NYCDEP-SWFM-2024",
    url: "https://nyc.gov/stormwater-map",
    vintage: "2024-06",
    retrieved: "2026-04-28",
  },
  c6: {
    n: 6,
    tier: "modeled",
    source: "NPCC4",
    title: "Sea-level rise projections, 2050 90th percentile",
    docId: "NPCC4-Ch3-Tbl3.2",
    url: "https://nyas.org/npcc4",
    vintage: "2024-03",
    retrieved: "2026-04-28",
  },
  c7: {
    n: 7,
    tier: "proxy",
    source: "NYC 311",
    title: "Flooding service requests, BK CB6 2019–2025",
    docId: "NYC311-FLD-CB6",
    url: "https://data.cityofnewyork.us/311",
    vintage: "2025-12",
    retrieved: "2026-05-01",
  },
  c8: {
    n: 8,
    tier: "proxy",
    source: "FEMA NFIP",
    title: "National Flood Insurance Program claims, tract 36047008500",
    docId: "NFIP-T36047008500",
    url: "https://www.fema.gov/openfema",
    vintage: "2024-12",
    retrieved: "2026-04-28",
  },
  c9: {
    n: 9,
    tier: "synthetic",
    source: "TerraMind v1.2",
    title: "Synthetic SAR backscatter for 2025-09-14 (Sentinel-1 cloud-occluded)",
    docId: "RIPRAP-SYN-20250914",
    url: "#methodology-synthetic",
    vintage: "2025-09",
    retrieved: "2026-05-02",
  },
  c10: {
    n: 10,
    tier: "modeled",
    source: "NYC DCP",
    title: "Waterfront Revitalization Program ,  Coastal Risk Area",
    docId: "NYCDCP-WRP-2022",
    url: "https://nyc.gov/dcp/wrp",
    vintage: "2022-11",
    retrieved: "2026-04-28",
  },
};

const Cite = ({ id, onActivate }) => {
  const c = CITATIONS[id];
  if (!c) return null;
  return (
    <a
      href={`#cite-${id}`}
      className="inline-cite"
      data-cite={id}
      onClick={(e) => {
        e.preventDefault();
        onActivate?.(id);
      }}
      aria-label={`Citation ${c.n}: ${c.source}, ${c.title}`}
    >
      <sup>[{c.n}]</sup>
    </a>
  );
};

const Claim = ({ tier, children }) => (
  <span className={`claim claim-${tier}`} data-tier={tier}>
    <span className="claim-glyph" aria-hidden="false">
      <TierGlyph tier={tier} size={11} color={`var(--tier-${tier})`} />
    </span>
    <span className="claim-body">{children}</span>
  </span>
);

const SectionHead = ({ n, label, tier, children }) => (
  <h3 className="briefing-section-head">
    <span className="briefing-section-num">{n}</span>
    <span className="briefing-section-label">{label}</span>
    {tier && (
      <span className="briefing-section-tier">
        <TierBadge tier={tier} compact />
      </span>
    )}
    {children && <span className="briefing-section-title">{children}</span>}
  </h3>
);

/* ── Sample briefing: 80 Pioneer St, Red Hook, Brooklyn ─────────── */
const BRIEFING_BLOCKS = [
  { kind: "status", html: `
    <p class="briefing-deck">
      <strong>80 Pioneer Street, Red Hook, Brooklyn 11231.</strong>
      Block 597, Lot 30. Industrial Business Zone (IBZ-RH).
      Queried 2026-05-05 14:22 ET. <span class="briefing-meta">Briefing v0.4.4 · 5 Stones engaged · Keystone silent (no register joins matched)</span>
    </p>
  ` },

  { kind: "head", n: "01", label: "Status", title: "Coastal-edge, post-Sandy, multi-hazard" },
  { kind: "prose", parts: [
    { tier: "empirical", text: "The address sits 380 ft inland of the Erie Basin bulkhead, at a ground elevation of 6.2 ft NAVD88", cite: "c1" },
    { text: " ,  within the " },
    { tier: "empirical", text: "2012 Sandy Inundation Zone, which recorded a peak storm tide of 11.4 ft NAVD88 at the Battery", cite: "c2" },
    { text: " 2.4 mi to the northwest. " },
    { tier: "modeled", text: "FEMA's preliminary FIRM places the parcel in Zone AE (BFE 11 ft NAVD88)", cite: "c4" },
    { text: ", a 4.8 ft freeboard above current grade. The site is upgradient of two FloodNet sensors and three blocks from a chronic 311 cluster." },
  ]},

  { kind: "head", n: "02", label: "Empirical evidence", tier: "empirical" },
  { kind: "prose", parts: [
    { tier: "empirical", text: "FloodNet sensor BK-RH-002 (Coffey Park, 1,200 ft south) recorded 7 above-curb events between 2024-06 and 2026-04", cite: "c3" },
    { text: ", with a peak depth of 14.3 cm during the 2025-09-29 nor'easter. " },
    { tier: "empirical", text: "USGS post-Sandy high-water marks within 500 ft cluster between 6.8 and 8.1 ft NAVD88", cite: "c1" },
    { text: ", consistent with 0.6–1.9 ft of standing water at the queried address during the storm." },
  ]},

  { kind: "head", n: "03", label: "Modeled scenarios", tier: "modeled" },
  { kind: "prose", parts: [
    { tier: "modeled", text: "DEP's Moderate Stormwater Scenario (2.13 in/hr design storm) shows ponding ≥4 in across the western half of the lot", cite: "c5" },
    { text: ", routed by the 1.2% slope toward Imlay St. " },
    { tier: "modeled", text: "Under NPCC4's 2050 90th-percentile sea-level rise (30 in)", cite: "c6" },
    { text: ", the parcel falls within the projected daily-tidal floodplain by mid-century. " },
    { tier: "synthetic", text: "Synthetic SAR backscatter for 2025-09-14 (Sentinel-1 cloud-occluded) was generated by TerraMind v1.2 and is presented as a prior, not an observation", cite: "c9" },
    { text: "; treat with appropriate caution." },
  ]},

  { kind: "head", n: "04", label: "Policy context" },
  { kind: "prose", parts: [
    { tier: "proxy", text: "311 flood complaints within the surrounding census tract total 89 calls over 2019–2025, with seasonal clustering in Aug–Oct", cite: "c7" },
    { text: ". " },
    { tier: "proxy", text: "NFIP claims aggregated to tract 36047008500 total $4.1M across 47 paid losses since 2000", cite: "c8" },
    { text: ". " },
    { tier: "modeled", text: "The site lies within the NYC Waterfront Revitalization Program Coastal Risk Area; CEQR §817 review applies to any discretionary action", cite: "c10" },
    { text: "." },
  ]},
];

/* ── Streaming renderer ───────────────────────────────────────────
   Uses CSS reveal (token-by-token via animation-delay) instead of
   recomputing innerText, to avoid layout shift.
*/
const StreamingBriefing = ({ onCite, replayKey }) => {
  const [visibleCount, setVisibleCount] = useState(0);
  const totalBlocks = BRIEFING_BLOCKS.length;

  useEffect(() => {
    setVisibleCount(0);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setVisibleCount(totalBlocks);
      return;
    }
    let i = 0;
    const tick = () => {
      i++;
      setVisibleCount(i);
      if (i < totalBlocks) {
        setTimeout(tick, i < 2 ? 280 : 420);
      }
    };
    const t = setTimeout(tick, 240);
    return () => clearTimeout(t);
  }, [replayKey]);

  return (
    <div
      className="briefing-prose"
      role="log"
      aria-live="polite"
      aria-atomic="false"
      aria-label="Streaming flood-exposure briefing"
    >
      {BRIEFING_BLOCKS.slice(0, visibleCount).map((b, i) => {
        if (b.kind === "status") {
          return <div key={i} className="briefing-status" dangerouslySetInnerHTML={{ __html: b.html }} />;
        }
        if (b.kind === "head") {
          return <SectionHead key={i} n={b.n} label={b.label} tier={b.tier}>{b.title}</SectionHead>;
        }
        if (b.kind === "prose") {
          return (
            <p key={i} className="briefing-para">
              {b.parts.map((p, j) => {
                if (p.tier) {
                  return (
                    <React.Fragment key={j}>
                      <Claim tier={p.tier}>{p.text}</Claim>
                      {p.cite && <Cite id={p.cite} onActivate={onCite} />}
                    </React.Fragment>
                  );
                }
                return <span key={j}>{p.text}</span>;
              })}
            </p>
          );
        }
        return null;
      })}
      {visibleCount < totalBlocks && (
        <span className="streaming-caret" aria-hidden="true">▍</span>
      )}
    </div>
  );
};

const CitationDrawer = ({ activeId, onClose }) => {
  const items = Object.entries(CITATIONS);
  return (
    <aside className="citation-drawer" aria-label="Citations">
      <div className="citation-drawer-head">
        <span className="section-label">Citations · {items.length}</span>
        <span className="citation-drawer-meta">live · primary sources</span>
      </div>
      <ol className="citation-list">
        {items.map(([id, c]) => (
          <li
            key={id}
            id={`cite-${id}`}
            className={`citation-item ${activeId === id ? "is-active" : ""}`}
          >
            <span className="citation-num">[{c.n}]</span>
            <div className="citation-body">
              <div className="citation-line-1">
                <TierGlyph tier={c.tier} size={10} color={`var(--tier-${c.tier})`} />
                <span className="citation-source">{c.source}</span>
                <span className="citation-vintage">v. {c.vintage}</span>
              </div>
              <div className="citation-title">{c.title}</div>
              <div className="citation-meta">
                <span className="citation-docid">{c.docId}</span>
                <span className="citation-retrieved">retr. {c.retrieved}</span>
              </div>
            </div>
          </li>
        ))}
      </ol>
      <div className="citation-drawer-foot">
        <span className="section-label">Trust signals</span>
        <p className="citation-foot-copy">
          All foundation models Apache-2.0. All data from public-record federal,
          state, and city sources. No commercial APIs contacted at runtime.
        </p>
      </div>
    </aside>
  );
};

Object.assign(window, { StreamingBriefing, CitationDrawer, CITATIONS, Cite, Claim });
