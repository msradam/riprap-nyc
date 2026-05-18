/**
 * MockEventSource — a deterministic stand-in for the global
 * EventSource that the agentStream client uses. Tests can:
 *
 *   - install it via installMockEventSource() in beforeEach
 *   - retrieve the active instance via getMockEventSource()
 *   - drive a scripted sequence of SSE events via .emit(name, data)
 *
 * Used by the page-level integration test that mounts /q/[queryId]
 * with a scripted backend, asserts the UI pivots correctly through
 * the lifecycle (deployment event swaps chip + scaffold, final
 * event renders the briefing, done event hides the status pill).
 */
import { vi } from 'vitest';

export class MockEventSource {
  url: string;
  readyState = 1;
  withCredentials = false;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  onopen: ((e: Event) => void) | null = null;
  private listeners = new Map<string, Set<(e: MessageEvent) => void>>();
  closed = false;

  constructor(url: string) {
    this.url = url;
  }

  addEventListener(name: string, fn: (e: MessageEvent) => void): void {
    if (!this.listeners.has(name)) this.listeners.set(name, new Set());
    this.listeners.get(name)!.add(fn);
  }

  removeEventListener(name: string, fn: (e: MessageEvent) => void): void {
    this.listeners.get(name)?.delete(fn);
  }

  close(): void {
    this.closed = true;
    this.readyState = 2;
  }

  /** Test helper: fire a named SSE event with JSON payload. */
  emit(name: string, data: unknown = {}): void {
    if (this.closed) return;
    const event = new MessageEvent(name, {
      data: typeof data === 'string' ? data : JSON.stringify(data),
    });
    this.listeners.get(name)?.forEach((fn) => fn(event));
  }
}

let CURRENT: MockEventSource | null = null;

/** Install the mock — replaces global.EventSource until uninstalled. */
export function installMockEventSource(): void {
  CURRENT = null;
  (globalThis as unknown as { EventSource: typeof MockEventSource }).EventSource =
    class extends MockEventSource {
      constructor(url: string) {
        super(url);
        CURRENT = this;
      }
    } as unknown as typeof MockEventSource;
}

/** Return the most-recent MockEventSource instance the SUT constructed. */
export function getMockEventSource(): MockEventSource {
  if (!CURRENT) {
    throw new Error(
      'No EventSource instance — did the SUT call new EventSource(url)? ' +
      'Make sure installMockEventSource() is invoked in beforeEach.',
    );
  }
  return CURRENT;
}

/** Convenience: drive a clean Boston run through the SSE handshake. */
export async function scriptBostonRun(es: MockEventSource): Promise<void> {
  await scriptCityRun(es, {
    name: 'boston', city: 'Boston', state: 'MA',
    address: 'Boston City Hall',
    lat: 42.36, lon: -71.06,
    pebbles: ['nws_obs', 'water_level', 'boston_311'],
    paragraph: 'Boston templated paragraph.',
  });
}

/** Drive any city through the SSE handshake. */
export async function scriptCityRun(
  es: MockEventSource,
  spec: {
    name: string | null; city: string | null; state: string | null;
    address: string; lat: number; lon: number;
    pebbles: string[]; paragraph: string;
  },
): Promise<void> {
  es.emit('hello', { query: spec.address });
  es.emit('plan', {
    intent: 'single_address',
    targets: [{ type: 'address', text: spec.address }],
    specialists: spec.pebbles, rationale: '',
  });
  es.emit('step', {
    kind: 'step', step: 'geocode', ok: true, elapsed_s: 0.2,
    result: { address: spec.address, lat: spec.lat, lon: spec.lon },
  });
  es.emit('deployment', {
    name: spec.name ?? '__none__',
    city: spec.city, state: spec.state,
  });
  for (const pid of spec.pebbles) {
    es.emit('step', { kind: 'step', step: pid, ok: true });
  }
  es.emit('final', {
    paragraph: spec.paragraph,
    intent: 'single_address',
    mellea: { passed: [], failed: [], attempts: 0 },
    citations: [],
  });
  es.emit('done', {});
}
