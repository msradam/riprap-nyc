/* App shell + cold-start state + spec sections that live below the
   prototype: typography spec, palette spec, glyph spec, MapLibre style.json
   fragments, layout grids, PDF template preview, accessibility checklist,
   design rationale, reference register sketches.
*/

const SAMPLE_QUERIES = [
  { mode: "address", q: "80 Pioneer Street, Red Hook, Brooklyn",
    sub: "Address-mode · Sandy edge · IBZ · NYCHA proximity" },
  { mode: "neighborhood", q: "Far Rockaway flood exposure briefing",
    sub: "Neighborhood-mode · chronic stormwater · 2050 SLR" },
  { mode: "development", q: "Hunts Point proposed rezoning ,  flood-context check",
    sub: "Development-check · CEQR §817 · 311 proxy density" },
];

const ColdStart = ({ onPick, onSubmit }) => {
  const [v, setV] = useState("");
  return (
    <section className="cold-start" aria-label="Empty query state">
      <div className="cold-start-band">
        <p className="cold-start-deck">
          <strong>Riprap</strong> is a citation-grounded Flood Exposure Briefing tool for New York City.
          Type an address, neighborhood, or proposed development ,  Riprap returns a written briefing
          where every numeric claim links to its primary public-record source.
        </p>
        <p className="cold-start-deck cold-start-deck-secondary">
          Built for agency analysts, planners, journalists, community boards, and researchers.
          <strong> Not for individual residents making personal property decisions.</strong>
          {" "}For residents seeking flood guidance, see <a href="https://www.floodhelpny.org" className="cold-start-redir">FloodHelpNY</a>.
          For real-time conditions, see <a href="https://www.floodnet.nyc" className="cold-start-redir">FloodNet NYC</a>.
        </p>
      </div>

      <form
        className="cold-start-form"
        onSubmit={(e) => { e.preventDefault(); onSubmit?.(v); }}
        role="search"
      >
        <label htmlFor="riprap-query" className="cold-start-label section-label">Query</label>
        <div className="cold-start-input-row">
          <input
            id="riprap-query"
            type="text"
            value={v}
            onChange={(e) => setV(e.target.value)}
            placeholder="address · neighborhood · proposed development"
            className="cold-start-input"
            autoComplete="off"
          />
          <button type="submit" className="cold-start-submit">Generate briefing →</button>
        </div>
      </form>

      <div className="cold-start-samples">
        <span className="section-label cold-start-samples-label">Sample queries</span>
        <div className="cold-start-samples-grid">
          {SAMPLE_QUERIES.map((s, i) => (
            <button
              key={i}
              type="button"
              className="cold-start-sample"
              onClick={() => onPick?.(s)}
            >
              <span className="cold-start-sample-mode">{s.mode}</span>
              <span className="cold-start-sample-q">{s.q}</span>
              <span className="cold-start-sample-sub">{s.sub}</span>
              <span className="cold-start-sample-arrow" aria-hidden="true">↗</span>
            </button>
          ))}
        </div>
      </div>

      <div className="cold-start-trust">
        <span className="section-label">How Riprap is built</span>
        <p className="cold-start-thesis">
          <strong>Cornerstone</strong> remembers. <strong>Keystone</strong> tallies.
          {" "}<strong>Touchstone</strong> watches. <strong>Lodestone</strong> projects.
          {" "}<strong>Capstone</strong> writes it all down with citations.
        </p>
        <ul className="cold-start-trust-list">
          <li>Five named cognitive roles compose ~25 atomic specialists. <a href="#spec-stones">Architecture →</a></li>
          <li>All foundation models <strong>Apache-2.0</strong>; no commercial APIs at runtime.</li>
          <li>All data from public-record federal, state, and city sources.</li>
          <li>Four epistemic tiers ,  empirical, modeled, proxy, synthetic prior ,  visible in the briefing margin and the trace.</li>
          <li>Sections without supporting documents are omitted entirely. Silence over confabulation.</li>
        </ul>
        <a href="#methodology" className="cold-start-method-link">Methodology paper →</a>
      </div>
    </section>
  );
};

const AppHeader = ({ query, onResetCold, onOpenMethodology }) => (
  <header className="app-header" data-screen-label="App header">
    <div className="app-header-inner">
      <div className="app-header-left">
        <span className="riprap-wordmark" aria-label="Riprap">riprap</span>
        <span className="app-header-sep">/</span>
        <span className="app-header-context">Flood Exposure Briefing</span>
      </div>
      <div className="app-header-mid">
        <button
          type="button"
          className="app-header-query"
          onClick={onResetCold}
          aria-label="Edit query"
        >
          <span className="app-header-query-icon" aria-hidden="true">⌕</span>
          <span className="app-header-query-text">{query}</span>
          <span className="app-header-query-edit">edit</span>
        </button>
      </div>
      <div className="app-header-right">
        <a className="app-header-link" href="#methodology" onClick={(e) => { e.preventDefault(); onOpenMethodology?.(); }}>methodology</a>
        <a className="app-header-link" href="#export-pdf">export PDF</a>
        <span className="app-header-status" aria-live="polite">
          <span className="app-header-status-dot" aria-hidden="true"></span>
          live
        </span>
      </div>
    </div>
  </header>
);

const AppFooter = () => (
  <footer className="app-footer">
    <div className="app-footer-inner">
      <p className="app-footer-guard">
        <strong>Riprap does not predict damage.</strong>
        {" "}This tool is for professional analytical work, not personal property decisions.
        For residents, see <a href="https://www.floodhelpny.org">FloodHelpNY</a> · <a href="https://www.floodnet.nyc">FloodNet NYC</a>.
      </p>
      <p className="app-footer-build">
        All foundation models Apache-2.0 · All data from public-record federal, state, and city sources · No commercial APIs contacted at runtime · Riprap v0.4.3 · build 2026-05-05
      </p>
    </div>
  </footer>
);

Object.assign(window, { ColdStart, AppHeader, AppFooter });
