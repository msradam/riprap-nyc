<svelte:options
  customElement={{
    tag: "r-briefing",
    props: {
      text:         { type: "String" },
      streaming:    { type: "Boolean", reflect: true },
      sourceLabels: { type: "Object" },
    },
  }} />

<script>
  import { onMount, tick } from "svelte";
  import { citeIndex, highlightedDocId } from "./stores.js";

  let { text = "", streaming = false, sourceLabels = {} } = $props();

  const escapeHtml = (s) =>
    String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  function renderMarkdown(input) {
    const lines = input.split("\n");
    const out = [];
    let para = []; let bullets = [];
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

  function rewriteCitations(html, indexMap) {
    return html.replace(/\[([a-z0-9_]+)\]/gi, (_, id) => {
      const norm = id.toLowerCase();
      if (indexMap[norm] == null) indexMap[norm] = Object.keys(indexMap).length + 1;
      const n = indexMap[norm];
      const lab = sourceLabels[norm] || norm;
      return `<span class="cite" data-src-id="${norm}" data-src-n="${n}" title="${lab.replace(/"/g, "&quot;")} — click to highlight">${n}</span>`;
    });
  }

  let bodyHtml = $derived.by(() => {
    if (!text) return "";
    const indexMap = {};
    const md = renderMarkdown(text);
    const html = rewriteCitations(md, indexMap);
    queueMicrotask(() => citeIndex.set({ ...indexMap }));
    return html;
  });

  let container;
  let hl = $derived($highlightedDocId);

  // Re-bind chip listeners + hl class whenever the body or hl changes.
  $effect(() => {
    void bodyHtml; void hl;
    if (!container) return;
    tick().then(() => {
      const chips = container.querySelectorAll(".cite");
      chips.forEach(c => {
        const id = c.dataset.srcId;
        if (!id) return;
        c.classList.toggle("hl", id === hl);
        if (c.dataset.bound) return;
        c.dataset.bound = "1";
        c.addEventListener("mouseenter", () => highlightedDocId.set(id));
        c.addEventListener("click", (e) => {
          e.stopPropagation();
          highlightedDocId.update(cur => cur === id ? null : id);
        });
      });
    });
  });
</script>

{#if !text}
  <div class="rsum-p" style="color:var(--text-muted, #6b7280)">Waiting for content…</div>
{:else}
  <div bind:this={container}>
    {@html bodyHtml}
  </div>
{/if}

<style>
  :host { display: block; }
  /* The host-level styles for typography, .cite, etc. live in the parent
     stylesheet and target #paragraph descendants — they pierce shadow DOM
     for inline-styled markup we don't ship here. The .rsum-* classes are
     wired in the global stylesheet. We intentionally don't restate them. */
  :host(.streaming)::after,
  :host([streaming])::after {
    content: "▋";
    display: inline-block; color: var(--nyc-blue, #1642DF);
    margin-left: 2px;
    animation: caret 0.9s steps(1) infinite;
  }
  @keyframes caret { 50% { opacity: 0; } }
</style>
