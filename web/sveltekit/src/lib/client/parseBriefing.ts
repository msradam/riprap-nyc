/**
 * Parse the streaming markdown produced by the Granite reconciler into the
 * four-section briefing IA the design system expects.
 *
 * The reconciler's prompt (app/reconcile.py:EXTRA_SYSTEM_PROMPT) enforces
 * **bold-stop** section heads, one per line:
 *   **Status.**
 *   **Empirical evidence.**
 *   **Modeled scenarios.**
 *   **Policy context.**
 * The model occasionally drops them inline; the backend's
 * _split_inline_headers normaliser fixes that before yielding final text,
 * but mid-stream we still tolerate inline forms ourselves.
 *
 * Within a section, every sentence with a `[doc_id]` citation is a Claim.
 * The claim's tier is inferred from the cited doc_id family via
 * tierForDocId(). Multiple cites on one sentence: the tier of the first
 * cited doc wins (visual margin glyph), all cites still rendered.
 */
import type { BriefingBlock, Citation, ClaimPart } from '$lib/types/claim';
import { tierForDocId, type Tier } from '$lib/types/tier';

const CANONICAL_SECTIONS: Array<{ key: string; label: string; n: string; tier?: Tier; aliases: string[] }> = [
  { key: 'status', label: 'Status', n: '01', aliases: ['status'] },
  { key: 'empirical', label: 'Empirical evidence', n: '02', tier: 'empirical', aliases: ['empirical evidence', 'empirical'] },
  { key: 'modeled', label: 'Modeled scenarios', n: '03', tier: 'modeled', aliases: ['modeled scenarios', 'modeled'] },
  { key: 'policy', label: 'Policy context', n: '04', aliases: ['policy context', 'policy'] }
];

function findSection(rawTitle: string) {
  const t = rawTitle.toLowerCase().replace(/[.:]+\s*$/, '').trim();
  return CANONICAL_SECTIONS.find((s) => s.aliases.includes(t));
}

// Match either `**Heading.**` (the canonical reconciler output) or the
// markdown-headed `## 01 Heading` form we use in the static demo data.
const SECTION_HEAD_RE = /(^|\n)\s*(?:\*\*([A-Z][A-Za-z\s/]+?)\.\s*\*\*|#{1,3}\s*(0[1-4])\s*[:\-—.]?\s*([^\n]+))/g;

export interface ParseResult {
  blocks: BriefingBlock[];
  citations: Record<string, Citation>;
  /** Doc IDs cited in the body but not in the provided citation registry. */
  unresolvedDocIds: string[];
}

/**
 * Build a Citation record from a doc_id and any backend-supplied metadata.
 * The reconciler has the registry; we keep this conservative so unknown
 * doc IDs still render with sensible defaults.
 */
export function citationFromMeta(
  n: number,
  docId: string,
  meta?: Partial<Pick<Citation, 'source' | 'title' | 'url' | 'vintage' | 'retrieved'>>
): Citation {
  // Most live-API pebbles don't have a baked `last_updated` date in
  // their manifest because the data IS live — the timestamp is the
  // moment of fetch. When vintage is null/blank, fall back to "live"
  // so the citation chip reads "v. live" instead of "v." (which
  // looked like a parse error in the user's screenshots).
  // Default the retrieved-at timestamp to the current ISO date so
  // citation chips always tell the reader WHEN we pulled this.
  const today = new Date().toISOString().slice(0, 10);
  return {
    id: docId,
    n,
    tier: tierForDocId(docId),
    source: meta?.source ?? docId.split(/[_-]/)[0].toUpperCase(),
    title: meta?.title ?? docId,
    docId,
    url: meta?.url ?? '',
    vintage: meta?.vintage || 'live',
    retrieved: meta?.retrieved || today,
  };
}

const CITE_RE = /\[([a-z][a-z0-9_]*(?:\s*,\s*[a-z][a-z0-9_]*)*)\]/gi;

function splitSentences(text: string): string[] {
  const parts = text.split(/(?<=[.!?])\s+(?=[A-Z(])/g);
  return parts.filter((s) => s.trim().length > 0);
}

function parseSentenceParts(
  sentence: string,
  cites: Record<string, Citation>,
  registerCite: (docId: string) => Citation
): ClaimPart[] {
  let cursor = 0;
  const parts: ClaimPart[] = [];
  let firstTier: Tier | undefined;
  const matches = [...sentence.matchAll(CITE_RE)];
  if (matches.length === 0) {
    return [{ text: sentence }];
  }
  for (const m of matches) {
    const before = sentence.slice(cursor, m.index ?? 0);
    const docIds = m[1].split(/\s*,\s*/).filter(Boolean);
    cursor = (m.index ?? 0) + m[0].length;

    const tier = tierForDocId(docIds[0]);
    if (!firstTier) firstTier = tier;

    parts.push({ text: before, tier, cite: docIds[0] });
    for (const id of docIds) {
      if (!cites[id]) cites[id] = registerCite(id);
    }
  }
  if (cursor < sentence.length) {
    const tail = sentence.slice(cursor);
    if (tail.trim()) parts.push({ text: tail });
  }
  return parts;
}

/**
 * Parse a fully-or-partially-streamed briefing markdown string into blocks.
 * Safe to call repeatedly during streaming — re-parses from scratch.
 */
export function parseBriefing(
  markdown: string,
  knownCitations: Record<string, Citation> = {}
): ParseResult {
  const cites: Record<string, Citation> = { ...knownCitations };
  let nextN = Object.values(cites).reduce((m, c) => Math.max(m, c.n), 0) + 1;
  const unresolvedDocIds = new Set<string>();
  const registerCite = (docId: string): Citation => {
    if (!knownCitations[docId]) unresolvedDocIds.add(docId);
    const c = citationFromMeta(nextN++, docId);
    return c;
  };

  const blocks: BriefingBlock[] = [];

  type Idx = { num: string; label: string; tier?: Tier; titleExtra?: string; start: number; bodyStart: number };
  const indices: Idx[] = [];
  let m: RegExpExecArray | null;
  SECTION_HEAD_RE.lastIndex = 0;
  while ((m = SECTION_HEAD_RE.exec(markdown))) {
    if (m[2] !== undefined) {
      // **Heading.** form
      const sec = findSection(m[2]);
      if (!sec) continue;
      indices.push({
        num: sec.n,
        label: sec.label,
        tier: sec.tier,
        start: m.index + m[1].length,
        bodyStart: m.index + m[0].length
      });
    } else if (m[3] !== undefined) {
      // ## 0n Heading form (used by the static demo)
      const num = m[3];
      const title = (m[4] ?? '').trim();
      const sec = CANONICAL_SECTIONS.find((s) => s.n === num) ?? findSection(title);
      indices.push({
        num,
        label: sec?.label ?? title,
        tier: sec?.tier,
        titleExtra: sec && title.toLowerCase() !== sec.label.toLowerCase() ? title : undefined,
        start: m.index + m[1].length,
        bodyStart: m.index + m[0].length
      });
    }
  }

  // Pre-section preamble. Don't render — the reconciler doesn't emit one and
  // we don't want a stray HTML escape of the bold-marker prefix to flash.
  for (let i = 0; i < indices.length; i++) {
    const sec = indices[i];
    const next = indices[i + 1];
    const body = markdown.slice(sec.bodyStart, next ? next.start : markdown.length).trim();
    if (!body) continue;

    blocks.push({
      kind: 'head',
      n: sec.num,
      label: sec.label,
      tier: sec.tier,
      title: sec.titleExtra
    });

    for (const para of body.split(/\n\s*\n/)) {
      const flat = para.replace(/\s+/g, ' ').trim();
      if (!flat) continue;

      const sentences = splitSentences(flat);
      const parts: ClaimPart[] = [];
      for (const s of sentences) {
        parts.push(...parseSentenceParts(s, cites, registerCite));
        parts.push({ text: ' ' });
      }
      while (parts.length && parts[parts.length - 1].text.trim() === '' && !parts[parts.length - 1].tier) {
        parts.pop();
      }
      if (parts.length) blocks.push({ kind: 'prose', parts });
    }
  }

  // Fallback: if the model hasn't emitted any recognised section head yet
  // (or won't — e.g. live_now intent), render the whole markdown as one
  // implicit "Status" block so the reader sees something during streaming.
  if (blocks.length === 0 && markdown.trim()) {
    blocks.push({ kind: 'head', n: '01', label: 'Status' });
    const flat = markdown.replace(/\s+/g, ' ').trim();
    const sentences = splitSentences(flat);
    const parts: ClaimPart[] = [];
    for (const s of sentences) {
      parts.push(...parseSentenceParts(s, cites, registerCite));
      parts.push({ text: ' ' });
    }
    while (parts.length && parts[parts.length - 1].text.trim() === '' && !parts[parts.length - 1].tier) {
      parts.pop();
    }
    if (parts.length) blocks.push({ kind: 'prose', parts });
  }

  return { blocks, citations: cites, unresolvedDocIds: [...unresolvedDocIds] };
}

/**
 * HTML escape — kept around because the v0.4.1 parser used it for the
 * status-preamble fallback path. The v0.4.2 parser drops the preamble
 * entirely (the reconciler doesn't emit one), so this is currently
 * dead-code documentation. If the preamble path comes back, wire it
 * here.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
