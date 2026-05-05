/* Riprap v0.4.5 · Stone-banded trace.
   Status enum (v0.4.5): fired / silent_by_design / warned / errored / not_invoked.
   See V0.4.5_SPEC.md §1 for the rationale.
*/

const { useState: useStV44, useEffect: useEfV44 } = React;

const STONES = [
  {
    key: "cornerstone", name: "Cornerstone", role: "the hazard reader",
    tag: "what NYC's ground remembers",
    members: [
      { id: "c1", name: "sandy_inundation.lookup",   status: "fired",  ms: 380, tier: "empirical" },
      { id: "c2", name: "usgs_hwm.spatial_join",     status: "fired",  ms: 460, tier: "empirical" },
      { id: "c3", name: "fema_firm.lookup",          status: "fired",  ms: 290, tier: "modeled" },
      { id: "c4", name: "dep_stormwater.lookup",     status: "fired",  ms: 540, tier: "modeled" },
      { id: "c5", name: "prithvi.historical_segment",status: "warned", ms: 1240, tier: "modeled",
        warning: "deprecation: Prithvi-100M v1 → v2 migration scheduled 2026-Q3" },
    ],
  },
  {
    key: "keystone", name: "Keystone", role: "the asset register",
    tag: "what's exposed",
    members: [
      { id: "k1", name: "mta_entrance_exposure",    status: "silent_by_design", ms: 30,  tier: "empirical",
        note: "no entrances within radius" },
      { id: "k2", name: "nycha.development_join",   status: "silent_by_design", ms: 28,  tier: "empirical",
        note: "no NYCHA developments within 1.0 mi" },
      { id: "k3", name: "doe.school_join",          status: "silent_by_design", ms: 24,  tier: "empirical",
        note: "no DOE schools within 1.0 mi" },
      { id: "k4", name: "doh.facility_join",        status: "silent_by_design", ms: 22,  tier: "empirical",
        note: "no acute-care hospitals within 1.0 mi" },
      { id: "k5", name: "pluto.lot_lookup",         status: "silent_by_design", ms: 18,  tier: "empirical",
        note: "PLUTO join skipped: queried address not in NYC PLUTO dataset" },
    ],
  },
  {
    key: "touchstone", name: "Touchstone", role: "the live observer",
    tag: "what's happening now",
    members: [
      { id: "t1", name: "floodnet.history",          status: "fired",  ms: 1240, tier: "empirical" },
      { id: "t2", name: "nyc311.flood_complaints",   status: "fired",  ms: 880,  tier: "proxy" },
      { id: "t3", name: "noaa_coops.recent",         status: "fired",  ms: 410,  tier: "empirical" },
      { id: "t4", name: "terramind.lulc",            status: "fired",  ms: 2100, tier: "synthetic" },
      { id: "t5", name: "prithvi_nyc_pluvial",       status: "fired",  ms: 1820, tier: "modeled" },
    ],
  },
  {
    key: "lodestone", name: "Lodestone", role: "the projector",
    tag: "what's coming",
    members: [
      { id: "l1", name: "npcc4.slr_projection",       status: "fired",   ms: 320,  tier: "modeled" },
      { id: "l2", name: "ttm_battery_surge.zero_shot",status: "fired",   ms: 1500, tier: "modeled" },
      { id: "l3", name: "ttm_battery_surge.fine_tune",status: "fired",   ms: 1480, tier: "modeled" },
      { id: "l4", name: "floodnet_forecast",          status: "silent_by_design", ms: 14, tier: "modeled",
        note: "sensor has only 2 historical events; forecast omitted (silent-floor: 5)" },
      { id: "l5", name: "ttm_311_forecast",           status: "errored", ms: 0,    tier: "modeled",
        error: "311 history fetch failed: HTTP 503 at NYC OpenData (3 retries)" },
    ],
  },
  {
    key: "capstone", name: "Capstone", role: "the synthesizer",
    tag: "writes it all down with citations",
    members: [
      { id: "p1", name: "granite.compose_briefing",  status: "fired", ms: 3200, tier: "modeled" },
      { id: "p2", name: "mellea.grounding_check",    status: "fired", ms: 480,  tier: "modeled" },
      { id: "p3", name: "weasyprint.render_artifact",status: "fired", ms: 920,  tier: null },
    ],
  },
];

const fmtMs = (ms) => ms === 0 ? "—" : ms < 1000 ? ms + "ms" : (ms / 1000).toFixed(1) + "s";
const tierColor = (t) => t ? `var(--tier-${t})` : "var(--ink-tertiary)";

const flat04 = (members) => members.flatMap(m => m.children ? [m, ...flat04(m.children)] : [m]);

const StoneAggregate = ({ stone }) => {
  const all = flat04(stone.members);
  const fired = all.filter(m => m.status === "fired" || m.status === "warned").length;
  const silent = all.filter(m => m.status === "silent_by_design").length;
  const warn = all.filter(m => m.status === "warned").length;
  const error = all.filter(m => m.status === "errored").length;
  const notInvoked = all.filter(m => m.status === "not_invoked").length;
  const ms = stone.members.reduce((acc, m) => Math.max(acc, m.ms || 0), 0);
  return (
    <span className="stone-band-agg">
      <span className="stone-band-agg-num">{fired}</span> fired
      {silent > 0 && <> · <span className="stone-band-agg-num">{silent}</span> silent</>}
      {warn > 0 && <> · <span className="stone-band-agg-warn">{warn} warn</span></>}
      {error > 0 && <> · <span className="stone-band-agg-err">{error} errored</span></>}
      {notInvoked > 0 && <> · <span className="stone-band-agg-num">{notInvoked}</span> not invoked</>}
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
  if (m.status === "errored") {
    return (
      <details className="trace-row trace-row-error trace-row-errored" style={{ paddingLeft: indent }}>
        <summary>
          <span className="trace-bullet trace-bullet-errored">■</span>
          <span className="trace-name">{m.name}</span>
          <span className="trace-status trace-status-err">errored</span>
          <span className="trace-tier" style={{ color: tierColor(m.tier) }}>{m.tier || ""}</span>
          <span className="trace-ms">{fmtMs(m.ms)}</span>
          <span className="trace-error-summary">{m.error}</span>
          <span className="trace-error-expand" aria-hidden="true">click to expand</span>
        </summary>
        <div className="trace-error-body">
          <div className="trace-error-line"><span className="trace-error-k">error</span><span>{m.error}</span></div>
          <div className="trace-error-line"><span className="trace-error-k">retries</span><span>3</span></div>
          <div className="trace-error-line"><span className="trace-error-k">elapsed</span><span>{fmtMs(m.ms)}</span></div>
        </div>
      </details>
    );
  }
  if (m.status === "silent_by_design") {
    return (
      <div className="trace-row trace-row-silent-bd" style={{ paddingLeft: indent }}>
        <span className="trace-bullet trace-bullet-silent">▢</span>
        <span className="trace-name">{m.name}</span>
        <span className="trace-status">silent</span>
        <span className="trace-tier" style={{ color: tierColor(m.tier) }}>{m.tier || ""}</span>
        <span className="trace-ms">{fmtMs(m.ms)}</span>
        {m.note && <span className="trace-silent-note">{m.note}</span>}
      </div>
    );
  }
  if (m.status === "not_invoked") {
    return (
      <div className="trace-row trace-row-not-invoked" style={{ paddingLeft: indent }}>
        <span className="trace-bullet trace-bullet-notinvoked">▫</span>
        <span className="trace-name">{m.name}</span>
        <span className="trace-status">not invoked</span>
        <span className="trace-tier" style={{ color: tierColor(m.tier) }}>{m.tier || ""}</span>
        <span className="trace-ms">—</span>
        {m.note && <span className="trace-note">{m.note}</span>}
      </div>
    );
  }
  if (m.status === "warned") {
    return (
      <div className="trace-row trace-row-warned" style={{ paddingLeft: indent }}>
        <span className="trace-bullet trace-bullet-warned" style={{ color: tierColor(m.tier) }}>■</span>
        <span className="trace-name">{m.name}</span>
        <span className="trace-status trace-status-warn">warned</span>
        <span className="trace-tier" style={{ color: tierColor(m.tier) }}>{m.tier || ""}</span>
        <span className="trace-ms">{fmtMs(m.ms)}</span>
        <span className="trace-warn-sidemark" aria-hidden="true">!</span>
        {m.warning && <span className="trace-warn-note">{m.warning}</span>}
      </div>
    );
  }
  /* fired */
  return (
    <div className="trace-row trace-row-fired" style={{ paddingLeft: indent }}>
      <span className="trace-bullet trace-bullet-fired" style={{ color: tierColor(m.tier), background: tierColor(m.tier) }}>■</span>
      <span className="trace-name">{m.name}</span>
      <span className="trace-status">fired</span>
      <span className="trace-tier" style={{ color: tierColor(m.tier) }}>{m.tier || ""}</span>
      <span className="trace-ms">{fmtMs(m.ms)}</span>
      {m.note && <span className="trace-note">{m.note}</span>}
    </div>
  );
};

const StoneBand = ({ stone }) => {
  const [open, setOpen] = useStV44(true);
  return (
    <section className={`stone-band stone-band-${stone.key}`} aria-labelledby={`band-h-${stone.key}`} data-stone={stone.key}>
      <button className="stone-band-head" aria-expanded={open} onClick={() => setOpen(o => !o)}>
        <span className="stone-band-head-left">
          <span id={`band-h-${stone.key}`} className="stone-band-name">{stone.name}</span>
          <span className="stone-band-role"> · {stone.role}</span>
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
  const all = STONES.flatMap(s => flat04(s.members));
  const fired = all.filter(m => m.status === "fired" || m.status === "warned").length;
  const silent = all.filter(m => m.status === "silent_by_design").length;
  const error = all.filter(m => m.status === "errored").length;
  return (
    <div className="trace-ui-v44">
      <header className="stone-trace-head">
        <span className="section-label">Run trace · 5 Stones</span>
        <span className="stone-trace-tally">{fired} fired · {silent} silent · {error} errored · 24.0s</span>
      </header>
      {STONES.map(s => <StoneBand key={s.key} stone={s}/>)}
    </div>
  );
};

Object.assign(window, { StoneTrace, STONES, TraceRow, fmtMs, tierColor });
