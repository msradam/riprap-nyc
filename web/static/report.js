// Renders the print-ready auditable report from the agent's last result,
// passed via sessionStorage. Includes original query, planner decision,
// full specialist trail, map snapshot, briefing prose with citations,
// and a Sources section listing every doc_id with its vintage + URL.

(function () {
  const raw = sessionStorage.getItem("riprap_report");
  if (!raw) return;
  let pkg;
  try { pkg = JSON.parse(raw); } catch (e) {
    document.getElementById("paper").innerHTML =
      `<p style="color:#c00">Could not parse stored report payload: ${e.message}</p>`;
    return;
  }
  render(pkg);
})();

function escapeHtml(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function render(pkg) {
  const r = pkg.result || {};
  const plan = pkg.plan || r.plan || {};
  const trace = pkg.trace || [];
  const labels = pkg.sourceLabels || {};
  const urls = pkg.sourceUrls || {};
  const vintages = pkg.sourceVintages || {};
  const stepLabels = pkg.stepLabels || {};

  const intent = r.intent || plan.intent || "—";
  const intentTitleMap = {
    single_address:    "Flood-exposure briefing — address",
    neighborhood:      "Flood-exposure briefing — neighborhood",
    development_check: "Active development × flood exposure",
    live_now:          "Current conditions — NYC",
  };
  const place = (r.target && r.target.nta_name)
              || (r.geocode && r.geocode.address)
              || r.place || "—";

  // Build the citation index from the briefing prose so we render a
  // numbered Sources section in the SAME order the chips appear in the
  // text — same idiom as the agent UI.
  const citeIndex = {};
  const para = r.paragraph || "";
  const para2 = para.replace(/\[([a-z0-9_]+)\]/gi, (_, id) => {
    const norm = id.toLowerCase();
    if (citeIndex[norm] == null) citeIndex[norm] = Object.keys(citeIndex).length + 1;
    return `<span class="cite">${citeIndex[norm]}</span>`;
  });

  const html = `
    <header class="r-head">
      <div class="r-brand">Riprap</div>
      <div class="r-tagline">Citation-grounded flood-exposure briefing</div>
      <dl class="r-meta-grid">
        <dt>Subject</dt><dd>${escapeHtml(intentTitleMap[intent] || "Briefing")} · <strong>${escapeHtml(place)}</strong></dd>
        ${r.geocode && r.geocode.borough ? `<dt>Borough</dt><dd>${escapeHtml(r.geocode.borough)}</dd>` : ""}
        ${r.target && r.target.borough ? `<dt>Borough</dt><dd>${escapeHtml(r.target.borough)}</dd>` : ""}
        ${r.geocode && r.geocode.bbl ? `<dt>BBL</dt><dd class="mono">${escapeHtml(r.geocode.bbl)}</dd>` : ""}
        ${r.target && r.target.nta_code ? `<dt>NTA</dt><dd class="mono">${escapeHtml(r.target.nta_code)}</dd>` : ""}
        <dt>Generated</dt><dd>${escapeHtml(pkg.finishedAt || new Date().toISOString())}</dd>
        <dt>Total runtime</dt><dd>${pkg.wallSeconds ?? r.total_s ?? "—"} s</dd>
      </dl>
    </header>

    <section class="r-section">
      <h2>1 · Original query</h2>
      <div class="r-query">"${escapeHtml(pkg.query)}"</div>
    </section>

    <section class="r-section">
      <h2>2 · Agent routing decision</h2>
      <dl class="r-plan">
        <dt>Intent</dt><dd class="mono">${escapeHtml(plan.intent || intent)}</dd>
        <dt>Targets</dt><dd class="mono">${escapeHtml((plan.targets || []).map(t => `${t.type}:${t.text}`).join(", ") || "—")}</dd>
        <dt>Specialists requested</dt><dd class="mono">${escapeHtml((plan.specialists || []).join(", ") || "—")}</dd>
        ${plan.rationale ? `<dd class="r-plan-rationale">"${escapeHtml(plan.rationale)}"</dd>` : ""}
      </dl>
    </section>

    <section class="r-section">
      <h2>3 · Specialist trail</h2>
      <div class="lead">${trace.length} specialists invoked. Each row shows the
        step name, status, elapsed time, and the structured result the step
        produced. Sources of any data referenced in the briefing appear in
        Section 6.</div>
      <table class="r-trace">
        <thead>
          <tr><th>#</th><th>Step</th><th>Status</th><th>Elapsed</th><th>Result / error</th></tr>
        </thead>
        <tbody>
          ${trace.map((s, i) => {
            const ok = s.ok === true;
            const fail = s.ok === false;
            const cls = ok ? "ok" : fail ? "err" : "";
            const mark = ok ? "✓" : fail ? "✗" : "○";
            const [label] = stepLabels[s.step] || [s.step, ""];
            const detail = s.err
              ? `<span class="err-msg">${escapeHtml(s.err)}</span>`
              : `<span class="result">${escapeHtml(JSON.stringify(s.result ?? {}))}</span>`;
            return `<tr class="${cls}">
              <td class="mono">${i + 1}</td>
              <td><strong>${escapeHtml(label)}</strong><br>
                  <span class="mono" style="color:#888;font-size:7.5pt">${escapeHtml(s.step)}</span></td>
              <td><span class="mark">${mark}</span></td>
              <td class="mono">${s.elapsed_s != null ? s.elapsed_s + "s" : "—"}</td>
              <td>${detail}</td>
            </tr>`;
          }).join("")}
        </tbody>
      </table>
    </section>

    ${pkg.mapPng ? `
    <section class="r-section">
      <h2>4 · Map (snapshot)</h2>
      <div class="r-map">
        <img src="${pkg.mapPng}" alt="Map snapshot at report-generation time">
        <div class="legend-cap">Snapshot of the live MapLibre map captured at report-generation time. Layers: per-intent (Sandy 2012 / DEP scenarios / NTA boundary / DOB permit pins / address pin).</div>
      </div>
    </section>
    ` : `
    <section class="r-section">
      <h2>4 · Map</h2>
      <div class="r-map no-map">No map snapshot was captured (the map may have been hidden or empty for this query type).</div>
    </section>
    `}

    <section class="r-section">
      <h2>5 · Cited briefing</h2>
      <div class="r-briefing">${renderBriefingMarkdown(para2)}</div>
    </section>

    <section class="r-section">
      <h2>6 · Sources</h2>
      <ol class="r-sources">
        ${Object.entries(citeIndex).sort((a, b) => a[1] - b[1]).map(([id, n]) => {
          const url = urls[id];
          return `<li>
            <span class="num">[${n}]</span>
            <div>
              <span class="label">${escapeHtml(labels[id] || id)}</span>
              ${vintages[id] ? `<span class="vintage">Vintage: ${escapeHtml(vintages[id])}</span>` : ""}
              ${url ? `<span class="url"><a href="${escapeHtml(url)}">${escapeHtml(url)}</a></span>` : ""}
              <span class="vintage" style="font-family:var(--mono);font-size:8pt;color:#888">doc_id: ${escapeHtml(id)}</span>
            </div>
          </li>`;
        }).join("")}
      </ol>
    </section>

    <section class="r-section">
      <h2>7 · Methodology &amp; honest scope</h2>
      <div class="r-method">
        <p><strong>This is an exposure briefing, not a damage probability or insurance rating.</strong> Tier and headline statistics are computed from a deterministic, peer-reviewed-grounded rubric (see <em>METHODOLOGY.md</em> in the source repository). The synthesis prose is generated by IBM Granite 4.1 in document-grounded mode; every numeric claim is verified to appear verbatim in a source document before render, and unsupported sentences are dropped.</p>
        <p><strong>Stack:</strong> Granite 4.1 (3b planner / 8b reconciler) via Ollama, Granite Embedding 278M for RAG over agency reports, Granite TimeSeries TTM r2 for live surge nowcast, Prithvi-EO 2.0 for satellite-derived flood polygons (offline pre-computed). Apache-2.0 across the stack. Inference runs locally on the deploying machine; no vendor LLM is contacted at runtime.</p>
        <p><strong>Out of scope:</strong> engineering vulnerability (foundation/structural fragility), social capacity, financial absorption, sub-surface flooding (basement apartments, subway entrances). Datasets are vintage-bounded as noted per source above.</p>
      </div>
    </section>

    <footer class="r-foot">
      <span>Generated by Riprap · https://huggingface.co/spaces/msradam/riprap-nyc</span>
      <span>${escapeHtml(pkg.finishedAt || "")}</span>
    </footer>
  `;
  document.getElementById("paper").innerHTML = html;
  // Update tab title to reflect the subject
  document.title = `Riprap — ${place}`;
}

// Subset markdown for the briefing: `**Header.**` lines → <h4>; `- ` lines
// → <ul><li>; inline `**foo**` → <strong>; rest → <p>. Keep parity with
// agent.js's renderMarkdown so reports look like the live UI.
function renderBriefingMarkdown(text) {
  const lines = text.split("\n");
  const out = [];
  let para = []; let bullets = [];
  const flushPara = () => {
    if (!para.length) return;
    const safe = para.join(" ").trim().replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    if (safe) out.push(`<p>${safe}</p>`);
    para = [];
  };
  const flushBullets = () => {
    if (!bullets.length) return;
    const items = bullets.map(b => {
      const safe = b.trim().replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
      return `<li>${safe}</li>`;
    }).join("");
    out.push(`<ul>${items}</ul>`);
    bullets = [];
  };
  // Pre-split inline-bullet runs that Granite occasionally emits as one line
  const expanded = [];
  for (const line of lines) {
    if (line.trim().startsWith("- ") && line.includes(" - ", 2)) {
      const parts = line.split(/(?:^|(?<=\.\s))\s*-\s+/g).filter(p => p.trim());
      for (const p of parts) expanded.push("- " + p.trim());
    } else { expanded.push(line); }
  }
  for (const line of expanded) {
    const m = line.match(/^\s*\*\*([A-Z][A-Za-z\s/]+)\.\*\*\s*$/);
    if (m) {
      flushPara(); flushBullets();
      out.push(`<h4>${m[1]}</h4>`);
    } else if (/^\s*[-*]\s+/.test(line)) {
      flushPara();
      bullets.push(line.replace(/^\s*[-*]\s+/, ""));
    } else {
      flushBullets();
      para.push(line);
    }
  }
  flushPara(); flushBullets();
  return out.join("");
}
