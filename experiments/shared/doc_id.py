"""doc_id helpers for specialist outputs.

Specialists emit chat messages with `role="document <doc_id>"` and a
content body. Both Granite paths (Ollama Modelfile + vLLM HF template
via app/llm.py) consume that shape. These helpers keep doc_id strings
consistent across experiments so the reconciler's `[doc_id]` regex
finds them.
"""

from __future__ import annotations

import re
from typing import Any

# doc_id syntax mirrors the existing production layers: lowercase, snake
# case, alphanumerics + underscores. The Mellea citations regex is
# `\[(?P<id>[a-z][a-z0-9_]*)\]` — anything that doesn't match is invisible
# to validation.
_VALID = re.compile(r"^[a-z][a-z0-9_]*$")


def make_doc(doc_id: str, body: str) -> dict[str, str]:
    if not _VALID.match(doc_id):
        raise ValueError(
            f"doc_id {doc_id!r} must match [a-z][a-z0-9_]* "
            "to be visible to the Mellea citations check"
        )
    return {"role": f"document {doc_id}", "content": body}


def render_kv_body(rows: list[tuple[str, Any]]) -> str:
    """Render a list of (label, value) tuples as a compact key:value
    body suitable for a `document <doc_id>` content payload. Granite
    grounds well against this format."""
    out = []
    for label, val in rows:
        if val is None or val == "":
            continue
        if isinstance(val, float):
            val = f"{val:.3f}".rstrip("0").rstrip(".")
        out.append(f"{label}: {val}")
    return "\n".join(out)
