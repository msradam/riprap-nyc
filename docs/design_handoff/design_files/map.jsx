/* Static SVG mock of the MapLibre map for 80 Pioneer St, Red Hook.
   No network dependency. Encodes all four evidence-tier styles
   per the brief: empirical solid + 0.4 fill, modeled solid + 0.25,
   synthetic dashed + 0.25 with stripe, proxy graduated dots no fill.
*/

const RedHookMapMock = ({ activeLayers, queriedAddress }) => {
  return (
    <svg
      viewBox="0 0 800 560"
      width="100%"
      height="100%"
      role="application"
      aria-label={`NYC flood-exposure map for ${queriedAddress}`}
      style={{ display: "block", background: "#F2F2EE" }}
      preserveAspectRatio="xMidYMid slice"
    >
      <defs>
        {/* Diagonal stripe pattern for synthetic-prior fill */}
        <pattern id="syn-stripe" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" fill="rgba(42,111,168,0.18)"/>
          <line x1="0" y1="0" x2="0" y2="6" stroke="#2A6FA8" strokeWidth="1" />
        </pattern>
        {/* Halo for label readability */}
        <filter id="label-halo" x="-10%" y="-10%" width="120%" height="120%">
          <feMorphology in="SourceAlpha" radius="1.5" operator="dilate" result="halo"/>
          <feFlood floodColor="#FAFAF7"/>
          <feComposite in2="halo" operator="in"/>
          <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>

      {/* ── Basemap: Carto Positron register ── */}
      {/* Water (Erie Basin / Buttermilk Channel) */}
      <path d="M 0 380 L 220 360 L 360 410 L 520 470 L 800 500 L 800 560 L 0 560 Z" fill="#DCE6EC"/>
      <path d="M 540 0 L 580 0 L 600 90 L 640 180 L 700 240 L 800 280 L 800 0 Z" fill="#DCE6EC"/>

      {/* Park (Coffey Park) */}
      <rect x="380" y="240" width="90" height="60" fill="#E2E8DA"/>

      {/* Parcels (reference layer #E5E5E5) */}
      <g stroke="#C9C9C5" strokeWidth="0.5" fill="#FAFAF7">
        {Array.from({ length: 8 }).map((_, r) =>
          Array.from({ length: 14 }).map((_, c) => (
            <rect key={`p-${r}-${c}`} x={60 + c * 50} y={60 + r * 38} width="46" height="34" />
          ))
        )}
      </g>

      {/* Streets */}
      <g stroke="#FAFAF7" strokeWidth="6" fill="none">
        <path d="M 0 100 L 800 90"/>
        <path d="M 0 200 L 800 190"/>
        <path d="M 0 300 L 800 290"/>
        <path d="M 60 0 L 50 380"/>
        <path d="M 200 0 L 190 380"/>
        <path d="M 340 0 L 330 380"/>
        <path d="M 480 0 L 470 380"/>
        <path d="M 620 0 L 610 380"/>
      </g>
      <g stroke="#C9C9C5" strokeWidth="6.5" fill="none" opacity="0.0"/>

      {/* ── Empirical layer: Sandy Inundation Zone ── */}
      {activeLayers.empirical && (
        <g aria-label="Sandy Inundation Zone">
          <path
            d="M 0 380 L 220 360 L 360 410 L 520 470 L 800 500 L 800 560 L 0 560 Z
               M 0 360 L 240 340 L 380 390 L 540 450 L 800 480
               L 800 380 L 600 360 L 420 320 L 240 300 L 0 320 Z"
            fill="rgba(11,83,148,0.40)"
            stroke="#0B5394"
            strokeWidth="1.5"
            fillRule="evenodd"
          />
        </g>
      )}

      {/* ── Modeled layer: FEMA AE zone (solid line, 0.25 fill) ── */}
      {activeLayers.modeled && (
        <g aria-label="FEMA Zone AE">
          <path
            d="M 40 340 L 280 320 L 440 360 L 600 420 L 800 440 L 800 560 L 0 560 L 0 350 Z"
            fill="rgba(42,111,168,0.25)"
            stroke="#2A6FA8"
            strokeWidth="1.5"
            strokeDasharray="0"
          />
        </g>
      )}

      {/* ── Synthetic-prior: dashed line + stripe pattern ── */}
      {activeLayers.synthetic && (
        <g aria-label="Synthetic SAR backscatter (TerraMind, 2025-09-14)">
          <path
            d="M 100 380 L 260 360 L 380 390 L 480 420 L 600 440 L 720 460 L 720 500 L 100 500 Z"
            fill="url(#syn-stripe)"
            stroke="#2A6FA8"
            strokeWidth="1.5"
            strokeDasharray="4 3"
          />
        </g>
      )}

      {/* ── Proxy: 311 flood complaints (graduated dots, no fill) ── */}
      {activeLayers.proxy && (
        <g aria-label="311 flood complaints, 2019-2025">
          {[
            [120, 320, 5], [180, 350, 8], [220, 280, 4], [280, 330, 11],
            [340, 360, 6], [240, 240, 3], [380, 320, 9], [440, 350, 7],
            [200, 220, 4], [160, 280, 5], [340, 240, 3], [420, 280, 4],
            [500, 360, 6], [540, 400, 8], [180, 380, 5],
          ].map(([x, y, r], i) => (
            <circle key={i} cx={x} cy={y} r={r} fill="none" stroke="#6B6B6B" strokeWidth="1.25" />
          ))}
        </g>
      )}

      {/* ── Asset pins for register specialists ── */}
      {/* Subway entrance ,  square */}
      <g transform="translate(580 260)">
        <rect x="-5" y="-5" width="10" height="10" fill="#1A1A1A" />
        <text x="0" y="-9" fontSize="9" fontFamily="IBM Plex Sans" textAnchor="middle" fill="#1A1A1A" filter="url(#label-halo)">Smith–9 St</text>
      </g>
      {/* NYCHA ,  open square */}
      <g transform="translate(420 200)">
        <rect x="-5" y="-5" width="10" height="10" fill="none" stroke="#1A1A1A" strokeWidth="1.5"/>
        <text x="0" y="-9" fontSize="9" fontFamily="IBM Plex Sans" textAnchor="middle" fill="#1A1A1A" filter="url(#label-halo)">Red Hook Houses</text>
      </g>
      {/* School ,  cross */}
      <g transform="translate(360 280)" stroke="#1A1A1A" strokeWidth="1.75" fill="none">
        <line x1="-5" y1="0" x2="5" y2="0"/><line x1="0" y1="-5" x2="0" y2="5"/>
        <text x="8" y="3" fontSize="9" fontFamily="IBM Plex Sans" fill="#1A1A1A" filter="url(#label-halo)">PS 15</text>
      </g>
      {/* Hospital ,  circle */}
      <g transform="translate(680 160)">
        <circle r="5" fill="#1A1A1A"/>
        <text x="8" y="3" fontSize="9" fontFamily="IBM Plex Sans" fill="#1A1A1A" filter="url(#label-halo)">NYU Cobble Hill</text>
      </g>

      {/* ── Queried-address pin (warm orange, dominant at z14+) ── */}
      <g transform="translate(300 320)">
        <circle r="14" fill="rgba(209,124,0,0.20)"/>
        <circle r="6" fill="#D17C00" stroke="#FAFAF7" strokeWidth="2"/>
        <line x1="0" y1="6" x2="0" y2="22" stroke="#D17C00" strokeWidth="2"/>
        <text x="0" y="-12" fontSize="11" fontWeight="600" fontFamily="IBM Plex Sans" textAnchor="middle" fill="#1A1A1A" filter="url(#label-halo)">80 Pioneer St</text>
      </g>

      {/* ── Map labels (Imhof hierarchy: water italic, neighborhoods regular caps) ── */}
      <text x="640" y="490" fontSize="13" fontStyle="italic" fontFamily="IBM Plex Sans" fill="#5A7B8A" filter="url(#label-halo)">Buttermilk Channel</text>
      <text x="120" y="450" fontSize="13" fontStyle="italic" fontFamily="IBM Plex Sans" fill="#5A7B8A" filter="url(#label-halo)">Erie Basin</text>
      <text x="180" y="40" fontSize="14" fontFamily="IBM Plex Sans" fontWeight="500" letterSpacing="0.18em" fill="#4A4A4A" filter="url(#label-halo)">RED HOOK</text>
      <text x="600" y="40" fontSize="14" fontFamily="IBM Plex Sans" fontWeight="500" letterSpacing="0.18em" fill="#4A4A4A" filter="url(#label-halo)">CARROLL GARDENS</text>
      <text x="425" y="265" fontSize="11" fontFamily="IBM Plex Sans" fill="#4A6B4A" filter="url(#label-halo)">Coffey Park</text>

      {/* Street labels at z15+ */}
      <text x="120" y="195" fontSize="10" fontFamily="IBM Plex Sans" fill="#6B6B6B" filter="url(#label-halo)">Van Brunt St</text>
      <text x="120" y="295" fontSize="10" fontFamily="IBM Plex Sans" fill="#6B6B6B" filter="url(#label-halo)">Pioneer St</text>
      <text x="120" y="345" fontSize="10" fontFamily="IBM Plex Sans" fill="#6B6B6B" filter="url(#label-halo)">Imlay St</text>

      {/* ── Scale bar + zoom indicator (corners, like USGS quad) ── */}
      <g transform="translate(20 530)" fontFamily="IBM Plex Mono" fontSize="10" fill="#4A4A4A">
        <line x1="0" y1="-2" x2="80" y2="-2" stroke="#1A1A1A" strokeWidth="1.5"/>
        <line x1="0" y1="-5" x2="0" y2="1" stroke="#1A1A1A" strokeWidth="1"/>
        <line x1="40" y1="-5" x2="40" y2="1" stroke="#1A1A1A" strokeWidth="1"/>
        <line x1="80" y1="-5" x2="80" y2="1" stroke="#1A1A1A" strokeWidth="1"/>
        <text x="0" y="14">0</text>
        <text x="40" y="14" textAnchor="middle">200</text>
        <text x="80" y="14" textAnchor="middle">400 ft</text>
      </g>
      <g transform="translate(720 28)" fontFamily="IBM Plex Mono" fontSize="10" fill="#4A4A4A">
        <text x="0" y="0">z 16 · 40.6776°N 74.0096°W</text>
      </g>
    </svg>
  );
};

const MapLegend = ({ activeLayers, onToggle }) => {
  const layers = [
    { key: "empirical", tier: "empirical", label: "Sandy Inundation Zone (2012)", source: "NYC OEM" },
    { key: "modeled", tier: "modeled", label: "FEMA Zone AE ,  preliminary FIRM", source: "FEMA" },
    { key: "synthetic", tier: "synthetic", label: "Synthetic SAR (2025-09-14)", source: "TerraMind v1.2" },
    { key: "proxy", tier: "proxy", label: "311 flood complaints, 2019–25", source: "NYC 311" },
  ];
  return (
    <div className="map-legend" role="group" aria-label="Map layer toggles">
      <div className="map-legend-head">
        <span className="section-label">Layers</span>
      </div>
      {layers.map((l) => (
        <button
          key={l.key}
          type="button"
          className={`map-legend-item ${activeLayers[l.key] ? "is-on" : "is-off"}`}
          onClick={() => onToggle(l.key)}
          aria-pressed={activeLayers[l.key]}
        >
          <span className="map-legend-swatch" aria-hidden="true">
            <TierGlyph tier={l.tier} size={11} color={`var(--tier-${l.tier})`} />
          </span>
          <span className="map-legend-text">
            <span className="map-legend-label">{l.label}</span>
            <span className="map-legend-source">{l.source} · <TierBadge tier={l.tier} compact /></span>
          </span>
          <span className="map-legend-toggle" aria-hidden="true">{activeLayers[l.key] ? "ON" : "OFF"}</span>
        </button>
      ))}
    </div>
  );
};

Object.assign(window, { RedHookMapMock, MapLegend });
