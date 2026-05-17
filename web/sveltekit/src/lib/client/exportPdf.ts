/**
 * Export a completed briefing as PDF via the server-side `/api/print`
 * route.
 *
 * Flow:
 *   1. Read the cached PrintSnapshot from localStorage (written by the
 *      streaming pipeline when the briefing settles).
 *   2. Transform it into the JSON shape app/print_pdf.py expects.
 *   3. POST to /api/print, get back PDF bytes.
 *   4. Open the PDF in a new tab via a blob URL.
 *
 * Replaces the previous "open /print/<queryId> in a new tab and let the
 * browser print dialog do its thing" pattern. The server-rendered PDF
 * carries a SHA-256 document hash and full Civic Hydrology typesetting
 * that the print stylesheet couldn't match.
 */

import { loadSnapshot, type PrintSnapshot } from '$lib/stores/briefingState.svelte';
import type { Citation, BriefingBlock, ClaimPart } from '$lib/types/claim';

/** Reconstruct the briefing prose from the snapshot's blocks.
 *  Cited spans get [N] markers inline so they map to the citations
 *  list on the PDF.
 */
function reconstructParagraph(blocks: BriefingBlock[], cites: Record<string, Citation>): string {
  const out: string[] = [];
  for (const b of blocks) {
    if (b.kind === 'status') {
      // Strip HTML tags — status copy is the planner intent line, not
      // load-bearing for the PDF body.
      out.push(b.html.replace(/<[^>]+>/g, '').trim());
    } else if (b.kind === 'head') {
      out.push(`\n\n${b.n}. ${b.label}\n`);
    } else if (b.kind === 'prose') {
      const seg = b.parts
        .map((p: ClaimPart) => {
          const marker = p.cite ? ` [${cites[p.cite]?.n ?? '?'}]` : '';
          return `${p.text}${marker}`;
        })
        .join('');
      out.push(seg);
    }
  }
  return out.join('\n').trim();
}

/** Convert PrintSnapshot → /api/print POST body shape. */
function snapshotToPrintPayload(snap: PrintSnapshot): Record<string, unknown> {
  const citations = Object.values(snap.citations)
    .sort((a, b) => a.n - b.n)
    .map((c) => ({
      doc_id: c.docId,
      source: c.source,
      title: c.title,
      url: c.url,
      vintage: c.vintage,
    }));
  return {
    query: snap.queryText,
    paragraph: reconstructParagraph(snap.blocks, snap.citations),
    plan: { intent: snap.intent ?? 'single_address' },
    citations,
    mellea: {
      attempts: snap.attempts ?? 1,
      passed: [],
      failed: [],
    },
    // emissions optional — the briefingState snapshot doesn't carry it
    // today; the route will simply skip the energy ledger section.
  };
}

export class ExportPdfError extends Error {
  constructor(message: string, public readonly status?: number) { super(message); }
}

/** Trigger a PDF export for the active briefing. Opens the result in
 *  a new browser tab. Throws ExportPdfError on snapshot-missing / API
 *  / network failures so the caller can surface a toast.
 */
export async function exportBriefingPdf(queryId: string): Promise<void> {
  const snap = loadSnapshot(queryId);
  if (!snap) {
    throw new ExportPdfError(
      'Briefing snapshot not found. Wait for the briefing to finish before exporting.',
    );
  }
  const payload = snapshotToPrintPayload(snap);

  const r = await fetch('/api/print', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try {
      const j = await r.json();
      if (j?.detail) detail = j.detail;
      else if (j?.error) detail = j.error;
    } catch { /* non-JSON error body */ }
    throw new ExportPdfError(`PDF render failed — ${detail}`, r.status);
  }

  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const win = window.open(url, '_blank', 'noopener');
  // Release the URL after the new tab has a chance to grab it. Some
  // browsers revoke too eagerly otherwise.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
  if (!win) {
    // Popup-blocked. Fall back to a direct same-tab download via <a>.
    const a = document.createElement('a');
    a.href = url;
    a.download = `riprap-briefing.pdf`;
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
  }
}
