"""Mock trace UI renderer for experiment validation.

Production renders specialist results into <r-trace>'s pushStep cards
(label + key=value rows + occasionally a thumbnail). Experiments don't
have a real frontend; this writes the same payload to stdout in a
trace-card-shaped block so a non-specialist viewer can confirm the
specialist would render legibly.
"""

from __future__ import annotations


def render_step(label: str, ok: bool, fields: dict, elapsed_s: float | None = None,
                thumbnail_path: str | None = None) -> str:
    head = f"[{'OK' if ok else 'ERR'}] {label}"
    if elapsed_s is not None:
        head += f"  ({elapsed_s:.2f}s)"
    rows = []
    for k, v in fields.items():
        if isinstance(v, float):
            v = f"{v:.3f}".rstrip("0").rstrip(".")
        rows.append(f"  {k} = {v}")
    if thumbnail_path:
        rows.append(f"  thumbnail = {thumbnail_path}")
    return head + "\n" + "\n".join(rows)


def banner(s: str) -> str:
    bar = "─" * len(s)
    return f"\n{bar}\n{s}\n{bar}"
