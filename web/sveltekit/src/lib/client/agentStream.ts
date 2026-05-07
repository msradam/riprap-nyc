/**
 * SSE client for the Riprap agent stream (`GET /api/agent/stream?q=…`).
 *
 * The FastAPI backend emits these events:
 *   hello            { query }
 *   plan_token       { delta }                             planner JSON, token-by-token
 *   plan             { intent, targets, specialists, ... } planner finished
 *   step             { step, ok, started_at, elapsed_s, result?, err? }
 *   token            { delta, attempt? }                   reconciler tokens (the briefing)
 *   mellea_attempt   { attempt, passed, failed }
 *   final            { paragraph, mellea, audit, tier, score, ... }
 *   error            { err }
 *   done             {}
 *
 * The handoff component contract talks about `token` (with section/claimId)
 * and `claim` boundary events. We don't ask the backend to emit those —
 * instead this client parses the streaming markdown into the four-section
 * Briefing structure, infers tier per claim from cited doc-id family
 * prefixes (see tierForDocId), and emits sentence-buffered chunks to a
 * subscriber for accessible aria-live updates.
 */
import type { Tier } from '$lib/types/tier';

export interface PlanInfo {
  intent: string;
  targets?: unknown;
  specialists?: string[];
  rationale?: string;
}

export interface StepEvent {
  step: string;
  ok: boolean;
  elapsed_s?: number;
  result?: unknown;
  err?: string;
  tier?: Tier | null;
  claims?: number;
  /** Present on compare-intent step events: "PLACE A" or "PLACE B". */
  target_label?: string;
}

export interface MelleaAttempt {
  attempt: number;
  passed: string[];
  failed: string[];
}

export interface FinalResult {
  paragraph: string;
  mellea?: { passed: string[]; failed: string[]; attempts: number };
  audit?: unknown;
  tier?: string;
  score?: number;
  citations?: Array<{ doc_id: string; source?: string; title?: string; url?: string; vintage?: string }>;
  /** Present when intent === "compare". */
  intent?: string;
  targets?: Array<{ label: string; address: string }>;
}

export interface AgentStreamHandlers {
  onHello?: (q: string) => void;
  onPlanToken?: (delta: string) => void;
  onPlan?: (plan: PlanInfo) => void;
  onStep?: (s: StepEvent) => void;
  /** Raw token, before sentence buffering. */
  onToken?: (delta: string, attempt: number | undefined) => void;
  /** Sentence-flushed chunk, safe for aria-live. */
  onSentence?: (sentence: string, attempt: number | undefined) => void;
  /** Fired when the reconciler restarts (a Mellea reroll wipes the buffer). */
  onAttemptStart?: (attempt: number) => void;
  onMelleaAttempt?: (m: MelleaAttempt) => void;
  onFinal?: (f: FinalResult) => void;
  onError?: (err: string) => void;
  onDone?: () => void;
}

export interface AgentStream {
  close(): void;
}

export function openAgentStream(query: string, handlers: AgentStreamHandlers): AgentStream {
  const url = `/api/agent/stream?q=${encodeURIComponent(query)}`;
  const es = new EventSource(url);

  let sentenceBuf = '';
  let currentAttempt: number | undefined;
  const SENT_END = /([.?!])(\s|$)/;

  function flushSentences(force = false) {
    let m: RegExpExecArray | null;
    while ((m = SENT_END.exec(sentenceBuf))) {
      const end = m.index + m[1].length + (m[2] ? m[2].length : 0);
      const sentence = sentenceBuf.slice(0, end).trim();
      sentenceBuf = sentenceBuf.slice(end);
      if (sentence) handlers.onSentence?.(sentence, currentAttempt);
    }
    if (force && sentenceBuf.trim()) {
      handlers.onSentence?.(sentenceBuf.trim(), currentAttempt);
      sentenceBuf = '';
    }
  }

  function on<T>(name: string, fn: (data: T) => void) {
    es.addEventListener(name, (e) => {
      try {
        fn(JSON.parse((e as MessageEvent).data) as T);
      } catch {
        /* ignore parse errors */
      }
    });
  }

  on<{ query: string }>('hello', (d) => handlers.onHello?.(d.query));
  on<{ delta: string }>('plan_token', (d) => handlers.onPlanToken?.(d.delta));
  on<PlanInfo>('plan', (d) => handlers.onPlan?.(d));
  on<StepEvent>('step', (d) => handlers.onStep?.(d));
  on<{ delta: string; attempt?: number }>('token', (d) => {
    if (d.attempt !== currentAttempt) {
      currentAttempt = d.attempt;
      sentenceBuf = '';
      handlers.onAttemptStart?.(d.attempt ?? 1);
    }
    handlers.onToken?.(d.delta, d.attempt);
    sentenceBuf += d.delta;
    flushSentences(false);
  });
  on<MelleaAttempt>('mellea_attempt', (d) => handlers.onMelleaAttempt?.(d));
  on<FinalResult>('final', (d) => {
    flushSentences(true);
    handlers.onFinal?.(d);
  });
  on<{ err: string }>('error', (d) => handlers.onError?.(d.err));
  es.addEventListener('done', () => {
    flushSentences(true);
    handlers.onDone?.();
    es.close();
  });
  es.addEventListener('error', () => {
    flushSentences(true);
    handlers.onError?.('SSE connection error');
    es.close();
  });

  return { close: () => es.close() };
}
