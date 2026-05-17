"""Server-side PDF rendering for completed briefings.

Renders a Riprap briefing — paragraph text + grouped citations + stamp
page (document hash, methodology summary, energy ledger) — into a
PDF/UA-friendly document via WeasyPrint. The web route at
`/api/print` accepts the briefing JSON in a POST body and streams the
PDF back as `application/pdf`.

System requirements:

  - WeasyPrint 68+ (pip)
  - pango + cairo + gobject system libraries:
      macOS:  brew install pango
      Linux:  apt-get install libpango-1.0-0 libpangoft2-1.0-0

On macOS the dyld loader doesn't search brew's prefix by default, so we
set DYLD_FALLBACK_LIBRARY_PATH at import time when libpango isn't in the
default search path. Production Linux containers find pango under
`/usr/lib/x86_64-linux-gnu/` and don't need this.

The PDF carries:

  - `<title>` metadata = "Riprap briefing — <address>"
  - SHA-256 document hash on the stamp page (deterministic over the
    briefing JSON; two reviewers comparing the same briefing can
    verify by hash)
  - Energy ledger when the caller's payload has emissions data
  - Apache-2.0 + Plain-Writing-Act voice footer on every page

Future:
  - PDF/UA-1 tagged-structure post-pass via pikepdf (HANDOFF §PDF)
  - Vector map page (HANDOFF §PDF page 3)
  - Evidence-grouped-by-Stone page with per-Stone tints (HANDOFF §PDF page 4)
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

log = logging.getLogger("riprap.print_pdf")

# ---------------------------------------------------------------------------
# Lazy WeasyPrint loader — sets the macOS dyld fallback path if needed so the
# brew-installed pango/cairo libs are findable. Import is deferred so the
# server still starts cleanly even if WeasyPrint's system deps are missing
# (only `/api/print` calls will fail in that case, with a clear 503).
# ---------------------------------------------------------------------------
_HTML = None
_CSS = None
_LOAD_ERR: str | None = None


def _ensure_loaded() -> None:
    global _HTML, _CSS, _LOAD_ERR
    if _HTML is not None or _LOAD_ERR is not None:
        return
    if sys.platform == "darwin":
        brew_lib = "/opt/homebrew/lib"
        if os.path.isdir(brew_lib):
            existing = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
            if brew_lib not in existing.split(":"):
                os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = (
                    f"{brew_lib}:{existing}" if existing else brew_lib
                )
    try:
        from weasyprint import CSS as _C
        from weasyprint import HTML as _H  # noqa: PLC0415
        _HTML, _CSS = _H, _C
    except Exception as e:  # noqa: BLE001
        _LOAD_ERR = f"{type(e).__name__}: {e}"
        log.warning("weasyprint import failed: %s", _LOAD_ERR)


# ---------------------------------------------------------------------------
# Document hash — deterministic SHA-256 over the briefing JSON.
# ---------------------------------------------------------------------------
def briefing_hash(payload: dict[str, Any]) -> str:
    """Canonical SHA-256 over the briefing payload.

    The hash is the verification fingerprint Two reviewers comparing the
    "same" briefing use to confirm bit-for-bit equivalence. Canonical
    JSON (sorted keys, no whitespace) ensures the hash is stable across
    serialiser differences.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# HTML template — semantic markup that WeasyPrint can tag for PDF/UA.
# All inline styles to keep the file self-contained; this avoids the
# need to ship an external print.css alongside the route.
# ---------------------------------------------------------------------------
_PDF_STYLES = """
@page {
  size: Letter;
  margin: 1in 0.9in 0.9in 0.9in;
  @bottom-left {
    content: "Riprap " counter(page) " / " counter(pages);
    font-family: "IBM Plex Mono", monospace;
    font-size: 8pt;
    color: #64748b;
  }
  @bottom-right {
    content: "Apache-2.0 · public-record sources only · no commercial APIs";
    font-family: "IBM Plex Mono", monospace;
    font-size: 8pt;
    color: #64748b;
  }
}
@page :first {
  @bottom-left { content: ""; }
  @bottom-right { content: ""; }
}
body {
  font-family: "IBM Plex Sans", -apple-system, system-ui, sans-serif;
  font-size: 10.5pt;
  line-height: 1.55;
  color: #0F172A;
}
h1.cover-h1 {
  font-family: "IBM Plex Serif", Georgia, serif;
  font-size: 28pt;
  font-weight: 500;
  letter-spacing: -0.01em;
  line-height: 1.12;
  margin: 0 0 16pt;
}
.cover-eyebrow {
  font-family: "IBM Plex Mono", monospace;
  font-size: 9pt;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #64748b;
  margin: 0 0 12pt;
}
.cover-meta {
  margin-top: 24pt;
  border-top: 1px solid #CBD5E1;
  padding-top: 14pt;
}
.cover-meta dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4pt 16pt;
  font-size: 10pt;
  margin: 0;
}
.cover-meta dt {
  font-family: "IBM Plex Mono", monospace;
  font-size: 9pt;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #64748b;
}
.cover-meta dd { margin: 0; color: #0F172A; }
.cover-disclaim {
  margin-top: 36pt;
  padding: 14pt 18pt;
  border-left: 3pt solid #92400E;
  background: #F4F6F9;
  font-size: 9.5pt;
  line-height: 1.5;
  color: #334155;
}
.cover-disclaim strong { color: #0F172A; }
h2.section-h2 {
  font-family: "IBM Plex Sans", system-ui, sans-serif;
  font-size: 13pt;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  color: #0F172A;
  border-bottom: 1px solid #CBD5E1;
  padding: 18pt 0 6pt;
  margin: 0 0 12pt;
  page-break-after: avoid;
}
.briefing-body {
  font-family: "IBM Plex Serif", Georgia, serif;
  font-size: 11pt;
  line-height: 1.62;
  color: #0F172A;
  white-space: pre-wrap;
}
.cites {
  margin-top: 18pt;
  border-top: 1px solid #CBD5E1;
  padding-top: 10pt;
}
.cites h3 {
  font-family: "IBM Plex Mono", monospace;
  font-size: 9pt;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748b;
  margin: 0 0 8pt;
}
.cites ol {
  /* `[N]` prefix in each item carries the citation marker — matches
     what appears inline in the prose. The <ol> auto-marker would
     duplicate that, so drop the auto-numbering. */
  list-style: none;
  font-size: 9.5pt;
  line-height: 1.5;
  padding-left: 0;
  color: #334155;
  margin: 0;
}
.cites li { margin-bottom: 4pt; }
.cites li strong { color: #0F172A; }
.cites li a {
  color: #005EA2;
  text-decoration: none;
  word-break: break-all;
}
.stamp {
  page-break-before: always;
}
.stamp .kv-block {
  margin: 14pt 0;
  border: 1px solid #CBD5E1;
  padding: 12pt 14pt;
}
.stamp .kv-block dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4pt 12pt;
  font-size: 9.5pt;
  margin: 0;
}
.stamp .kv-block dt {
  font-family: "IBM Plex Mono", monospace;
  font-size: 9pt;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #64748b;
}
.stamp .kv-block dd { margin: 0; color: #0F172A; }
.stamp .hash {
  font-family: "IBM Plex Mono", monospace;
  font-size: 9pt;
  word-break: break-all;
  color: #0F172A;
}
.foot-note {
  font-family: "IBM Plex Mono", monospace;
  font-size: 8pt;
  color: #64748b;
  margin-top: 18pt;
  padding-top: 8pt;
  border-top: 1px dashed #CBD5E1;
}
"""


def _e(s: str | None) -> str:
    """HTML-escape None/str safely."""
    return html.escape(s or "", quote=True)


def _render_html(payload: dict[str, Any], doc_hash: str) -> str:
    """Build the semantic HTML the WeasyPrint engine will tag and paginate."""
    address = payload.get("query") or payload.get("address") or "—"
    paragraph = payload.get("paragraph") or "(no briefing text)"
    plan = payload.get("plan") or {}
    intent = plan.get("intent") or payload.get("intent") or "—"
    deployment = payload.get("deployment") or {}
    city = deployment.get("city") or "—"
    hazard = deployment.get("hazard") or "Climate-exposure briefing"
    cites = payload.get("citations") or []
    mellea = payload.get("mellea") or {}
    emissions = payload.get("emissions") or {}

    rendered_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    # Cites list — each is { doc_id, source?, title?, url?, vintage? }
    cite_lis = []
    for i, c in enumerate(cites, start=1):
        if not isinstance(c, dict):
            continue
        doc_id = _e(c.get("doc_id") or "")
        source = _e(c.get("source") or "")
        title = _e(c.get("title") or "")
        url = c.get("url") or ""
        vintage = _e(c.get("vintage") or "")
        url_html = f' &middot; <a href="{_e(url)}">{_e(url)}</a>' if url else ""
        vintage_html = f' &middot; <span>{vintage}</span>' if vintage else ""
        cite_lis.append(
            f"<li><strong>[{i}]</strong> "
            f"<strong>{doc_id}</strong> &middot; {source} &middot; {title}"
            f"{vintage_html}{url_html}</li>"
        )
    cite_html = "\n".join(cite_lis) or "<li>(no citations)</li>"

    # Energy ledger lines (best-effort — only show what's present)
    ledger_rows: list[tuple[str, str]] = []
    for k, label in (
        ("model", "Reconciler model"),
        ("hardware", "Serve hardware"),
        ("wall_s", "Wall-clock (s)"),
        ("total_tokens", "Total tokens"),
        ("total_wh", "Energy (Wh)"),
        ("co2e_g", "CO₂e (g)"),
    ):
        v = emissions.get(k)
        if v is None:
            continue
        ledger_rows.append((label, _e(str(v))))
    ledger_html = (
        "<dl>"
        + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in ledger_rows)
        + "</dl>"
    ) if ledger_rows else "<p>(no energy ledger in payload)</p>"

    mellea_attempts = mellea.get("attempts") or "—"
    mellea_passed = ", ".join(mellea.get("passed") or []) or "—"
    mellea_failed = ", ".join(mellea.get("failed") or []) or "—"

    # Paragraph: convert simple **bold** markdown to <strong>, escape rest.
    # The Capstone reconciler emits paragraph with [N] citation markers
    # already inline; we preserve them verbatim.
    safe_para = _e(paragraph).replace("**", "")
    # Best-effort line-break preservation (the paragraph is multi-paragraph)
    safe_para = safe_para.replace("\n\n", "</p><p>").replace("\n", "<br />")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Riprap briefing — {_e(address)}</title>
<style>{_PDF_STYLES}</style>
</head>
<body>

<section class="cover">
  <p class="cover-eyebrow">Riprap &middot; {_e(hazard)}</p>
  <h1 class="cover-h1">{_e(address)}</h1>
  <div class="cover-meta">
    <dl>
      <dt>Deployment</dt><dd>{_e(city)}</dd>
      <dt>Intent</dt><dd>{_e(intent)}</dd>
      <dt>Generated</dt><dd>{_e(rendered_at)}</dd>
      <dt>Document hash</dt><dd class="hash">{_e(doc_hash)}</dd>
    </dl>
  </div>
  <div class="cover-disclaim">
    <strong>Riprap is a reference dossier, not a stamped engineering memo, risk score, or disclosure.</strong>
    It is informational only; not a substitute for a licensed professional, and not designed
    for personal property decisions, real-estate transactions, or mortgage / insurance
    underwriting. Data is used under each source's open-data terms. Independent open-source
    project; not affiliated with FEMA, NOAA, USGS, or any city government.
  </div>
</section>

<section>
  <h2 class="section-h2">Briefing</h2>
  <div class="briefing-body"><p>{safe_para}</p></div>
</section>

<section>
  <h2 class="section-h2">Citations &middot; {len(cite_lis)}</h2>
  <div class="cites">
    <ol>{cite_html}</ol>
  </div>
</section>

<section class="stamp">
  <h2 class="section-h2">Verification &amp; methodology</h2>
  <div class="kv-block">
    <dl>
      <dt>Document hash</dt><dd class="hash">{_e(doc_hash)}</dd>
      <dt>Reconciler</dt><dd>IBM Granite 4.1 (Apache 2.0)</dd>
      <dt>Grounding</dt><dd>Mellea rejection sampling, {_e(str(mellea_attempts))} attempt(s)</dd>
      <dt>Mellea passed</dt><dd>{mellea_passed}</dd>
      <dt>Mellea failed</dt><dd>{mellea_failed}</dd>
    </dl>
  </div>
  <h3 style="font-family:'IBM Plex Mono',monospace;font-size:9pt;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;margin:0 0 8pt;">Energy ledger</h3>
  <div class="kv-block">{ledger_html}</div>
  <p class="foot-note">
    Riprap composes federal, state, and city public-record data into a written, citation-grounded
    briefing. Every numeric claim in the prose above links to one of the cited sources. Two reviewers
    comparing the same briefing can verify bit-for-bit equivalence by comparing the document hash.
  </p>
</section>

</body>
</html>"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
class PdfRenderFailed(RuntimeError):
    """Raised when WeasyPrint's system deps are missing or rendering errors."""


def render_briefing_pdf(payload: dict[str, Any]) -> bytes:
    """Render a briefing payload to PDF bytes. Raises PdfRenderFailed if
    WeasyPrint isn't available (system deps missing) or rendering throws."""
    _ensure_loaded()
    if _HTML is None:
        raise PdfRenderFailed(
            f"WeasyPrint unavailable: {_LOAD_ERR}. "
            f"Install system deps: brew install pango (macOS) "
            f"or apt-get install libpango-1.0-0 libpangoft2-1.0-0 (Linux)."
        )
    doc_hash = briefing_hash(payload)
    html_doc = _render_html(payload, doc_hash)
    try:
        return _HTML(string=html_doc).write_pdf()
    except Exception as e:  # noqa: BLE001
        raise PdfRenderFailed(f"WeasyPrint render failed: {e}") from e
