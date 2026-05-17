// Concurrent /api/agent stress test.
//
// This is the LLM-bound path — each request runs the full briefing
// pipeline (intake → 4 stones → mellea reconcile). The Granite call
// dominates wall time (~30 s per briefing on Ollama). The pebble
// fan-out is already parallel within one request; this test measures
// how many concurrent requests we can serve before reconcile-queue
// blowback makes p95 unacceptable.
//
// Run:
//   k6 run load/k6/agent_concurrency.js
//
// What "good" looks like (single Ollama, M3, granite4.1:8b-q3):
//   VU=1     p95 ~90 s   (baseline single-user)
//   VU=2     p95 ~150 s  (reconcile starts queueing)
//   VU=5     p95 ~300+s  (clear degradation)
//
// The output graph (p50/p90/p95 vs concurrent VUs) tells us where
// the curve bends — that's the moment to pull the trigger on
// remote-vLLM batching or a briefing cache.
import http from 'k6/http';
import { check } from 'k6';
import { Trend } from 'k6/metrics';

const BASE = __ENV.BASE || 'http://127.0.0.1:8765';

// Five curated NYC addresses — picked so each VU hits a different
// geo cache line, exercising both Sandy-positive and -negative.
const ADDRESSES = [
  '442 East Houston Street, Manhattan',
  '80 Pioneer Street, Brooklyn',
  '100 Gold Street, Manhattan',
  '189 Atlantic Avenue, Brooklyn',
  'Coney Island, Brooklyn',
];

// Custom trend so the per-request wall time is easy to plot.
const agentWall = new Trend('agent_wall_seconds', false);

export const options = {
  scenarios: {
    concurrent_briefings: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '2m', target: 1 },   // baseline (single user)
        { duration: '2m', target: 2 },   // bumping to 2 concurrent
        { duration: '3m', target: 5 },   // stress
        { duration: '1m', target: 0 },
      ],
      gracefulRampDown: '30s',
    },
  },
  thresholds: {
    // p95 ceilings — fail the run if briefings get unbearably slow.
    'agent_wall_seconds{vus:1}':  ['p(95)<150'],
    'agent_wall_seconds{vus:5}':  ['p(95)<600'],
    'http_req_failed':            ['rate<0.05'],
  },
};

export default function () {
  const addr = ADDRESSES[__VU % ADDRESSES.length];
  const url = `${BASE}/api/agent?q=${encodeURIComponent(addr)}`;
  const t0 = Date.now();
  const r = http.get(url, { timeout: '600s' });
  const elapsed = (Date.now() - t0) / 1000;
  agentWall.add(elapsed);
  check(r, {
    '200': (x) => x.status === 200,
    'has paragraph': (x) => {
      try {
        const j = JSON.parse(x.body);
        return (j.paragraph || '').length > 100;
      } catch {
        return false;
      }
    },
  });
}
