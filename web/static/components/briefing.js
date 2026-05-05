// <r-briefing> — the streaming-token, citation-chipped briefing panel.
//
// Replaces the agent.js renderMarkdown + rewriteCitations + paint
// scheduler. Token streaming becomes "append to a signal, re-render."
//
// Properties:
//   text       — full markdown text (set by parent on token / final events)
//   streaming  — bool; shows the blinking caret
//   citeIndex  — { doc_id: number } shared with <r-sources-footer>
//   sourceLabels — passed through for chip tooltips
//
// Signals consumed:
//   highlightedDocId — toggles `.hl` on chips reactively (set by
//                      <r-sources-footer> on hover)
// Signals updated:
//   citeIndex        — populated as citations are encountered in the text
//   highlightedDocId — set on chip hover/click

import { html, LitElement } from "https://esm.sh/lit@3";
import { unsafeHTML } from "https://esm.sh/lit@3/directives/unsafe-html.js";
import { SignalWatcher } from "https://esm.sh/@lit-labs/signals@0.1.x";
import { citeIndex, highlightedDocId } from "./signals.js";

// Same minimal markdown subset as agent.js renderMarkdown — kept
// duplicated for now; will collapse when agent.js stops calling
// renderMarkdown. After full port this is the only impl.
function renderMarkdownPure(text) {
  const lines = text.split("\n");
  const out = [];
  let para = []; let bullets = [];
  const escapeHtml = (s) =>
    String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const flushPara = () => {
    if (!para.length) return;
    const safe = escapeHtml(para.join(" ").trim())
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    if (safe) out.push(`<p class="rsum-p">${safe}</p>`);
    para = [];
  };
  const flushBullets = () => {
    if (!bullets.length) return;
    const items = bullets.map(b => {
      const safe = escapeHtml(b.trim()).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
      return `<li>${safe}</li>`;
    }).join("");
    out.push(`<ul class="rsum-list">${items}</ul>`);
    bullets = [];
  };
  // Granite sometimes runs all bullets onto one line.
  const expanded = [];
  for (const line of lines) {
    if (line.trim().startsWith("- ") && line.includes(" - ", 2)) {
      const parts = line.split(/(?:^|(?<=\.\s))\s*-\s+/g).filter(p => p.trim());
      for (const p of parts) expanded.push("- " + p.trim());
    } else { expanded.push(line); }
  }
  for (const line of expanded) {
    const m = line.match(/^\s*\*\*([A-Z][A-Za-z\s/]+)\.\*\*\s*$/);
    if (m) { flushPara(); flushBullets(); out.push(`<h4 class="rsum-h">${escapeHtml(m[1])}</h4>`); }
    else if (/^\s*[-*]\s+/.test(line)) { flushPara(); bullets.push(line.replace(/^\s*[-*]\s+/, "")); }
    else { flushBullets(); para.push(line); }
  }
  flushPara(); flushBullets();
  return out.join("");
}

function rewriteCitations(html, sourceLabels, indexMap) {
  return html.replace(/\[([a-z0-9_]+)\]/gi, (_, id) => {
    const norm = id.toLowerCase();
    if (indexMap[norm] == null) indexMap[norm] = Object.keys(indexMap).length + 1;
    const n = indexMap[norm];
    const lab = sourceLabels[norm] || norm;
    return `<span class="cite" data-src-id="${norm}" data-src-n="${n}" title="${lab.replace(/"/g, "&quot;")} — click to highlight in Sources">${n}</span>`;
  });
}

export class Briefing extends SignalWatcher(LitElement) {
  static properties = {
    text:         { type: String },
    streaming:    { type: Boolean, reflect: true },
    sourceLabels: { type: Object },
  };

  // No shadow DOM — we use the parent's `.report-pane #paragraph` styles
  // directly so the markdown renders match the legacy/print idiom.
  createRenderRoot() { return this; }

  constructor() {
    super();
    this.text = "";
    this.streaming = false;
    this.sourceLabels = {};
  }

  updated(changed) {
    if (changed.has("text") && this.text) {
      // Bind chip hover/click to the highlight signal post-render.
      this._bindChips();
    }
  }

  _bindChips() {
    this.querySelectorAll(".cite").forEach(c => {
      const id = c.dataset.srcId;
      if (!id || c.dataset.signalBound) return;
      c.dataset.signalBound = "1";
      c.addEventListener("mouseenter", () => highlightedDocId.set(id));
      c.addEventListener("click", (e) => {
        e.stopPropagation();
        const cur = highlightedDocId.get();
        highlightedDocId.set(cur === id ? null : id);
      });
    });
    // Apply highlight class reactively from current signal value.
    const hl = highlightedDocId.get();
    this.querySelectorAll(".cite").forEach(c => {
      c.classList.toggle("hl", c.dataset.srcId === hl);
    });
  }

  render() {
    if (!this.text) return html`<div class="rsum-p" style="color:var(--text-muted)">Waiting for content…</div>`;
    const indexMap = {};
    const md = renderMarkdownPure(this.text);
    const withCites = rewriteCitations(md, this.sourceLabels, indexMap);
    // Push the citation index up to the shared signal so SourcesFooter
    // re-renders. Done in render() because indexMap is computed here.
    queueMicrotask(() => citeIndex.set({ ...indexMap }));
    return html`${unsafeHTML(withCites)}`;
  }
}

customElements.define("r-briefing", Briefing);
