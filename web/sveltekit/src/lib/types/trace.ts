import type { Tier } from './tier';

export type TraceStatus = 'ok' | 'silent' | 'error' | 'fan' | 'merge';

export interface TraceNode {
  id: string;
  name: string;
  status: TraceStatus;
  ms: number;
  tier: Tier | null;
  note?: string;
  /** Raw structured payload from the specialist — full object preserved
   *  so the trace UI can render it on click as the auditable evidence
   *  surface. Strings are rendered inline; objects as formatted JSON. */
  output?: string | object | null;
  /** When status === 'error', the error message string. */
  error?: string;
  /** Doc id this specialist contributed (when known). Surfaced in the
   *  expanded panel so a judge can cross-reference to a citation chip. */
  docId?: string;
  /** Foundation model that produced this specialist's output. Used by
   *  the trace renderer to group co-model specialists under a parent. */
  model?: string;
  claims?: number;
  children?: TraceNode[];
}
