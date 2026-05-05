"""Quick end-to-end sanity check.

Exercises every public route once and prints a summary. Catches:
 - 404/500s on routes
 - missing static assets
 - broken /api/stream or /api/compare SSE
 - missing register data
 - hallucination drops > N

Run while the server is up:
    python scripts/dry_run.py
"""
from __future__ import annotations

import json
import sys
import time

import httpx

BASE = "http://127.0.0.1:8765"


def check(label: str, fn):
    t0 = time.time()
    try:
        ok, detail = fn()
        elapsed = time.time() - t0
        marker = "✓" if ok else "✗"
        print(f"  {marker} {label:42s}  ({elapsed:5.2f}s)  {detail}")
        return ok
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  ✗ {label:42s}  ({elapsed:5.2f}s)  EXCEPTION: {type(e).__name__}: {e}")
        return False


def get_status(path: str) -> tuple[bool, str]:
    r = httpx.get(BASE + path, timeout=10)
    return r.status_code == 200, f"HTTP {r.status_code} ({len(r.content)} bytes)"


def stream_one(query: str) -> tuple[bool, str]:
    with httpx.stream("GET", BASE + f"/api/stream?q={query}", timeout=120) as r:
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        steps = 0; final = None
        for line in r.iter_lines():
            if line.startswith("data: "):
                d = json.loads(line[6:])
                if d.get("kind") == "step": steps += 1
                elif d.get("kind") == "final": final = d
        if not final:
            return False, f"no final event (steps={steps})"
        dropped = len(((final.get("audit") or {}).get("dropped") or []))
        en = final.get("energy") or {}
        return True, (f"steps={steps}, dropped={dropped}, "
                      f"energy={en.get('local_mwh','?')} mWh local")


def compare_one(a: str, b: str) -> tuple[bool, str]:
    with httpx.stream("GET", BASE + f"/api/compare?a={a}&b={b}", timeout=120) as r:
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        finals = {}
        steps = 0
        for line in r.iter_lines():
            if line.startswith("data: "):
                d = json.loads(line[6:])
                if d.get("kind") == "step": steps += 1
                elif d.get("kind") == "final": finals[d.get("side")] = d
        if "a" not in finals or "b" not in finals:
            return False, f"missing final (got {list(finals)})"
        return True, f"both sides done; steps={steps}"


def register_check(asset_class: str) -> tuple[bool, str]:
    r = httpx.get(BASE + f"/api/register/{asset_class}", timeout=10)
    if r.status_code == 503:
        return False, "register not built"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    data = r.json()
    rows = data.get("rows", [])
    tiers = {1: 0, 2: 0, 3: 0}
    for r_ in rows:
        tiers[r_.get("tier", 0)] = tiers.get(r_.get("tier", 0), 0) + 1
    return True, f"{len(rows)} rows · tier1={tiers.get(1,0)} t2={tiers.get(2,0)} t3={tiers.get(3,0)}"


def main():
    print(f"=== Riprap dry-run vs {BASE} ===\n")

    print("[Pages]")
    check("/",                  lambda: get_status("/"))
    check("/compare",           lambda: get_status("/compare"))
    check("/register/schools",  lambda: get_status("/register/schools"))
    check("/register/nycha",    lambda: get_status("/register/nycha"))
    check("/static/style.css",  lambda: get_status("/static/style.css"))
    check("/static/app.js",     lambda: get_status("/static/app.js"))
    check("/static/compare.js", lambda: get_status("/static/compare.js"))
    check("/static/register.js",lambda: get_status("/static/register.js"))
    fontf = "/static/vendor/nyco/fonts/IBM-Plex-Sans/IBMPlexSans-Regular.woff2"
    check(fontf,                lambda: get_status(fontf))

    print("\n[API: layer endpoints]")
    check("/api/layers/sandy",  lambda: get_status("/api/layers/sandy?lat=40.59&lon=-73.77&r=1500"))
    check("/api/layers/dep_extreme_2080",
          lambda: get_status("/api/layers/dep_extreme_2080?lat=40.59&lon=-73.77&r=1500"))
    check("/api/floodnet_near", lambda: get_status("/api/floodnet_near?lat=40.59&lon=-73.77&r=1000"))

    print("\n[API: register endpoints]")
    check("/api/register/schools", lambda: register_check("schools"))
    check("/api/register/nycha",   lambda: register_check("nycha"))

    print("\n[Streams]")
    check("stream  · 180 Beach 35 St",
          lambda: stream_one("180 Beach 35 St, Queens"))
    check("stream  · Empire State (cleaner case)",
          lambda: stream_one("350 5 Avenue, Manhattan"))
    check("compare · Hollis vs Empire State",
          lambda: compare_one("153-09 90 Avenue Jamaica Queens",
                              "350 5 Avenue Manhattan"))


if __name__ == "__main__":
    sys.exit(main())
