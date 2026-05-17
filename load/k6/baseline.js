// Baseline throughput test for Riprap's light read endpoints.
//
// These are the endpoints the SvelteKit frontend hits on every page
// load — they need to stay fast under concurrent users while the heavy
// Burr pipeline does its thing in the background.
//
// Targets:
//   /api/pebbles          — manifest catalog (cached in-memory at startup)
//   /api/backend          — LLM backend descriptor (does a reachability ping)
//   /                     — SvelteKit landing page (static)
//   /api/layers/sandy?... — geo layer clip for the map (per-coord, cached)
//
// Run:
//   k6 run load/k6/baseline.js                 # default scenario
//   k6 run -e BASE=http://other.host load/k6/baseline.js
//
// What "good" looks like (single-worker Granian, M3 laptop):
//   /api/pebbles  p95 < 5 ms,    >5000 RPS
//   /            p95 < 10 ms,   >1000 RPS
//   /api/layers   p95 < 200 ms,  >50  RPS
import http from 'k6/http';
import { check, group, sleep } from 'k6';

const BASE = __ENV.BASE || 'http://127.0.0.1:8765';

// Two NYC test coords for the layer endpoint.
const COORDS = [
  { lat: 40.7100, lon: -73.9800 }, // Lower East Side
  { lat: 40.6810, lon: -74.0090 }, // Red Hook
];

export const options = {
  scenarios: {
    // Ramp from 1 → 20 VUs over 1 min, hold 20 for 1 min, ramp down.
    ramp: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '1m',  target: 20 },
        { duration: '1m',  target: 20 },
        { duration: '15s', target: 0  },
      ],
    },
  },
  thresholds: {
    'http_req_duration{name:pebbles}':  ['p(95)<50'],     // ms
    'http_req_duration{name:backend}':  ['p(95)<100'],
    'http_req_duration{name:landing}':  ['p(95)<100'],
    'http_req_duration{name:layer}':    ['p(95)<500'],
    'http_req_failed':                  ['rate<0.01'],     // <1% errors
  },
};

export default function () {
  group('catalog', () => {
    const r = http.get(`${BASE}/api/pebbles`, { tags: { name: 'pebbles' } });
    check(r, { '200': (x) => x.status === 200 });
  });

  group('backend', () => {
    const r = http.get(`${BASE}/api/backend`, { tags: { name: 'backend' } });
    check(r, { '200': (x) => x.status === 200 });
  });

  group('landing', () => {
    const r = http.get(`${BASE}/`, { tags: { name: 'landing' } });
    check(r, { '200': (x) => x.status === 200 });
  });

  group('layer', () => {
    const c = COORDS[Math.floor(Math.random() * COORDS.length)];
    const r = http.get(
      `${BASE}/api/layers/sandy?lat=${c.lat}&lon=${c.lon}`,
      { tags: { name: 'layer' } },
    );
    check(r, { '200': (x) => x.status === 200 });
  });

  sleep(0.1);
}
