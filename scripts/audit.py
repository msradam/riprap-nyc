"""Hallucination audit harness.

Runs the FSM against a curated address sweep, logs every paragraph,
counts dropped sentences, flags any sentence with an event name not in
its source documents.

Run after the schools register has finished building (otherwise it
contends with the batch for Ollama).

    python scripts/audit.py
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.fsm import run  # noqa: E402

OUT = ROOT / "outputs" / "audit_log.jsonl"
OUT.parent.mkdir(exist_ok=True, parents=True)

# A curated cross-borough sweep covering the full range of conditions
ADDRESSES = [
    # Far Rockaway / Sandy zone (everything fires)
    "180 Beach 35 St, Queens",
    "Beach 105 Street and Rockaway Boulevard, Queens",

    # Hollis / Jamaica (Ida basement deaths)
    "153-09 90 Avenue, Jamaica, Queens",
    "Hollis Avenue and 200th Street, Queens",

    # Brooklyn coastal — Coney Island / NYCHA
    "2950 W 25 Street, Brooklyn",
    "Surf Avenue and West 25 Street, Brooklyn",
    "Sheepshead Bay Road, Brooklyn",

    # Carroll Gardens / Gowanus (chronic flooding)
    "Smith and 9 Street, Brooklyn",
    "Carroll Street and 3 Avenue, Brooklyn",

    # Lower Manhattan / Sandy zone
    "280 Broome Street, Manhattan",
    "South Street Seaport, Manhattan",
    "Battery Park, Manhattan",

    # Midtown / dry control
    "350 5 Avenue, Manhattan",          # Empire State
    "1 Times Square, Manhattan",
    "Lincoln Center, Manhattan",

    # Bronx
    "Pelham Bay Park, Bronx",
    "Hunts Point, Bronx",
    "Yankee Stadium, Bronx",

    # Staten Island
    "Tottenville, Staten Island",
    "Great Kills, Staten Island",
    "St. George Ferry Terminal, Staten Island",

    # Queens dry / inland
    "Forest Hills, Queens",
    "JFK Airport, Queens",
    "Astoria Park, Queens",

    # Edge cases
    "Brooklyn Bridge Park, Brooklyn",
    "Roosevelt Island, Manhattan",
]

EVENT_NAMES = ["sandy", "ida", "ophelia", "henri", "irene", "isaias",
               "harvey", "katrina", "florence"]


def find_event_leaks(paragraph: str, doc_corpus: str) -> list[str]:
    leaks = []
    p = paragraph.lower()
    for ev in EVENT_NAMES:
        if ev in p and ev not in doc_corpus.lower():
            leaks.append(ev)
    return leaks


def main() -> int:  # TODO(cleanup): cc-grade-D (24)
    if OUT.exists():
        OUT.unlink()
    print(f"running audit on {len(ADDRESSES)} addresses; logging to {OUT}",
          file=sys.stderr)

    summary = {
        "total": 0, "ok": 0, "dropped_total": 0,
        "with_drops": 0, "event_leaks": 0,
    }
    t0 = time.time()
    for q in ADDRESSES:
        try:
            r = run(q)
        except Exception as e:
            print(f"  ! {q[:50]:<50} ERR: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        para = r.get("paragraph") or ""
        audit = r.get("audit") or {}
        dropped = audit.get("dropped", []) or []

        # rebuild a haystack from documents we sent to Granite
        from app.reconcile import build_documents
        # NOTE: build_documents needs the same snap shape the FSM stored
        snap = {k: r.get(k) for k in ("geocode","sandy","dep","floodnet",
                                       "nyc311","microtopo","ida_hwm","rag")}
        doc_msgs = build_documents(snap)
        haystack = "\n".join(m.get("content", "") for m in doc_msgs)

        leaks = find_event_leaks(para, haystack)

        rec = {
            "query": q,
            "address": (r.get("geocode") or {}).get("address"),
            "borough": (r.get("geocode") or {}).get("borough"),
            "paragraph": para,
            "raw": audit.get("raw"),
            "dropped": dropped,
            "event_leaks": leaks,
            "sandy": r.get("sandy"),
            "n_floodnet_events_3y": (r.get("floodnet") or {}).get("n_flood_events_3y", 0),
            "n_311": (r.get("nyc311") or {}).get("n", 0),
            "microtopo_pct_200m": (r.get("microtopo") or {}).get("rel_elev_pct_200m"),
        }
        with OUT.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")

        summary["total"] += 1
        summary["dropped_total"] += len(dropped)
        if dropped: summary["with_drops"] += 1
        if leaks:   summary["event_leaks"] += 1
        if not leaks and not dropped: summary["ok"] += 1

        marker = "✓" if (not leaks and not dropped) else ("⚠" if dropped or leaks else "·")
        print(f"  {marker} {q[:50]:<50} dropped={len(dropped)}  leaks={leaks or '-'}",
              file=sys.stderr)

    elapsed = time.time() - t0
    print(f"\n=== SUMMARY (in {elapsed:.0f}s) ===", file=sys.stderr)
    for k, v in summary.items():
        print(f"  {k:18s} {v}", file=sys.stderr)
    print(f"\nfull log: {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
