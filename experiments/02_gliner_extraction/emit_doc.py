"""Build a `role: "document gliner_<source>"` chat message from a
GLiNER extraction list.

The doc body is a labeled list of extractions:

    source: <pdf_id>
    paragraph_excerpt: "<first 240 chars of the source paragraph>"
    extractions:
      - [agency] NYC DEP
      - [dollar_amount] $22.5 million
      - [date_range] FY 2025-2027
      - [nyc_location] Hollis
      - [infrastructure_project] Bluebelt expansion

This is structured enough that Granite 4.1 grounds against the typed
fields ("DEP allocated $22.5 million for the Bluebelt expansion in
Hollis"), and the doc_id tag naming by source PDF means [gliner_dep]
or [gliner_comptroller] resolves cleanly through the existing Mellea
citations_resolve check.
"""

from __future__ import annotations

SYSTEM_PROMPT_FRAGMENT = """\
You will be given GLiNER-extracted typed entities tagged
[gliner_<source>]. Cite at least one specific [agency], [dollar_amount],
or [infrastructure_project] from the extractions, using its parent
[gliner_<source>] tag. Do not invent values that aren't in the
extractions list.
"""


def make_doc(source_id: str, paragraph: str, extractions) -> dict:
    """Construct {role, content} for the reconciler.

    source_id: short slug like "comptroller", "dep", "mta", "nycha",
    "coned" — must match [a-z][a-z0-9_]* so the doc_id appears in the
    Mellea citations check.
    """
    excerpt = paragraph.strip().replace("\n", " ")[:240]
    if len(paragraph) > 240:
        excerpt += "…"
    rows = [f"source: {source_id}",
            f"paragraph_excerpt: \"{excerpt}\"",
            "extractions:"]
    for e in extractions:
        rows.append(f"  - [{e.label}] {e.text}  (score={e.score:.2f})")
    return {"role": f"document gliner_{source_id}", "content": "\n".join(rows)}


def render_for_trace(source_id: str, extractions) -> dict:
    counts = {}
    for e in extractions:
        counts[e.label] = counts.get(e.label, 0) + 1
    return {
        "label": f"gliner_{source_id}",
        "ok": True,
        "fields": {
            "n_entities": len(extractions),
            **counts,
        },
    }
