"""Riprap agent CLI — address → cited briefing via the Burr FSM.

Usage:
    python agent.py "180 Beach 35 St, Queens"
    python agent.py "280 Broome St, Manhattan"  --json
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings

warnings.filterwarnings("ignore")

from app.fsm import run  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="NYC address or natural-language location")
    ap.add_argument("--json", action="store_true", help="emit full JSON state")
    args = ap.parse_args()

    print(f"\n  query: {args.query}", file=sys.stderr)
    print("  running FSM... (Granite 4.1 + open data, all local)\n", file=sys.stderr)

    result = run(args.query)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0

    print("─── trace " + "─" * 56)
    for step in result["trace"]:
        ok = "✓" if step["ok"] else "✗"
        line = f"  {ok} {step['step']:22s} {step.get('elapsed_s', 0):>5.2f}s"
        if step.get("result"):
            line += "  " + json.dumps(step["result"], default=str)
        elif step.get("err"):
            line += "  ERR: " + step["err"]
        print(line)

    print("\n─── cited report " + "─" * 49)
    print()
    print(result["paragraph"])
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
