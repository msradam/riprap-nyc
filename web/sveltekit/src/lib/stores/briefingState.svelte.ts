/**
 * Cross-component "briefing is done" signal + snapshot for export-PDF.
 *
 * `ready` flips true only after the streaming pipeline has produced a
 * grounded briefing. The header's "export PDF" button keys off this —
 * premature print of a half-streamed briefing is bad UX.
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

/** Coarse pipeline phase, surfaced in the AppHeader status indicator
 *  so a user staring at a half-rendered page knows what's happening.
 *  Phases are picked from the SSE event stream in /q/[queryId]/+page.svelte. */
export type RunPhase =
  | 'idle'
  | 'planning'      // planner JSON is streaming
  | 'specialists'   // FSM is firing data Stones (cornerstone → lodestone)
  | 'reconciling'   // Granite + Mellea is composing the briefing
  | 'streaming'     // first reconcile token has arrived; paragraph is materialising
  | 'done'
  | 'error';

class BriefingState {
  ready = $state(false);

  /** Live phase indicator. AppHeader reads these to render the status
   *  pill. /q/[queryId]/+page.svelte is the canonical writer.
   */
  phase = $state<RunPhase>('idle');
  /** The most recent step name the FSM emitted — e.g. `floodnet`,
   *  `terramind_lulc`. Pretty-printed by AppHeader via STEP_LABELS. */
  activeStep = $state<string | null>(null);
  /** How many specialists have fired (any non-error status) so far. */
  firedCount = $state(0);
  /** Total specialists registered for this run. Set when the planner
   *  resolves an intent or when the FSM trace settles. */
  totalSpecialists = $state(0);
  /** Mellea attempt counter (1-indexed once tokens start streaming). */
  attempt = $state(0);
  /** Last error message — shown in the header status when phase = error. */
  errorMessage = $state<string | null>(null);

  reset() {
    this.ready = false;
    this.phase = 'idle';
    this.activeStep = null;
    this.firedCount = 0;
    this.totalSpecialists = 0;
    this.attempt = 0;
    this.errorMessage = null;
  }

  markReady() {
    this.ready = true;
    this.phase = 'done';
    this.activeStep = null;
  }

  markError(msg: string) {
    this.phase = 'error';
    this.errorMessage = msg;
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
