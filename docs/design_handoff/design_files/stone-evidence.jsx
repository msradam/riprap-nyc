/* Riprap v0.4.4 ,  Unified Stone bands.
   Each Stone holds: header (name + aggregate) → evidence cards → collapsed trace.
   This replaces the duplicated "evidence grouped by stone" + "trace grouped by stone".
*/

const { useState: useSEv44 } = React;

const EVIDENCE_BY_STONE = {
  cornerstone: ["e1", "e3", "e4"],   // USGS HWMs · FEMA FIRM · DEP stormwater
  keystone:    [],                    // (no exposure-register cards in current EVIDENCE ,  Keystone-silent)
  touchstone:  ["e2", "e7"],          // FloodNet sensor · 311 complaints
  lodestone:   ["e5"],                // NPCC4 SLR projection
  capstone:    ["e6", "e8"],          // synthesis-tier outputs
};

const STONE_LOOKUP_V44 = {
  cornerstone: { name: "Cornerstone", role: "the hazard reader",  tag: "what NYC's ground remembers" },
  keystone:    { name: "Keystone",    role: "the asset register", tag: "what's exposed" },
  touchstone:  { name: "Touchstone",  role: "the live observer",  tag: "what's happening now" },
  lodestone:   { name: "Lodestone",   role: "the projector",      tag: "what's coming" },
  capstone:    { name: "Capstone",    role: "the synthesizer",    tag: "writes it all down with citations" },
};

/* Walk a Stone's trace members (incl. nested children) into a flat list for tally. */
const flattenMembers = (members) =>
  members.flatMap((m) => (m.children ? [m, ...flattenMembers(m.children)] : [m]));

const StoneTally = ({ cards, members }) => {
  const flat = flattenMembers(members);
  const fired = flat.filter((m) => m.status === "ok").length;
  const silent = flat.filter((m) => m.status === "silent").length;
  const warn = flat.filter((m) => m.status === "warn").length;
  const error = flat.filter((m) => m.status === "error").length;
  const ms = members.reduce((acc, m) => Math.max(acc, m.ms || 0), 0);
  const fmt = (x) => (x === 0 ? ", " : x < 1000 ? x + "ms" : (x / 1000).toFixed(1) + "s");
  return (
    <span className="stone-uni-agg">
      <span className="stone-uni-agg-cards">{cards.length} card{cards.length === 1 ? "" : "s"}</span>
      <span className="stone-uni-agg-sep">·</span>
      <span className="stone-uni-agg-num">{fired}</span> fired
      {silent > 0 && <>{" · "}<span className="stone-uni-agg-num">{silent}</span> silent</>}
      {warn > 0 && <>{" · "}<span className="stone-uni-agg-warn">{warn} warn</span></>}
      {error > 0 && <>{" · "}<span className="stone-uni-agg-err">{error} error</span></>}
      <span className="stone-uni-agg-sep">·</span>
      <span className="stone-uni-agg-ms">{fmt(ms)}</span>
    </span>
  );
};

const UnifiedStoneBand = ({ stone, cardIds, onCite }) => {
  const meta = STONE_LOOKUP_V44[stone.key];
  const cards = cardIds.map((id) => EVIDENCE.find((e) => e.id === id)).filter(Boolean);
  const traceCount = flattenMembers(stone.members).length;
  const [traceOpen, setTraceOpen] = useSEv44(false);

  return (
    <section className={`stone-uni stone-uni-${stone.key}`} aria-labelledby={`stone-uni-h-${stone.key}`}>
      <header className="stone-uni-head">
        <div className="stone-uni-head-left">
          <h3 id={`stone-uni-h-${stone.key}`} className="stone-uni-name">{meta.name}</h3>
          <span className="stone-uni-role">,  {meta.role}</span>
          <span className="stone-uni-tag">{meta.tag}</span>
        </div>
        <StoneTally cards={cards} members={stone.members}/>
      </header>

      {/* Findings ,  primary surface */}
      {cards.length === 0 ? (
        <div className="stone-uni-empty">
          <span className="section-label">silent</span>
          <p>No exposure-register cards landed for this query ,  Keystone's atomic functions all fired (5 joins, see trace) but none of the asset registers (MTA, NYCHA, DOE, DOH, PLUTO) returned a hit at this address.</p>
        </div>
      ) : (
        <div className="stone-uni-rail">
          {cards.map((ev) => <EvidenceCard key={ev.id} ev={ev} onCite={onCite}/>)}
        </div>
      )}

      {/* Provenance ,  collapsed by default */}
      <div className="stone-uni-trace">
        <button
          className="stone-uni-trace-toggle"
          aria-expanded={traceOpen}
          onClick={() => setTraceOpen((o) => !o)}
        >
          <span className="stone-uni-trace-caret" aria-hidden="true">{traceOpen ? "▾" : "▸"}</span>
          <span className="stone-uni-trace-label">
            {traceOpen ? "Hide" : "Show"} provenance · {traceCount} function{traceCount === 1 ? "" : "s"}
          </span>
        </button>
        {traceOpen && (
          <div className="stone-uni-trace-body">
            {stone.members.map((m) => <window.TraceRow key={m.id} m={m}/>)}
          </div>
        )}
      </div>
    </section>
  );
};

/* Global tally strip ,  at-a-glance run health */
const RunHealthStrip = () => {
  const allMembers = STONES.flatMap((s) => flattenMembers(s.members));
  const fired = allMembers.filter((m) => m.status === "ok").length;
  const total = allMembers.length;
  const silent = allMembers.filter((m) => m.status === "silent").length;
  const warn = allMembers.filter((m) => m.status === "warn").length;
  const error = allMembers.filter((m) => m.status === "error").length;
  const totalCards = Object.values(EVIDENCE_BY_STONE).reduce((n, ids) => n + ids.length, 0);
  return (
    <div className="run-health">
      <span className="run-health-item"><strong>5</strong> Stones</span>
      <span className="run-health-sep">·</span>
      <span className="run-health-item"><strong>{fired}/{total}</strong> functions fired</span>
      <span className="run-health-sep">·</span>
      <span className="run-health-item"><strong>{totalCards}</strong> evidence cards</span>
      <span className="run-health-sep">·</span>
      <span className="run-health-item run-health-time"><strong>14.0s</strong> wall-clock</span>
      {silent > 0 && <><span className="run-health-sep">·</span><span className="run-health-item run-health-silent">{silent} silent</span></>}
      {warn > 0 && <><span className="run-health-sep">·</span><span className="run-health-item run-health-warn">{warn} warn</span></>}
      {error > 0 && <><span className="run-health-sep">·</span><span className="run-health-item run-health-error">{error} error</span></>}
    </div>
  );
};

const UnifiedStoneLayout = ({ onCite }) => (
  <section className="stone-uni-layout" aria-label="Findings and provenance, grouped by Stone">
    <RunHealthStrip/>
    {STONES.map((stone) => (
      <UnifiedStoneBand
        key={stone.key}
        stone={stone}
        cardIds={EVIDENCE_BY_STONE[stone.key] || []}
        onCite={onCite}
      />
    ))}
  </section>
);

Object.assign(window, { UnifiedStoneLayout });
