/* Trace UI: <details>-based tree of the Burr FSM run.
   Three columns: action name · elapsed ms · epistemic-tier badge.
   Parallel branches shown as sibling rows under a "fan-out" parent;
   convergence step shown as a "merge" node. Reference: Postgres
   EXPLAIN ANALYZE viewers, Apache Airflow DAG.
*/

const TRACE = {
  id: "root",
  name: "briefing.run",
  status: "ok",
  ms: 14820,
  tier: null,
  children: [
    { id: "n1", name: "geocode.address", status: "ok", ms: 142, tier: null,
      output: { lat: 40.6776, lon: -74.0096, bbl: "3005970030" } },
    { id: "n2", name: "fan_out.stones", status: "fan", ms: 0, tier: null,
      note: "5 Stones engaged in parallel",
      children: [
        { id: "s1", name: "sandy_inundation.lookup", status: "ok", ms: 380, tier: "empirical",
          claims: 2, output: "polygon: contains; nearest HWM 0.4mi" },
        { id: "s2", name: "floodnet.history", status: "ok", ms: 1240, tier: "empirical",
          claims: 1, output: "BK-RH-002: 7 events, peak 14.3cm" },
        { id: "s3", name: "usgs.high_water_marks", status: "ok", ms: 612, tier: "empirical",
          claims: 1, output: "9 marks within 500ft" },
        { id: "s4", name: "fema.firm.preliminary", status: "ok", ms: 488, tier: "modeled",
          claims: 1, output: "Zone AE, BFE 11ft NAVD88" },
        { id: "s5", name: "dep.stormwater.scenario", status: "ok", ms: 2104, tier: "modeled",
          claims: 1, output: "moderate: ponding ≥4in W half" },
        { id: "s6", name: "npcc4.slr.projection", status: "ok", ms: 320, tier: "modeled",
          claims: 1, output: "2050 90th: +30in" },
        { id: "s7", name: "nyc311.flood_complaints", status: "ok", ms: 980, tier: "proxy",
          claims: 1, output: "89 calls / tract / 2019–25" },
        { id: "s8", name: "nfip.claims_aggregate", status: "ok", ms: 540, tier: "proxy",
          claims: 1, output: "$4.1M / 47 paid losses" },
        { id: "s9", name: "terramind.synthetic_sar", status: "ok", ms: 6840, tier: "synthetic",
          claims: 1, output: "synthesis confidence 0.71" },
        { id: "s10", name: "tidal_gauge.range", status: "silent", ms: 18, tier: null,
          claims: 0, output: "out of range: nearest gauge >2mi" },
        { id: "s11", name: "wrp.coastal_risk_area", status: "ok", ms: 210, tier: "modeled",
          claims: 1, output: "within Coastal Risk Area" },
      ]
    },
    { id: "n3", name: "merge.evidence", status: "merge", ms: 92, tier: null,
      note: "10 cards · 1 silent · 0 errors" },
    { id: "n4", name: "compose.briefing", status: "ok", ms: 1380, tier: null,
      output: "4 sections · 11 claims · 10 citations" },
    { id: "n5", name: "stream.sse", status: "ok", ms: 4940, tier: null,
      output: "1812 tokens · 11 sentence chunks" },
  ]
};

const StatusGlyph = ({ status }) => {
  const map = {
    ok: { fill: "#0B5394", char: "" },
    silent: { fill: "transparent", stroke: "#6B6B6B", char: "" },
    error: { fill: "#B8620A", char: "!" },
    fan: { char: "⤳" },
    merge: { char: "⤺" },
  };
  const m = map[status];
  if (status === "fan" || status === "merge") {
    return <span className="trace-status-glyph" aria-label={status}>{m.char}</span>;
  }
  return (
    <svg width="9" height="9" viewBox="0 0 9 9" aria-label={status}>
      <rect x="0.75" y="0.75" width="7.5" height="7.5" fill={m.fill} stroke={m.stroke || m.fill} strokeWidth="1.5"/>
    </svg>
  );
};

const TraceRow = ({ node, depth = 0, defaultOpen = false }) => {
  const hasChildren = node.children && node.children.length > 0;
  const [open, setOpen] = useState(defaultOpen);
  const indent = depth * 16;

  return (
    <>
      <div className={`trace-row trace-row-${node.status}`} style={{ paddingLeft: indent + 12 }}>
        <button
          type="button"
          className="trace-row-toggle"
          onClick={() => hasChildren && setOpen(!open)}
          aria-expanded={hasChildren ? open : undefined}
          aria-label={`${node.name}, ${node.ms}ms, ${node.status}`}
          disabled={!hasChildren}
        >
          <span className="trace-tree-glyph" aria-hidden="true">
            {hasChildren ? (open ? "▾" : "▸") : "·"}
          </span>
          <span className="trace-status-col">
            <StatusGlyph status={node.status} />
          </span>
          <span className="trace-name-col">
            <span className="trace-name">{node.name}</span>
            {node.note && <span className="trace-note"> · {node.note}</span>}
          </span>
          <span className="trace-ms-col">{node.ms}ms</span>
          <span className="trace-tier-col">
            {node.tier && <TierBadge tier={node.tier} compact />}
            {node.status === "silent" && (
              <span className="trace-silent-tag">silent</span>
            )}
          </span>
        </button>
        {open && node.output && (
          <div className="trace-output" style={{ paddingLeft: indent + 44 }}>
            <span className="trace-output-prefix">→</span>
            <span className="trace-output-text">
              {typeof node.output === "string" ? node.output : JSON.stringify(node.output)}
            </span>
            {node.claims != null && (
              <span className="trace-output-claims">{node.claims} claim{node.claims === 1 ? "" : "s"} cited</span>
            )}
          </div>
        )}
      </div>
      {open && hasChildren && node.children.map((c) => (
        <TraceRow key={c.id} node={c} depth={depth + 1} defaultOpen={c.status === "fan"} />
      ))}
    </>
  );
};

const TraceUI = ({ collapsed, onToggleCollapsed }) => {
  return (
    <section className={`trace-ui ${collapsed ? "is-collapsed" : ""}`} aria-label="Run trace">
      <header className="trace-head">
        <div className="trace-head-left">
          <span className="section-label">Run trace</span>
          <span className="trace-head-meta">
            <span className="trace-head-stat">14.82s total</span>
            <span className="trace-head-sep">·</span>
            <span className="trace-head-stat">10 fired</span>
            <span className="trace-head-sep">·</span>
            <span className="trace-head-stat trace-head-silent">1 silent</span>
            <span className="trace-head-sep">·</span>
            <span className="trace-head-stat">0 errors</span>
          </span>
        </div>
        <button
          type="button"
          className="trace-collapse-btn"
          onClick={onToggleCollapsed}
          aria-expanded={!collapsed}
        >
          {collapsed ? "Expand ▾" : "Collapse ▴"}
        </button>
      </header>
      {!collapsed && (
        <div className="trace-body">
          <div className="trace-col-heads">
            <span className="trace-col-head trace-col-head-name">action</span>
            <span className="trace-col-head trace-col-head-ms">elapsed</span>
            <span className="trace-col-head trace-col-head-tier">tier</span>
          </div>
          <div className="trace-tree" role="tree">
            <TraceRow node={TRACE} defaultOpen={true} />
          </div>
        </div>
      )}
    </section>
  );
};

Object.assign(window, { TraceUI });
