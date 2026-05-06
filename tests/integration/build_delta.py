"""Produce a before/after FRAMING-DELTA.md from two suite runs.

Usage:
    python tests/integration/build_delta.py \\
        --baseline tests/integration/results/2026-05-06 \\
        --framed tests/integration/results/2026-05-06-framed \\
        --out tests/integration/results/2026-05-06/FRAMING-DELTA.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_run(d: Path) -> dict[str, dict]:
    """Map qid -> per-query JSON payload."""
    out: dict[str, dict] = {}
    for p in sorted(d.glob("q*-*.json")):
        try:
            payload = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        qid = payload.get("qid") or p.stem.split("-", 1)[0].lstrip("q")
        out[qid] = payload
    return out


def opening_first_sentence(p: str) -> str:
    """Best-effort first non-header sentence of the briefing."""
    if not p:
        return "(no prose)"
    # Strip the **Status.** header line and take the first sentence body.
    lines = [line.strip() for line in p.splitlines() if line.strip()]
    body = []
    for line in lines:
        if line.startswith("**Status"):
            continue
        if line.startswith("**"):
            break
        body.append(line)
    text = " ".join(body)
    # First sentence
    for end in (". ", ".\n", ". **"):
        if end in text:
            return text.split(end, 1)[0].strip() + "."
    return text[:200]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--framed", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    base_dir = Path(args.baseline)
    framed_dir = Path(args.framed)
    out_path = Path(args.out)

    baseline = load_run(base_dir)
    framed = load_run(framed_dir)
    qids = sorted(set(baseline) | set(framed),
                   key=lambda x: int(x.lstrip("q") or "0"))

    rows: list[str] = []
    rows.append("# Question-aware framing — before/after delta")
    rows.append("")
    rows.append("Compares two runs of `tests/integration/stakeholder_queries.py`:")
    rows.append("")
    rows.append(f"- **baseline**: `{base_dir}` — system before `app/framing.py`")
    rows.append(f"- **framed**:   `{framed_dir}` — same suite, Capstone now "
                f"augmented with a per-question-type opening directive")
    rows.append("")
    rows.append("Framing score is 0–5 (5 = opening directly answers the "
                "user's question shape; 3 = generic Status with place named; "
                "1 = no engagement). The same scorer runs against both runs.")
    rows.append("")

    base_total = sum(b.get("framing_score", 0) for b in baseline.values())
    framed_total = sum(f.get("framing_score", 0) for f in framed.values())
    base_n = len(baseline)
    framed_n = len(framed)
    rows.append("## Aggregate")
    rows.append("")
    rows.append("| Metric | Baseline | Framed | Δ |")
    rows.append("|--------|---------:|-------:|---:|")
    if base_n:
        rows.append(f"| n queries | {base_n} | {framed_n} | — |")
        rows.append(f"| sum framing | {base_total} | {framed_total} | "
                    f"{framed_total - base_total:+d} |")
        rows.append(f"| mean framing | {base_total/base_n:.2f} | "
                    f"{framed_total/max(framed_n,1):.2f} | "
                    f"{(framed_total/max(framed_n,1)) - (base_total/base_n):+.2f} |")
        for thresh in (3, 4, 5):
            b = sum(1 for x in baseline.values() if x.get("framing_score", 0) >= thresh)
            f = sum(1 for x in framed.values() if x.get("framing_score", 0) >= thresh)
            rows.append(f"| ≥ {thresh}/5 | {b} | {f} | {f - b:+d} |")

    rows.append("")
    rows.append("## Per-query detail")
    rows.append("")
    rows.append("| # | Persona | Q-type | Frame | Mellea | Wall | Δ frame |")
    rows.append("|---|---------|--------|------:|-------:|-----:|---------|")
    for qid in qids:
        b = baseline.get(qid) or {}
        f = framed.get(qid) or {}
        bs = b.get("framing_score", 0)
        fs = f.get("framing_score", 0)
        delta_frame = fs - bs
        delta_str = f"{delta_frame:+d}"
        if delta_frame > 0:
            delta_str = f"**{delta_str}**"
        elif delta_frame < 0:
            delta_str = f"_{delta_str}_"
        m_b = (b.get("mellea") or {}).get("passed", "?")
        m_f = (f.get("mellea") or {}).get("passed", "?")
        rows.append(
            f"| {qid} | {(b.get('persona') or f.get('persona') or '?')[:35]} | "
            f"{b.get('question_type') or f.get('question_type') or '?'} | "
            f"{bs}→{fs} | {m_b}→{m_f}/4 | "
            f"{(f.get('wall_clock_s') or b.get('wall_clock_s') or 0):.0f}s | "
            f"{delta_str} |"
        )

    rows.append("")
    rows.append("## Opening sentence diff")
    rows.append("")
    for qid in qids:
        b = baseline.get(qid) or {}
        f = framed.get(qid) or {}
        rows.append(f"### q{qid} — {b.get('persona') or f.get('persona') or '?'}")
        rows.append("")
        rows.append(f"_Question_: `{b.get('query') or f.get('query') or ''}`")
        rows.append("")
        rows.append("Baseline opening:")
        rows.append("")
        rows.append(f"> {opening_first_sentence(b.get('paragraph', ''))}")
        rows.append("")
        rows.append("Framed opening:")
        rows.append("")
        rows.append(f"> {opening_first_sentence(f.get('paragraph', ''))}")
        rows.append("")
        rows.append(f"_Frame: {b.get('framing_score','?')} → {f.get('framing_score','?')}; "
                    f"detector matched type: `{b.get('framing_rationale','')[:80]}` → "
                    f"`{f.get('framing_rationale','')[:80]}`_")
        rows.append("")

    # Stop-condition check (Adam's rule)
    rows.append("## Stop-condition check")
    rows.append("")
    below_three = sum(1 for x in framed.values() if x.get("framing_score", 0) < 3)
    rows.append(f"Queries with framing < 3 in the framed run: **{below_three}**.")
    rows.append("")
    if below_three > 5:
        rows.append("**Threshold exceeded.** Per Adam's stop condition, this means "
                    "the Capstone prompt-conditional alone is insufficient. The next "
                    "step would be option (a) — planner sub-classifier — or option "
                    "(c) — both. Documented but NOT implemented in this overnight pass.")
    else:
        rows.append("Within budget. Capstone prompt-conditional is the right intervention; "
                    "no need to escalate to option (a)/(c).")

    out_path.write_text("\n".join(rows) + "\n")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
