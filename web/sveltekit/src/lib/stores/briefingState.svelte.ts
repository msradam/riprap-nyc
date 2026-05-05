/**
 * Cross-component "briefing is done" signal + snapshot for export-PDF.
 *
 * `ready` flips true only after the streaming pipeline has produced a
 * grounded briefing (or the prerendered /q/sample mounts). The header's
 * "export PDF" button keys off this — premature print of a half-streamed
 * briefing is bad UX.
 *
 * `persistSnapshot` stashes the curated payload in localStorage under
 * `riprap:print:<queryId>` so the dedicated print tab (opened with
 * `window.open`) can hydrate from it without re-running the pipeline.
 */
import type { BriefingBlock, Citation } from '$lib/types/claim';

export interface PrintSnapshot {
  queryId: string;
  queryText: string;
  intent: string | null;
  specialists: number;
  blocks: BriefingBlock[];
  citations: Record<string, Citation>;
  generatedAt: string;
  attempts: number | null;
}

class BriefingState {
  ready = $state(false);

  reset() {
    this.ready = false;
  }

  markReady() {
    this.ready = true;
  }
}

export const briefingState = new BriefingState();

const STORAGE_PREFIX = 'riprap:print:';

export function snapshotKey(queryId: string): string {
  return STORAGE_PREFIX + queryId;
}

export function persistSnapshot(snap: PrintSnapshot): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(snapshotKey(snap.queryId), JSON.stringify(snap));
  } catch {
    /* quota / private mode — print tab will fall back to "no snapshot" */
  }
}

export function loadSnapshot(queryId: string): PrintSnapshot | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(snapshotKey(queryId));
    return raw ? (JSON.parse(raw) as PrintSnapshot) : null;
  } catch {
    return null;
  }
}
