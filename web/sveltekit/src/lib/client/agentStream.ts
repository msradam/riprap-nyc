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
  /** Per-call emissions ledger from app/emissions.py. Optional —
   *  older backends + the not_implemented short-circuit may omit it. */
  emissions?: EmissionsSummary;
}

export interface EmissionsCall {
  kind: 'llm' | 'ml';
  model?: string;
  endpoint?: string;
  backend: string;
  hardware: string;
  hardware_label: string;
  /** Power figure used for this row's energy. When measured=true this is
   *  the NVML-derived avg watts; otherwise it's the data-sheet fallback. */
  power_w: number;
  duration_s: number;
  /** True when joules came from a real NVML read on the inference proxy
   *  (X-GPU-Energy-J header for ML / bracket-sampled /v1/power for LLM).
   *  False = data-sheet × duration estimate. */
  measured: boolean;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  stream?: boolean;
  wh: number;
  joules: number;
}

export interface EmissionsSummary {
  n_calls: number;
  /** Number of calls whose joules came from a real GPU power read. */
  n_measured: number;
  total_wh: number;
  total_mwh: number;
  total_joules: number;
  total_duration_s: number;
  tokens: {
    prompt?: number | null;
    completion?: number | null;
    total?: number | null;
  };
  by_kind: Record<string, { wh: number; mwh: number; n: number; duration_s: number }>;
  by_hardware: Record<string, {
    label: string; wh: number; mwh: number; n: number; duration_s: number;
  }>;
  calls: EmissionsCall[];
  method: string;
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
  /** Fired after the backend resolves the deployment for this query
   *  (post-geocode). `name` is the deployment directory name (e.g.
   *  `boston`) or null when out-of-coverage. Used by /q/[queryId] to
   *  swap the header chip + reload the pebble scaffold so the UI
   *  renders the routed-to city, not the server's boot deployment. */
  onDeployment?: (d: { name: string | null; city?: string | null; state?: string | null }) => void;
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
  on<{ name: string | null; city?: string | null; state?: string | null }>(
    'deployment', (d) => handlers.onDeployment?.(d));
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
