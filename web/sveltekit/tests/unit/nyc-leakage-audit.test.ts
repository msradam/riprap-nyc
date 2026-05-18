/**
 * Static NYC-leak audit — reads every .svelte source file and flags
 * NYC-specific strings that aren't justified by an in-file allow-list
 * comment (`// nyc-leak-ok: <reason>`).
 *
 * This is the catch-all gate. Unit + integration tests cover specific
 * rendering paths; this one greps the source so any new hardcoded
 * "NYC OEM" / "FloodHelpNY" / "MTA station entrance dataset" / etc.
 * fails CI without needing a per-component test.
 *
 * Allow-listing is explicit: add `// nyc-leak-ok: <reason>` on or just
 * above the offending line. That's the contract — every NYC reference
 * in user-visible markup must be a deliberate, deployment-gated, or
 * justified-as-credit choice.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

// Vitest runs from the package root (web/sveltekit). `process.cwd()`
// gives us a stable anchor without relying on import.meta.url which
// vitest serves through a non-file scheme.
const COMPONENTS_DIR = join(process.cwd(), 'src/lib/components');

/** Patterns that indicate NYC-specific content. Each match is
 *  REVIEWED — false positives can be allow-listed in-file with
 *  `// nyc-leak-ok: <reason>`. */
const NYC_PATTERNS: { re: RegExp; description: string }[] = [
  { re: /\bNYC\b/g,                description: 'literal "NYC"' },
  { re: /\bNYCHA\b/g,              description: 'NYCHA reference' },
  { re: /MTA subway entrances/g,   description: 'MTA-specific text' },
  { re: /Sandy Inundation/gi,      description: 'Sandy Inundation reference' },
  { re: /Hurricane Ida/g,          description: 'Hurricane Ida reference' },
  { re: /Ida HWM/g,                description: 'Ida HWM reference' },
  { re: /FloodHelpNY/g,            description: 'FloodHelpNY link' },
  { re: /FloodNet NYC/g,           description: 'FloodNet NYC link' },
  { re: /Prithvi-NYC/g,            description: 'Prithvi-NYC model reference' },
  { re: /five boroughs/gi,         description: '"five boroughs" phrase' },
  { re: /the Battery/gi,           description: '"the Battery" NYC reference' },
  { re: /Brooklyn|Manhattan|Queens|the Bronx|Staten Island/gi, description: 'NYC borough name' },
];

/** Files exempt from the audit:
 *    - landing/  → marketing copy intentionally describes shipped cities
 *    - tests/    → fixtures + test code legitimately contain needles
 *    - .test.    → already excluded by COMPONENTS_DIR but defensive
 */
const EXEMPT_FILES = new Set<string>([
  // Landing pages: marketing copy that references shipped cities
  // (NYC, Boston, Chicago, Seattle, SF) as features — this is by
  // design, not a leak.
  'landing/CityPicker.svelte',
  'landing/LandHero.svelte',
  'landing/LandHeader.svelte',
  'landing/LandFooter.svelte',
  'landing/LandStones.svelte',
  'landing/SourceStrip.svelte',
  'landing/LandMiniMap.svelte',
  'landing/StandardsStrip.svelte',
  'landing/UseBand.svelte',
  'landing/PhaseBanner.svelte',
  'landing/ByodDialog.svelte',
  // RegisterCard renders ONLY when NYC register data is present (the
  // four NYC-only register specialists fired). NYC-specific provenance
  // text inside it is therefore data-gated, not deployment-leaked.
  'evidence/RegisterCard.svelte',
  // RegisterBody is the cardAdapter-driven variant of the same data
  // path. Same gating logic — empty `registers` array → no render.
  'findings/cards/RegisterBody.svelte',
  // RipMap layer descriptions reference NYC-specific data sources
  // (FloodNet NYC, Prithvi-NYC). Map layers visibility is itself
  // gated on the per-query manifest's display.map_layer flag, so
  // these strings only render when their data source is active.
  'map/RipMap.svelte',
  // ColdStart copy mentions Sandy/NYCHA proximity as an example query
  // type for the analyst's empty state. Pre-deployment-pick render,
  // hazard-agnostic context; the per-query chip overrides downstream.
  // TODO(post-launch): rotate the example query per active deployment.
  'shell/ColdStart.svelte',
  // CardGrammarReference is a dev-only documentation surface rendered
  // ONLY when /q/[queryId]?grammar=1 is in the URL. The NYC examples
  // are spec catalog data, not user-facing content for any
  // production briefing render.
  'findings/CardGrammarReference.svelte',
]);

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (full.endsWith('.svelte')) out.push(full);
  }
  return out;
}

/** Strip JS/TS line + block comments and HTML comments from source so
 *  the audit only sees user-visible text. Comments may legitimately
 *  reference NYC (incident history, bug context, design rationale)
 *  without being rendered. */
function stripComments(src: string): string {
  let out = src.replace(/<!--[\s\S]*?-->/g, '');                   // HTML
  out = out.replace(/\/\*[\s\S]*?\*\//g, '');                       // JS block
  out = out.replace(/(^|[^:"'`])\/\/[^\n]*/g, (_, prefix) => prefix); // JS line
  return out;
}

/** Heuristic: a TS object-literal key like `nyc311: '...'` is a
 *  dictionary lookup, NOT user-visible text. The label only renders
 *  when that pebble id fires — which only happens under that
 *  deployment. Skip lines that look like dictionary KEYS containing
 *  NYC pebble names. */
function isPebbleIdMapKey(line: string): boolean {
  // Matches `  nycXXX: 'value'` or `  nycha_developments: 'value'`
  // or `  ttm_battery_surge: 'TTM Battery (NYC fine-tune)'`
  // — these are pebble-id → short-label maps in StatusPill.
  return /^\s*(nyc311|nycha_\w+|ttm_battery_surge|prithvi_eo_live|nycha_development_exposure)\s*:/i.test(line);
}

interface Leak {
  file: string;
  line: number;
  pattern: string;
  context: string;
}

function findLeaks(): Leak[] {
  const leaks: Leak[] = [];
  const files = walk(COMPONENTS_DIR);
  for (const path of files) {
    const rel = relative(COMPONENTS_DIR, path);
    if (EXEMPT_FILES.has(rel)) continue;
    const src = readFileSync(path, 'utf8');
    const stripped = stripComments(src);
    const lines = stripped.split('\n');
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (!line.trim()) continue;
      // Skip inline allow-list (preserves on either the line or
      // directly above, even after comment stripping — we keep the
      // directive by scanning the ORIGINAL line text).
      const origLine = src.split('\n')[i] ?? '';
      if (origLine.includes('nyc-leak-ok')) continue;
      if (i > 0 && (src.split('\n')[i - 1] ?? '').includes('nyc-leak-ok')) continue;
      // Skip pebble-id → label maps (only fire when the named pebble
      // does, which is itself deployment-gated).
      if (isPebbleIdMapKey(line)) continue;
      for (const { re, description } of NYC_PATTERNS) {
        re.lastIndex = 0;
        if (re.test(line)) {
          leaks.push({
            file: rel,
            line: i + 1,
            pattern: description,
            context: line.trim().slice(0, 140),
          });
        }
      }
    }
  }
  return leaks;
}

describe('NYC-leakage audit across all .svelte components', () => {
  it('every non-exempt component is free of NYC-specific hardcoded strings', () => {
    const leaks = findLeaks();
    if (leaks.length > 0) {
      const grouped = new Map<string, Leak[]>();
      for (const l of leaks) {
        if (!grouped.has(l.file)) grouped.set(l.file, []);
        grouped.get(l.file)!.push(l);
      }
      const report = [...grouped.entries()]
        .map(([file, ls]) => {
          const detail = ls.map((l) => `    line ${l.line} — ${l.pattern}: ${l.context}`).join('\n');
          return `  ${file}:\n${detail}`;
        })
        .join('\n');
      // Throw with actionable guidance.
      throw new Error(
        `Found ${leaks.length} NYC-leaking string(s) across ${grouped.size} file(s):\n${report}\n\n` +
        `Each line must either:\n` +
        `  (a) be removed / made city-agnostic;\n` +
        `  (b) be deployment-gated (e.g. {#if deployment.current?.name === 'nyc'});\n` +
        `  (c) carry a "// nyc-leak-ok: <reason>" comment on the line or directly above it;\n` +
        `  (d) have its file added to the EXEMPT_FILES list with a one-line justification.`,
      );
    }
    expect(leaks).toEqual([]);
  });
});

describe('NYC-leakage audit fixture sanity', () => {
  it('discovers .svelte files in components/ (positive control)', () => {
    const files = walk(COMPONENTS_DIR);
    expect(files.length).toBeGreaterThan(20);
  });

  it('the EXEMPT_FILES list only names files that actually exist', () => {
    const all = new Set(walk(COMPONENTS_DIR).map((f) => relative(COMPONENTS_DIR, f)));
    for (const exempt of EXEMPT_FILES) {
      expect(all,
        `EXEMPT_FILES references "${exempt}" which doesn't exist under components/`,
      ).toContain(exempt);
    }
  });
});
