"""Programmatic Mellea probe — hit the agent stream N times and dump
per-requirement pass/fail to a CSV so we can see which invariant keeps
failing and decide how to fix.

Requires the local server running on http://127.0.0.1:7860.

Usage:
    uv run python scripts/probe_mellea.py --query Hollis --runs 5
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from urllib.parse import quote

import httpx


def stream_one(query: str, base: str, timeout_s: float) -> dict:
    url = f"{base}/api/agent/stream?q={quote(query)}"
    t0 = time.time()
    final = None
    intent = None
    attempts = []  # list of {attempt, passed, failed} from mellea_attempt
    with httpx.stream("GET", url, timeout=timeout_s) as r:
        r.raise_for_status()
        ev = None
        buf = []
        for line in r.iter_lines():
            if line.startswith("event:"):
                ev = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                buf.append(line[5:].lstrip())
            elif line == "":
                if ev and buf:
                    data = "\n".join(buf)
                    buf = []
                    if ev == "plan":
                        try:
                            intent = json.loads(data).get("intent")
                        except json.JSONDecodeError:
                            pass
                    elif ev == "mellea_attempt":
                        try:
                            attempts.append(json.loads(data))
                        except json.JSONDecodeError:
                            pass
                    elif ev == "final":
                        try:
                            final = json.loads(data)
                        except json.JSONDecodeError:
                            final = {"_raw": data}
                ev = None
    dt = round(time.time() - t0, 2)
    return {"final": final or {}, "elapsed_s": dt, "intent": intent,
            "attempts": attempts}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--base", default="http://127.0.0.1:7860")
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--out", default="outputs/mellea_probe.csv")
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for i in range(args.runs):
        try:
            r = stream_one(args.query, args.base, args.timeout)
        except Exception as e:
            print(f"[{i+1}/{args.runs}] ERROR: {e!r}")
            continue
        f = r["final"]
        m = f.get("mellea") or {}
        passed = m.get("requirements_passed", [])
        failed = m.get("requirements_failed", [])
        para = f.get("paragraph", "")
        row = {
            "run": i + 1,
            "intent": r.get("intent"),
            "elapsed_s": r["elapsed_s"],
            "rerolls": m.get("rerolls"),
            "n_attempts": m.get("n_attempts"),
            "passed_count": len(passed),
            "failed_count": len(failed),
            "failed": ",".join(failed),
            "passed": ",".join(passed),
            "para_chars": len(para),
            "paragraph": para.replace("\n", " "),
        }
        # Add per-attempt detail.
        for a in r.get("attempts", []):
            row[f"attempt{a.get('attempt')}_failed"] = ",".join(a.get("failed", []))
        rows.append(row)
        atts = r.get("attempts", [])
        att_summary = " | ".join(
            f"#{a.get('attempt')}={'✓' if not a.get('failed') else 'fail:'+','.join(a.get('failed', []))}"
            for a in atts
        ) or "no attempts"
        print(f"[{i+1}/{args.runs}] {r['elapsed_s']:6.1f}s  final={len(passed)}/4  attempts: {att_summary}")

    if rows:
        with out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nWrote {out}")
        print("Pass-rate distribution: " +
              json.dumps({n: sum(1 for r in rows if r['passed_count'] == n)
                          for n in range(5)}))
        # Show the failed paragraphs for inspection.
        for r in rows:
            if r['failed_count']:
                print(f"\n--- run {r['run']} failed [{r['failed']}] ---")
                print(r['paragraph'][:600])


if __name__ == "__main__":
    main()
