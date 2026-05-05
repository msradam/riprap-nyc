/* Riprap v0.4.4 ,  Stone-banded trace (Treatment A).
   Pulled out of the deleted spec-v043.jsx; this is what the mockup uses.
*/

const { useState: useStV44, useEffect: useEfV44 } = React;

const STONES = [
  {
    key: "cornerstone", name: "Cornerstone", role: "the hazard reader",
    tag: "what NYC's ground remembers",
    members: [
      { id: "c1", name: "sandy_inundation.lookup",  status: "ok",   ms: 380, tier: "empirical" },
      { id: "c2", name: "usgs_hwm.spatial_join",     status: "ok",   ms: 460, tier: "empirical" },
      { id: "c3", name: "fema_firm.lookup",          status: "ok",   ms: 290, tier: "modeled" },
      { id: "c4", name: "dep_stormwater.lookup",     status: "ok",   ms: 540, tier: "modeled" },
      { id: "c5", name: "prithvi.historical_segment",status: "warn", ms: 1240, tier: "modeled",
        warning: "deprecation: Prithvi-100M v1 → v2 migration scheduled 2026-Q3" },
    ],
  },
  {
    key: "keystone", name: "Keystone", role: "the asset register",
    tag: "what's exposed",
    members: [
      { id: "k1", name: "mta.entrance_join",      status: "ok", ms: 220, tier: "empirical" },
      { id: "k2", name: "nycha.development_join", status: "ok", ms: 538, tier: "empirical" },
      { id: "k3", name: "doe.school_join",        status: "ok", ms: 180, tier: "empirical" },
      { id: "k4", name: "doh.facility_join",      status: "ok", ms: 210, tier: "empirical" },
      { id: "k5", name: "pluto.lot_lookup",       status: "ok", ms: 142, tier: "empirical" },
    ],
  },
  {
    key: "touchstone", name: "Touchstone", role: "the live observer",
    tag: "what's happening now",
    members: [
      { id: "t1", name: "floodnet.history",      status: "ok",     ms: 1240, tier: "empirical" },
      { id: "t2", name: "nyc311.flood_complaints", status: "ok",   ms: 880, tier: "proxy" },
      { id: "t3", name: "tidalgauge.recent",      status: "silent", ms: 0,  tier: "empirical",
        note: "out of range (gauge >2km from address)" },
    ],
  },
  {
    key: "lodestone", name: "Lodestone", role: "the projector",
    tag: "what's coming",
    members: [
      { id: "l1", name: "npcc4.slr_projection", status: "ok", ms: 320, tier: "modeled" },
      { id: "l2", name: "ttm.foundation_run", status: "ok", ms: 14000, tier: "modeled",
        children: [
          { id: "l2a", name: "ttm.zarr_load",        status: "ok",    ms: 2400, tier: "modeled" },
          { id: "l2b", name: "ttm.checkpoint",        status: "error", ms: 10750, tier: "modeled",
            error: "checkpoint architecture mismatch (ttm-r2 vs ttm-r1 weights)" },
          { id: "l2c", name: "ttm.cpu_inference",    status: "ok",    ms: 850,  tier: "modeled" },
        ],
      },
      { id: "l3", name: "terramind.synthetic_sar", status: "ok", ms: 8200, tier: "synthetic" },
      { id: "l4", name: "nfip.claims_aggregation", status: "ok", ms: 460, tier: "proxy" },
    ],
  },
  {
    key: "capstone", name: "Capstone", role: "the synthesizer",
    tag: "writes it all down with citations",
    members: [
      { id: "p1", name: "granite.compose_briefing",  status: "ok", ms: 3200, tier: "modeled" },
      { id: "p2", name: "mellea.grounding_check",    status: "ok", ms: 480,  tier: "modeled" },
      { id: "p3", name: "weasyprint.render_artifact",status: "ok", ms: 920,  tier: null },
    ],
  },
];

const fmtMs = (ms) => ms === 0 ? ", " : ms < 1000 ? ms + "ms" : (ms / 1000).toFixed(1) + "s";
const tierColor = (t) => t ? `var(--tier-${t})` : "var(--ink-tertiary)";

const StoneAggregate = ({ stone }) => {
  const flat = (members) => members.flatMap(m => m.children ? [m, ...flat(m.children)] : [m]);
  const all = flat(stone.members);
  const fired = all.filter(m => m.status === "ok").length;
  const silent = all.filter(m => m.status === "silent").length;
  const warn = all.filter(m => m.status === "warn").length;
  const error = all.filter(m => m.status === "error").length;
  const ms = stone.members.reduce((acc, m) => Math.max(acc, m.ms || 0), 0);
  return (
    <span className="stone-band-agg">
      <span className="stone-band-agg-num">{fired}</span> fired
      {silent > 0 && <> · <span className="stone-band-agg-num">{silent}</span> silent</>}
      {warn > 0 && <> · <span className="stone-band-agg-warn">{warn} warn</span></>}
      {error > 0 && <> · <span className="stone-band-agg-err">{error} error</span></>}
      {" · "}<span className="stone-band-agg-ms">{fmtMs(ms)}</span>
    </span>
  );
};

const TraceRow = ({ m, indent = 16 }) => {
  if (m.children) {
    return (
      <details className="trace-row trace-row-group" style={{ paddingLeft: indent }} open>
        <summary>
          <span className="trace-bullet">▸</span>
          <span className="trace-name">{m.name}</span>
          <span className="trace-status">{m.status}</span>
          <span className="trace-tier" style={{ color: tierColor(m.tier) }}>{m.tier || ""}</span>
          <span className="trace-ms">{fmtMs(m.ms)}</span>
        </summary>
        {m.children.map(c => <TraceRow key={c.id} m={c} indent={indent + 16}/>)}
      </details>
    );
  }
  if (m.status === "error") {
    return (
      <div className="trace-row trace-row-error" style={{ paddingLeft: indent }}>
        <span className="trace-bullet">●</span>
        <span className="trace-name">{m.name}</span>
        <span className="trace-status trace-status-err">error</span>
        <span className="trace-tier" style={{ color: tierColor(m.tier) }}>{m.tier || ""}</span>
        <span className="trace-ms">{fmtMs(m.ms)}</span>
        <span className="trace-error-summary">{m.error}</span>
      </div>
    );
  }
  return (
    <div className={`trace-row trace-row-${m.status}`} style={{ paddingLeft: indent }}>
      <span className="trace-bullet">{m.status === "silent" ? "□" : m.status === "warn" ? "!" : "·"}</span>
      <span className="trace-name">{m.name}</span>
      <span className="trace-status">{m.status}</span>
      <span className="trace-tier" style={{ color: tierColor(m.tier) }}>{m.tier || ""}</span>
      <span className="trace-ms">{fmtMs(m.ms)}</span>
      {m.warning && <span className="trace-warn-note">{m.warning}</span>}
      {m.note && <span className="trace-note">{m.note}</span>}
    </div>
  );
};

const StoneBand = ({ stone }) => {
  const [open, setOpen] = useStV44(true);
  return (
    <section className={`stone-band stone-band-${stone.key}`} aria-labelledby={`band-h-${stone.key}`}>
      <button className="stone-band-head" aria-expanded={open} onClick={() => setOpen(o => !o)}>
        <span className="stone-band-head-left">
          <span id={`band-h-${stone.key}`} className="stone-band-name">{stone.name}</span>
          <span className="stone-band-role">,  {stone.role}</span>
          <span className="stone-band-tag">{stone.tag}</span>
        </span>
        <StoneAggregate stone={stone}/>
      </button>
      {open && (
        <div className="stone-band-body">
          {stone.members.map(m => <TraceRow key={m.id} m={m}/>)}
        </div>
      )}
    </section>
  );
};

const StoneTrace = () => {
  return (
    <div className="trace-ui-v44">
      <header className="stone-trace-head">
        <span className="section-label">Run trace · 5 Stones</span>
        <span className="stone-trace-tally">17 fired · 1 silent · 1 warn · 1 error · 14.0s</span>
      </header>
      {STONES.map(s => <StoneBand key={s.key} stone={s}/>)}
    </div>
  );
};

Object.assign(window, { StoneTrace, STONES, TraceRow, fmtMs, tierColor });
