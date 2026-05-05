/* Epistemic-tier glyphs.
   12×12 monochrome SVGs. Distinguishable by shape (filled square,
   open square, filled circle, striped square) ,  never by color alone.
   Used in: briefing prose left margin, evidence card badge, trace tier
   column, PDF body, MapLibre legend.
*/

const TierGlyph = ({ tier, size = 12, color = "currentColor", title }) => {
  const s = size;
  const stroke = Math.max(1, Math.round(size / 9));
  const ariaTitle = title || ({
    empirical: "Empirical: directly measured or observed",
    modeled: "Modeled: scenario-based prediction",
    proxy: "Proxy: indirect indicator",
    synthetic: "Synthetic prior: generated, not observed",
  })[tier];

  const patternId = `rip-stripe-${tier}-${size}`;

  return (
    <svg
      width={s}
      height={s}
      viewBox={`0 0 ${s} ${s}`}
      role="img"
      aria-label={ariaTitle}
      style={{ flex: "none", display: "inline-block", verticalAlign: "-0.12em" }}
    >
      <title>{ariaTitle}</title>
      {tier === "empirical" && (
        <rect x="0" y="0" width={s} height={s} fill={color} />
      )}
      {tier === "modeled" && (
        <rect
          x={stroke / 2}
          y={stroke / 2}
          width={s - stroke}
          height={s - stroke}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
        />
      )}
      {tier === "proxy" && (
        <circle cx={s / 2} cy={s / 2} r={s / 2 - 0.5} fill={color} />
      )}
      {tier === "synthetic" && (
        <>
          <defs>
            <pattern
              id={patternId}
              width="3"
              height="3"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)"
            >
              <line x1="0" y1="0" x2="0" y2="3" stroke={color} strokeWidth="1.5" />
            </pattern>
          </defs>
          <rect
            x={stroke / 2}
            y={stroke / 2}
            width={s - stroke}
            height={s - stroke}
            fill={`url(#${patternId})`}
            stroke={color}
            strokeWidth={stroke}
          />
        </>
      )}
    </svg>
  );
};

const TIER_META = {
  empirical: {
    label: "Empirical",
    short: "EMP",
    desc: "Directly measured or observed",
    examples: "USGS high-water marks · FloodNet sensors · Sandy Inundation Zone",
  },
  modeled: {
    label: "Modeled",
    short: "MOD",
    desc: "Scenario-based prediction",
    examples: "FEMA flood zones · DEP stormwater scenarios · NPCC4 SLR",
  },
  proxy: {
    label: "Proxy",
    short: "PRX",
    desc: "Indirect indicator",
    examples: "311 flood complaints · NFIP claims · terrain indices",
  },
  synthetic: {
    label: "Synthetic prior",
    short: "SYN",
    desc: "Generated, not observed",
    examples: "TerraMind land-cover · synthetic SAR for occluded days",
  },
};

const TierBadge = ({ tier, compact = false }) => {
  const meta = TIER_META[tier];
  return (
    <span
      className={`tier-badge tier-badge-${tier}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontFamily: "var(--font-mono)",
        fontSize: 11,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        color: `var(--tier-${tier})`,
        fontWeight: 500,
      }}
      title={meta.desc}
    >
      <TierGlyph tier={tier} size={10} color={`var(--tier-${tier})`} />
      {compact ? meta.short : meta.label}
    </span>
  );
};

Object.assign(window, { TierGlyph, TierBadge, TIER_META });
