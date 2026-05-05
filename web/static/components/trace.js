// <r-trace> — specialist trail. Reactive list of pipeline steps.
//
// API:
//   .pushStep(step)    — append a {step, ok, elapsed_s, result, err} record
//   .clear()           — reset
//   .meta = "1.4s"     — text shown in the header
//   .stepLabels = {...} — { stepName: [label, hint] } map (set once at boot)
//
// Light DOM (no shadow) so the existing `#steps li.ok / .err / .running`
// CSS in agent.html keeps applying without rewrites.

import { html, css, LitElement } from "https://esm.sh/lit@3";

const escapeHtml = (s) =>
  String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export class Trace extends LitElement {
  static properties = {
    steps:      { type: Array, state: true },
    meta:       { type: String, reflect: true },
    stepLabels: { type: Object },
  };

  createRenderRoot() { return this; }

  constructor() {
    super();
    this.steps = [];
    this.meta = "";
    this.stepLabels = {};
  }

  pushStep(step) {
    this.steps = [...this.steps, step];
  }

  clear() {
    this.steps = [];
    this.meta = "";
  }

  _renderStep(step) {
    const [label, hint] = this.stepLabels[step.step] || [step.step, ""];
    const ok = step.ok === true;
    const fail = step.ok === false;
    const cls = ok ? "ok" : fail ? "err" : "running";
    const mark = ok ? "✓" : fail ? "✗" : "○";
    const time = step.elapsed_s != null
      ? `<span class="time">${step.elapsed_s}s</span>` : "";
    const result = step.result
      ? `<div class="result">${escapeHtml(JSON.stringify(step.result))}</div>` : "";
    const err = step.err
      ? `<div class="result" style="color:var(--nyc-scarlet)">${escapeHtml(step.err)}</div>` : "";
    // Inner HTML is hand-built so the existing list CSS targets the same
    // structure as the legacy renderer; we keep .innerHTML rather than
    // Lit's html`` for byte-for-byte parity here.
    const li = document.createElement("li");
    li.className = cls;
    li.innerHTML = `
      <span class="icon">${mark}</span>
      <div>
        <div class="label">${escapeHtml(label)}</div>
        <div class="meta">${escapeHtml(hint)}</div>
      </div>
      ${time}
      ${result}
      ${err}
    `;
    return li;
  }

  render() {
    // Render the <ol> as innerHTML on update so we don't fight Lit's
    // template diffing for raw HTML lists.
    queueMicrotask(() => {
      const ol = this.querySelector("ol#steps-list");
      if (!ol) return;
      ol.innerHTML = "";
      for (const s of this.steps) ol.appendChild(this._renderStep(s));
    });
    // Inline reset so the legacy `#steps { list-style: none; ... }` rules
    // (which now target the host element, not the <ol>) keep applying.
    return html`<ol id="steps-list" style="list-style:none; margin:0; padding:4px 0; font-size:12.5px;"></ol>`;
  }
}

customElements.define("r-trace", Trace);
