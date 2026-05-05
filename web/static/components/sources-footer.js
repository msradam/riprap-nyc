// <r-sources-footer> — numbered, hyperlinked, vintage-aware Sources
// section that appears below the Briefing in the agent UI and inside
// the printable /report.
//
// Shared signals power the cross-linking with <r-briefing>: hovering
// a [N] chip in the prose highlights the matching <li> here, and
// clicking either side persists the highlight + scrolls into view.
//
// Mounts via <r-sources-footer></r-sources-footer>. Reads:
//   - citeIndex     — { doc_id: number } from Briefing
//   - highlightedDocId — current highlight target (in/out)
// Plus three label/url/vintage maps passed in as properties.

import { html, css, LitElement } from "https://esm.sh/lit@3";
import { SignalWatcher } from "https://esm.sh/@lit-labs/signals@0.1.x";
import { citeIndex, highlightedDocId } from "./signals.js";

export class SourcesFooter extends SignalWatcher(LitElement) {
  static properties = {
    labels:   { type: Object },
    urls:     { type: Object },
    vintages: { type: Object },
  };

  static styles = css`
    :host {
      display: block;
      border-top: 1px solid var(--line, #e5e7eb);
      background: var(--bg-soft, #f5f7fb);
      padding: 12px 16px 14px;
    }
    :host([hidden]) { display: none; }
    .src-h {
      font-size: 10px; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.10em;
      color: var(--text-muted, #6b7280);
      margin: 0 0 8px;
    }
    ol {
      margin: 0; padding: 0; list-style: none;
      display: grid; gap: 6px;
      font-size: 11.5px; line-height: 1.45;
    }
    li {
      display: grid; grid-template-columns: 22px 1fr;
      gap: 8px; align-items: baseline;
      padding: 4px 6px; border-radius: 3px;
      cursor: pointer;
      transition: background 0.15s;
    }
    li:hover, li.hl {
      background: rgba(22, 66, 223, 0.10);
    }
    .src-num {
      font-family: var(--mono, monospace); font-size: 10.5px;
      font-weight: 700; color: var(--nyc-blue, #1642DF);
      text-align: right;
    }
    .src-link {
      color: var(--text, #111); text-decoration: none;
      border-bottom: 1px dotted var(--text-muted, #6b7280);
      transition: color 0.12s, border-color 0.12s;
    }
    .src-link:hover {
      color: var(--nyc-blue, #1642DF);
      border-bottom-color: var(--nyc-blue, #1642DF);
    }
    .src-ext {
      font-size: 9.5px; color: var(--text-faint, #9ca3af);
      margin-left: 2px; vertical-align: super;
    }
    .src-vintage {
      display: block; color: var(--text-muted, #6b7280);
      font-size: 9.5px; margin-top: 2px;
    }
    .src-id {
      display: inline-block;
      font-family: var(--mono, monospace); font-size: 9.5px;
      color: var(--text-faint, #9ca3af); margin-left: 6px;
    }
  `;

  constructor() {
    super();
    this.labels = {};
    this.urls = {};
    this.vintages = {};
  }

  _entries() {
    return Object.entries(citeIndex.get() || {}).sort((a, b) => a[1] - b[1]);
  }

  _onHover(id) {
    highlightedDocId.set(id);
  }

  _onLeave() {
    // Only clear if not pinned by click — keep highlight on click.
    // For now, hover-only highlight clears on leave.
  }

  _onClick(id) {
    const cur = highlightedDocId.get();
    highlightedDocId.set(cur === id ? null : id);
  }

  render() {
    const entries = this._entries();
    if (!entries.length) {
      this.setAttribute("hidden", "");
      return html``;
    }
    this.removeAttribute("hidden");
    const hl = highlightedDocId.get();
    return html`
      <div class="src-h">Sources</div>
      <ol>
        ${entries.map(([id, n]) => {
          const url = this.urls[id];
          const label = this.labels[id] || id;
          const vintage = this.vintages[id];
          const cls = id === hl ? "hl" : "";
          return html`
            <li class="${cls}"
                @mouseenter=${() => this._onHover(id)}
                @click=${() => this._onClick(id)}>
              <span class="src-num">[${n}]</span>
              <div>
                ${url
                  ? html`<a class="src-link" href="${url}" target="_blank" rel="noopener noreferrer" @click=${(e) => e.stopPropagation()}>${label} <span class="src-ext">↗</span></a>`
                  : html`<span>${label}</span>`}
                <span class="src-id">${id}</span>
                ${vintage ? html`<span class="src-vintage">${vintage}</span>` : ""}
              </div>
            </li>
          `;
        })}
      </ol>
    `;
  }
}

customElements.define("r-sources-footer", SourcesFooter);
