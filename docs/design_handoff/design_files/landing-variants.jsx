/* Riprap landing-page variants — three artboards on a design canvas.
   v1: Minimal pushed harder (cycling example queries + tiny grounded-output preview)
   v2: Example gallery (query box + 6 pre-baked NYC archetype briefings)
   v3: Methodology-forward (5 Stones frieze leads, query box below)
*/

const { useState: useLand, useEffect: useLandFx } = React;

/* ═══════════════════════════════════════════════════════════════════════
   Shared chrome — wordmark + footer methodology link
   ═══════════════════════════════════════════════════════════════════════ */
const LandingChrome = ({ children, board }) => (
  <div className={`land land-${board}`}>
    <header className="land-header">
      <span className="riprap-wordmark">riprap</span>
      <span className="land-header-sep">/</span>
      <span className="land-header-context">Flood Exposure Briefing · NYC</span>
      <nav className="land-header-nav">
        <a href="#methodology">Methodology</a>
        <a href="#sources">Sources</a>
        <a href="#about">About</a>
      </nav>
    </header>
    {children}
    <footer className="land-footer">
      <span>Riprap v0.4.4 — built on NYC OpenData, FEMA NFHL, USGS, NPCC4</span>
      <span>Each briefing is a citation graph. Every claim links to its primary source.</span>
    </footer>
  </div>
);

const QueryBox = ({ size = "md", placeholder = "Address, neighborhood, or BBL — e.g. 80 Pioneer Street, Red Hook" }) => (
  <form className={`land-query land-query-${size}`} onSubmit={(e) => e.preventDefault()}>
    <span className="land-query-prompt" aria-hidden="true">›</span>
    <input
      type="text"
      placeholder={placeholder}
      className="land-query-input"
      aria-label="Query an address, neighborhood, or BBL"
    />
    <button type="submit" className="land-query-submit">
      Brief this place →
    </button>
  </form>
);

/* ═══════════════════════════════════════════════════════════════════════
   v1 · Minimal pushed harder
   ═══════════════════════════════════════════════════════════════════════ */
const SAMPLE_QUERIES = [
  "80 Pioneer Street, Red Hook",
  "Coney Island Hospital",
  "PS 188, Lower East Side",
  "Hammels Houses, Rockaway",
  "Bowling Green station",
  "555 W 57th Street",
];

const CyclingExamples = () => {
  const [i, setI] = useLand(0);
  useLandFx(() => {
    const t = setInterval(() => setI((x) => (x + 1) % SAMPLE_QUERIES.length), 2200);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="land-cycling" aria-live="polite">
      <span className="land-cycling-label">Try:</span>
      <span className="land-cycling-rail">
        {SAMPLE_QUERIES.map((q, idx) => (
          <span
            key={q}
            className={`land-cycling-item ${idx === i ? "is-active" : ""}`}
            aria-hidden={idx !== i}
          >
            {q}
          </span>
        ))}
      </span>
    </div>
  );
};

const GroundedOutputPreview = () => (
  <div className="land-preview" aria-label="Sample of grounded output">
    <div className="land-preview-frame">
      <div className="land-preview-eyebrow">Excerpt — 80 Pioneer Street briefing</div>
      <p className="land-preview-body">
        The lot sits inside the FEMA <span className="land-preview-cite">1% AE flood zone <sup>[c3]</sup></span>,
        with Hurricane Sandy storm-surge high-water marks recorded
        <span className="land-preview-cite"> 4.7 ft above grade <sup>[c1]</sup></span> at the address.
        FloodNet sensor FN-BK-018, two blocks north, has logged
        <span className="land-preview-cite"> 14 nuisance-flood events since 2023 <sup>[c2]</sup></span>.
      </p>
      <div className="land-preview-cites">
        <div className="land-preview-cite-row">
          <span className="land-preview-cite-pin">[c1]</span>
          <span className="land-preview-cite-src">USGS High-Water Mark · Sandy 2012</span>
          <span className="land-preview-cite-tier">empirical</span>
        </div>
        <div className="land-preview-cite-row">
          <span className="land-preview-cite-pin">[c2]</span>
          <span className="land-preview-cite-src">FloodNet sensor FN-BK-018 · 2023–2026</span>
          <span className="land-preview-cite-tier">empirical</span>
        </div>
        <div className="land-preview-cite-row">
          <span className="land-preview-cite-pin">[c3]</span>
          <span className="land-preview-cite-src">FEMA NFHL · panel 36047C0207</span>
          <span className="land-preview-cite-tier">modeled</span>
        </div>
      </div>
    </div>
  </div>
);

const LandingV1 = () => (
  <LandingChrome board="v1">
    <main className="land-hero land-hero-v1">
      <h1 className="land-hero-h1">
        <span className="land-hero-eyebrow">Riprap</span>
        <span className="land-hero-headline">A flood exposure briefing for any place in New York City.</span>
        <span className="land-hero-deck">
          Type an address. Get a written briefing where every numeric claim
          links to its primary public-record source.
        </span>
      </h1>
      <QueryBox size="lg"/>
      <CyclingExamples/>
    </main>
    <section className="land-section land-section-v1">
      <div className="land-section-head">
        <span className="section-label">What you'll get back</span>
        <span className="land-section-meta">A grounded paragraph with citations — not a chatbot answer.</span>
      </div>
      <GroundedOutputPreview/>
    </section>
  </LandingChrome>
);

/* ═══════════════════════════════════════════════════════════════════════
   v2 · Example gallery
   ═══════════════════════════════════════════════════════════════════════ */
const GALLERY = [
  { kind: "Address",     title: "80 Pioneer Street",       sub: "Red Hook · industrial loft on Sandy inundation footprint",      tally: "8 cards · 1% AE zone · 4.7ft Sandy HWM" },
  { kind: "Hospital",    title: "Coney Island Hospital",   sub: "Brooklyn · NYC Health+Hospitals · coastal AE-zone facility",     tally: "11 cards · evacuated 2012 · NPCC4 +30in by 2070" },
  { kind: "School",      title: "PS 188",                  sub: "Lower East Side · K-5 · 1.3mi from East River shore",            tally: "6 cards · 0.2% shaded-X zone · DEP CSO outfall 200ft" },
  { kind: "NYCHA",       title: "Hammels Houses",          sub: "Rockaway · 712 units · ocean-side public housing",               tally: "13 cards · multi-event flooding · TerraMind synthetic SAR" },
  { kind: "Transit",     title: "Bowling Green station",   sub: "Lower Manhattan · 4/5 line · 2012 inundation, post-Sandy hardened", tally: "9 cards · MTA flood-resilience capital plan referenced" },
  { kind: "Address",     title: "555 W 57th Street",       sub: "Hell's Kitchen · inland · low-exposure control case",            tally: "4 cards · X-zone · cited for context comparison" },
];

const GalleryCard = ({ item }) => (
  <a className="land-gallery-card" href="#" onClick={(e) => e.preventDefault()}>
    <div className="land-gallery-kind">{item.kind}</div>
    <h3 className="land-gallery-title">{item.title}</h3>
    <p className="land-gallery-sub">{item.sub}</p>
    <div className="land-gallery-tally">{item.tally}</div>
    <span className="land-gallery-arrow" aria-hidden="true">Open briefing →</span>
  </a>
);

const LandingV2 = () => (
  <LandingChrome board="v2">
    <main className="land-hero land-hero-v2">
      <h1 className="land-hero-h1">
        <span className="land-hero-eyebrow">Riprap · Flood Exposure Briefing</span>
        <span className="land-hero-headline">What does flood mean for this place in New York?</span>
        <span className="land-hero-deck">
          Riprap reads a place across hazard, exposure, observation, and projection —
          and writes it down with citations.
        </span>
      </h1>
      <QueryBox size="lg"/>
    </main>
    <section className="land-section land-section-v2">
      <div className="land-section-head">
        <span className="section-label">Or open a sample briefing</span>
        <span className="land-section-meta">Six NYC archetypes · pre-computed · click to read</span>
      </div>
      <div className="land-gallery">
        {GALLERY.map((it) => <GalleryCard key={it.title} item={it}/>)}
      </div>
    </section>
    <section className="land-section land-section-stones">
      <div className="land-section-head">
        <span className="section-label">How Riprap reads a place</span>
        <a className="land-section-link" href="#methodology">See methodology →</a>
      </div>
      <div className="land-stones-strip">
        <div className="land-stone-pill"><strong>Cornerstone</strong> hazard reader</div>
        <div className="land-stone-pill"><strong>Keystone</strong> asset register</div>
        <div className="land-stone-pill"><strong>Touchstone</strong> live observer</div>
        <div className="land-stone-pill"><strong>Lodestone</strong> projector</div>
        <div className="land-stone-pill"><strong>Capstone</strong> synthesizer</div>
      </div>
    </section>
  </LandingChrome>
);

/* ═══════════════════════════════════════════════════════════════════════
   v3 · Methodology-forward
   ═══════════════════════════════════════════════════════════════════════ */
const STONE_FRIEZE = [
  { name: "Cornerstone", role: "the hazard reader",  tag: "what NYC's ground remembers", sources: "USGS HWMs · FEMA NFHL · DEP stormwater · Prithvi historical" },
  { name: "Keystone",    role: "the asset register", tag: "what's exposed",              sources: "MTA · NYCHA · DOE · DOH · PLUTO" },
  { name: "Touchstone",  role: "the live observer",  tag: "what's happening now",        sources: "FloodNet sensors · 311 complaints · tidal gauges" },
  { name: "Lodestone",   role: "the projector",      tag: "what's coming",               sources: "NPCC4 · TTM foundation model · TerraMind synthetic SAR · NFIP" },
  { name: "Capstone",    role: "the synthesizer",    tag: "writes it all down",          sources: "Granite composer · Mellea grounding-check · WeasyPrint" },
];

const LandingV3 = () => (
  <LandingChrome board="v3">
    <main className="land-hero land-hero-v3">
      <h1 className="land-hero-h1">
        <span className="land-hero-eyebrow">Riprap · Flood Exposure Briefing</span>
        <span className="land-hero-headline">Five Stones read every place.</span>
        <span className="land-hero-deck">
          Each briefing routes through a fixed taxonomy of public-record specialists.
          Each Stone is a class of evidence; together they form the briefing.
        </span>
      </h1>
      <div className="land-frieze">
        {STONE_FRIEZE.map((s, i) => (
          <article key={s.name} className="land-frieze-stone">
            <div className="land-frieze-num">{String(i + 1).padStart(2, "0")}</div>
            <h3 className="land-frieze-name">{s.name}</h3>
            <div className="land-frieze-role">{s.role}</div>
            <p className="land-frieze-tag">{s.tag}</p>
            <div className="land-frieze-sources">{s.sources}</div>
          </article>
        ))}
      </div>
      <div className="land-frieze-query">
        <QueryBox size="lg"/>
        <span className="land-frieze-query-meta">
          Try <button className="land-link" type="button">80 Pioneer Street, Red Hook</button> ·
          <button className="land-link" type="button"> Coney Island Hospital</button> ·
          <button className="land-link" type="button"> Hammels Houses</button>
        </span>
      </div>
    </main>
  </LandingChrome>
);

/* ═══════════════════════════════════════════════════════════════════════
   Canvas mount
   ═══════════════════════════════════════════════════════════════════════ */
const App = () => (
  <DesignCanvas
    title="Riprap landing — three directions"
    subtitle="Compare side-by-side. Click any artboard to focus."
  >
    <DCSection id="landings" title="Landing page · directions">
      <DCArtboard id="v1" label="v1 · Minimal pushed harder" width={1200} height={1500}>
        <LandingV1/>
      </DCArtboard>
      <DCArtboard id="v2" label="v2 · Example gallery" width={1200} height={1700}>
        <LandingV2/>
      </DCArtboard>
      <DCArtboard id="v3" label="v3 · Methodology-forward" width={1200} height={1500}>
        <LandingV3/>
      </DCArtboard>
    </DCSection>
  </DesignCanvas>
);

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
