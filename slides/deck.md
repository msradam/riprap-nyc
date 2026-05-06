---
marp: true
theme: riprap
paginate: true
size: 16:9
title: Riprap. Citation-grounded NYC flood briefings.
description: AMD x lablab.ai Developer Hackathon, May 4–10 2026
---

<!-- _class: lead -->
<!-- _paginate: false -->

<img class="lead-mark" src="logo.svg" alt="Riprap dam mark" />

<div class="eyebrow" style="padding-top: 132px;">
  AMD &times; lablab.ai &nbsp;·&nbsp; Developer Hackathon
</div>

# Riprap

## Citation-grounded NYC flood-exposure briefings, on AMD MI300X.

<div class="meta">
  <div>
    <div class="meta-label">Engine</div>
    <div class="meta-value">vLLM &middot; Granite 4.1 8B</div>
  </div>
  <div class="meta-divider"></div>
  <div>
    <div class="meta-label">Hardware</div>
    <div class="meta-value">AMD MI300X</div>
  </div>
  <div>
    <div class="meta-label">Date</div>
    <div class="meta-value">May 4&ndash;10 2026</div>
  </div>
</div>

---

<div class="eyebrow">01 &middot; The problem</div>

# Climate risk data is a black box.

<div class="box-grid cols-2">

<div class="box">
  <div class="lbl">The market</div>
  <div class="body">
    <strong>First Street.</strong> Score 1&ndash;10.<br>
    <strong>ClimateCheck.</strong> Score 1&ndash;100.<br>
    <strong>Jupiter.</strong> Enterprise SaaS.<br>
    <br>
    A number. A bar chart. A black box.
  </div>
</div>

<div class="box tinted">
  <div class="lbl">Nov 14&middot;2025 &middot; CNN / TechCrunch (paraphrase)</div>
  <div class="body" style="font-size: 19px; line-height: 1.4;">
    Zillow removed climate risk scores from listings under pressure from the real-estate industry. In their place: a link, far less visible.
  </div>
</div>

</div>

<p style="margin-top: 20px; font-size: 22px;">When a number meets resistance, <strong>the only defense is the audit trail.</strong></p>

<p style="margin-top: 4px; font-size: 18px; color: var(--ink-3);">Riprap is not a property-risk score. It is the audit trail behind one.</p>

---

<div class="eyebrow">02 &middot; SOLUTION</div>

# A flood-exposure briefing for any place in New York City.

<p style="margin-bottom: 14px; font-size: 20px; max-width: 72ch; color: var(--ink-2);">Type an address or neighborhood. Get a written briefing in 5&ndash;13 seconds, fusing four temporal modes &mdash; Sandy 2012 inundation, current 311 history, FloodNet sensor reads, NPCC4 projections &mdash; into one cited paragraph.</p>

<div style="border: 2px dashed #94A3B8; background: #E8ECF2; display: flex; align-items: center; justify-content: center; height: 280px; border-radius: 2px; margin-bottom: 10px;">
  <p style="font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-3); text-align: center; margin: 0; padding: 24px;">
    [ screenshot of riprap.nyc landing &mdash; to be added ]
  </p>
</div>

<p style="font-size: 15px; color: var(--ink-3); margin: 0;">Behind the prose: every numeric claim links to its primary public-record source. Mellea rejection sampling refuses to publish what it can&rsquo;t cite.</p>

---

<div class="eyebrow">03 &middot; The civic-tech case</div>

# The civic-tech case.

<div class="box-grid cols-2">

<div class="box">
  <div class="lbl">NY Property Disclosure Law</div>
  <div class="body">March 2024. Sellers must disclose flood history. <strong>Riprap is the citable narrative.</strong></div>
</div>

<div class="box">
  <div class="lbl">NYC DEP Stormwater Plan</div>
  <div class="body">2024. $30B priority list, 86 sites. <strong>Riprap is the per-NTA evidence layer.</strong></div>
</div>

<div class="box">
  <div class="lbl">EJNYC Flood Vulnerability Index</div>
  <div class="body">2024. 35% of state climate spend goes to "disadvantaged communities." <strong>Riprap stays open-source so advocacy can audit.</strong></div>
</div>

<div class="box dark">
  <div class="lbl">No commercial APIs</div>
  <div class="body">Every dataset is public-record federal, state, or city. Every foundation model is Apache-2.0. <strong>Every claim cites its source.</strong></div>
</div>

</div>

---

<div class="eyebrow">04 &middot; Architecture</div>

# Five Stones fan out. One cited briefing comes back.

<p style="margin: 4px 0 10px; font-size: 17px; color: var(--ink-3); font-family: var(--font-mono);">query &rarr; <strong style="color: var(--ink);">Planner</strong> (Granite 4.1 3B, intent classification) &rarr; Stone roster &rarr; <strong style="color: var(--ink);">Capstone</strong> (Granite 4.1 8B + Mellea) &rarr; briefing</p>

<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 0;">

  <div style="background: var(--paper-deep); border: 1px solid var(--rule-soft); border-top: 3px solid #475569; padding: 12px 14px; display: flex; flex-direction: column; gap: 4px;">
    <div style="display: flex; justify-content: space-between; align-items: baseline;">
      <span style="font-family: var(--font-mono); font-size: 9px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #475569;">Cornerstone · USGS 3DEP</span>
      <span style="font-family: var(--font-mono); font-size: 9px; color: var(--ink-3);">2020</span>
    </div>
    <div style="font-size: 13px; font-weight: 600; color: var(--ink); line-height: 1.2; margin-bottom: 4px;">Microtopography (HAND / TWI)</div>
    <div style="display: grid; grid-template-columns: auto 1fr; gap: 2px 8px;">
      <span style="font-family: var(--font-mono); font-size: 9px; color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.08em;">HAND</span><span style="font-family: var(--font-mono); font-size: 13px; font-weight: 700; color: #475569;">0.82 m</span>
      <span style="font-family: var(--font-mono); font-size: 9px; color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.08em;">TWI</span><span style="font-family: var(--font-mono); font-size: 13px; font-weight: 700; color: #475569;">14.3</span>
      <span style="font-family: var(--font-mono); font-size: 9px; color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.08em;">Elev.</span><span style="font-family: var(--font-mono); font-size: 13px; font-weight: 700; color: #475569;">2.1 m MSL</span>
      <span style="font-family: var(--font-mono); font-size: 9px; color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.08em;">Pct. lower</span><span style="font-family: var(--font-mono); font-size: 13px; font-weight: 700; color: #475569;">78%</span>
    </div>
    <div style="margin-top: 8px; padding-top: 6px; border-top: 1px solid var(--rule-soft); font-family: var(--font-mono); font-size: 10px; color: #475569; font-weight: 600;">[topo]</div>
  </div>

  <div style="background: var(--paper-deep); border: 1px solid var(--rule-soft); border-top: 3px solid #1A4480; padding: 12px 14px; display: flex; flex-direction: column; gap: 4px;">
    <div style="display: flex; justify-content: space-between; align-items: baseline;">
      <span style="font-family: var(--font-mono); font-size: 9px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #1A4480;">Keystone · TerraMind-NYC</span>
      <span style="font-family: var(--font-mono); font-size: 9px; color: var(--ink-3);">2024</span>
    </div>
    <div style="font-size: 13px; font-weight: 600; color: var(--ink); line-height: 1.2; margin-bottom: 4px;">Building footprint coverage</div>
    <div style="margin: 6px 0;">
      <div style="font-family: var(--font-mono); font-size: 30px; font-weight: 700; color: #1A4480; line-height: 1;">48.41<span style="font-size: 16px;">%</span></div>
      <div style="font-family: var(--font-mono); font-size: 10px; color: var(--ink-3); margin-top: 3px;">250 m radius &middot; Buildings LoRA adapter</div>
    </div>
    <div style="margin-top: 8px; padding-top: 6px; border-top: 1px solid var(--rule-soft); font-family: var(--font-mono); font-size: 10px; color: #1A4480; font-weight: 600;">[keystone_bldg]</div>
  </div>

  <div style="background: var(--paper-deep); border: 1px solid var(--rule-soft); border-top: 3px solid #0E7490; padding: 12px 14px; display: flex; flex-direction: column; gap: 4px;">
    <div style="display: flex; justify-content: space-between; align-items: baseline;">
      <span style="font-family: var(--font-mono); font-size: 9px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #0E7490;">Touchstone · NYC 311</span>
      <span style="font-family: var(--font-mono); font-size: 9px; color: var(--ink-3);">live</span>
    </div>
    <div style="font-size: 13px; font-weight: 600; color: var(--ink); line-height: 1.2; margin-bottom: 4px;">Flood complaints · 200 m buffer</div>
    <div style="margin: 4px 0;">
      <svg viewBox="0 0 220 60" style="width:100%; display:block;">
        <rect x="8" y="52" width="212" height="1" fill="#CBD5E1"/>
        <rect x="12" y="35" width="28" height="17" fill="#0E7490" rx="1"/>
        <rect x="54" y="18" width="28" height="34" fill="#0E7490" rx="1"/>
        <rect x="96" y="10" width="28" height="42" fill="#0E7490" rx="1"/>
        <rect x="138" y="10" width="28" height="42" fill="#0E7490" rx="1"/>
        <rect x="180" y="27" width="28" height="25" fill="#0E7490" rx="1"/>
        <text x="26" y="32" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="8" fill="#0E7490">2</text>
        <text x="68" y="15" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="8" fill="#0E7490">4</text>
        <text x="110" y="7" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="8" fill="#0E7490">5</text>
        <text x="152" y="7" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="8" fill="#0E7490">5</text>
        <text x="194" y="24" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="8" fill="#0E7490">3</text>
        <text x="26" y="59" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="7" fill="#94A3B8">'19</text>
        <text x="68" y="59" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="7" fill="#94A3B8">'20</text>
        <text x="110" y="59" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="7" fill="#94A3B8">'21</text>
        <text x="152" y="59" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="7" fill="#94A3B8">'22</text>
        <text x="194" y="59" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="7" fill="#94A3B8">'23</text>
      </svg>
      <div style="font-family: var(--font-mono); font-size: 10px; color: var(--ink-3);">19 requests &middot; 5-yr lookback</div>
    </div>
    <div style="margin-top: 8px; padding-top: 6px; border-top: 1px solid var(--rule-soft); font-family: var(--font-mono); font-size: 10px; color: #0E7490; font-weight: 600;">[nyc311]</div>
  </div>

  <div style="background: var(--paper-deep); border: 1px solid var(--rule-soft); border-top: 3px solid #92400E; padding: 12px 14px; display: flex; flex-direction: column; gap: 4px;">
    <div style="display: flex; justify-content: space-between; align-items: baseline;">
      <span style="font-family: var(--font-mono); font-size: 9px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #92400E;">Lodestone · Granite TTM r2</span>
      <span style="font-family: var(--font-mono); font-size: 9px; color: var(--ink-3);">live</span>
    </div>
    <div style="font-size: 13px; font-weight: 600; color: var(--ink); line-height: 1.2; margin-bottom: 4px;">Surge residual nowcast</div>
    <div style="margin: 4px 0;">
      <svg viewBox="0 0 220 60" style="width:100%; display:block;">
        <path d="M10,40 35,30 60,19 85,16 110,21 135,27 160,34 185,40 210,45 L210,52 L10,52 Z" fill="#92400E" opacity="0.12"/>
        <rect x="8" y="52" width="212" height="1" fill="#CBD5E1"/>
        <line x1="60" y1="19" x2="60" y2="52" stroke="#92400E" stroke-width="1" stroke-dasharray="3,2" opacity="0.6"/>
        <polyline points="10,40 35,30 60,19 85,16 110,21 135,27 160,34 185,40 210,45" fill="none" stroke="#92400E" stroke-width="2" stroke-linejoin="round"/>
        <circle cx="60" cy="19" r="3" fill="#92400E"/>
        <text x="65" y="17" font-family="IBM Plex Mono,monospace" font-size="8" fill="#92400E" font-weight="700">0.22 ft</text>
        <text x="10" y="59" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="7" fill="#94A3B8">0h</text>
        <text x="60" y="59" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="7" fill="#92400E">NOW</text>
        <text x="110" y="59" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="7" fill="#94A3B8">4.8h</text>
        <text x="210" y="59" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="7" fill="#94A3B8">9.6h</text>
      </svg>
      <div style="font-family: var(--font-mono); font-size: 10px; color: var(--ink-3);">peak surge residual &middot; 9.6 h horizon</div>
    </div>
    <div style="margin-top: 8px; padding-top: 6px; border-top: 1px solid var(--rule-soft); font-family: var(--font-mono); font-size: 10px; color: #92400E; font-weight: 600;">[ttm_surge]</div>
  </div>

</div>

<p style="margin-top: 8px; font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-3);">Real evidence cards rendered by the live system &nbsp;&middot;&nbsp; 442 East Houston Street, Manhattan.</p>

<div class="box" style="border-top: 3px solid #162E51; margin-top: 10px; padding: 12px 18px;">
  <span style="font-family: var(--font-mono); font-size: 10px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: #162E51;">Capstone</span>
  <span style="font-size: 16px; color: var(--ink-2); margin-left: 14px;">Granite 4.1 8B + Mellea rejection sampling &nbsp;&middot;&nbsp; <code>numerics_grounded</code> &middot; <code>no_placeholder_tokens</code> &middot; <code>citations_dense</code> &middot; <code>citations_resolve</code> &nbsp;&middot;&nbsp; reroll until resolved &nbsp;&rarr;&nbsp; <strong>cited 4-section briefing</strong></span>
</div>

---

<div class="eyebrow">05 &middot; Fine-Tuning on AMD MI300X</div>

# Three Apache-2.0 NYC fine-tunes on MI300X.

<div class="box-grid cols-3" style="margin-top: 12px; gap: 14px;">

<div class="box" style="border-top: 3px solid #0E7490; padding: 18px 18px 16px;">
  <div class="lbl" style="color: #0E7490; margin-bottom: 6px;">Prithvi-EO-2.0-NYC-Pluvial</div>
  <div style="font-size: 14px; color: var(--ink-2); margin-bottom: 12px;">Hurricane Ida pluvial flood detection from Sentinel-2</div>
  <div style="font-family: var(--font-mono); font-size: 22px; font-weight: 700; color: var(--ink); letter-spacing: -0.02em;">0.5979</div>
  <div style="font-family: var(--font-mono); font-size: 11px; color: var(--ink-3); margin-bottom: 10px;">test flood IoU &nbsp;·&nbsp; 6&times; lift over Sen1Floods11 baseline</div>
  <div style="font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3);">MI300X &middot; AMD Developer Cloud</div>
</div>

<div class="box" style="border-top: 3px solid #1A4480; padding: 18px 18px 16px;">
  <div class="lbl" style="color: #1A4480; margin-bottom: 6px;">TerraMind-NYC-Adapters</div>
  <div style="font-size: 14px; color: var(--ink-2); margin-bottom: 12px;">LULC + Buildings + TiM LoRA adapters for NYC</div>
  <div style="font-family: var(--font-mono); font-size: 22px; font-weight: 700; color: var(--ink); letter-spacing: -0.02em;">+6.13<span style="font-size: 15px;">pp</span></div>
  <div style="font-family: var(--font-mono); font-size: 11px; color: var(--ink-3); margin-bottom: 10px;">LULC mIoU over full-FT baseline &nbsp;·&nbsp; mIoU 0.5866</div>
  <div style="font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3);">~18 min total &middot; MI300X</div>
</div>

<div class="box" style="border-top: 3px solid #92400E; padding: 18px 18px 16px;">
  <div class="lbl" style="color: #92400E; margin-bottom: 6px;">Granite-TTM-r2-Battery-Surge</div>
  <div style="font-size: 14px; color: var(--ink-2); margin-bottom: 12px;">NOAA Battery tide gauge 96h surge residual nowcast</div>
  <div style="font-family: var(--font-mono); font-size: 22px; font-weight: 700; color: var(--ink); letter-spacing: -0.02em;">0.157<span style="font-size: 15px;">m</span></div>
  <div style="font-family: var(--font-mono); font-size: 11px; color: var(--ink-3); margin-bottom: 10px;">RMSE &nbsp;·&nbsp; &minus;35% vs persistence baseline</div>
  <div style="font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3);">MI300X &middot; Apache-2.0 &middot; HF Hub</div>
</div>

</div>

<p style="margin-top: 18px; font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-3);">Track submitted: Fine-Tuning on AMD GPUs &nbsp;&middot;&nbsp; All three models Apache-2.0, published on HF Hub</p>

---

<div class="eyebrow">06 &middot; DEMO</div>

# Live demo.

<div style="margin: 48px 0 32px; text-align: center;">
  <p style="font-family: var(--font-mono); font-size: 28px; font-weight: 700; color: var(--ink); margin: 0 auto; max-width: 860px; line-height: 1.35;">&ldquo;I&rsquo;m thinking about renting an apartment at 80 Pioneer Street, Brooklyn. Should I worry?&rdquo;</p>
</div>

<div style="text-align: center; margin-bottom: 40px;">
  <span style="font-family: var(--font-mono); font-size: 20px; letter-spacing: 0.06em; color: var(--accent); font-weight: 700;">riprap.nyc</span>
</div>

<p style="text-align: center; font-family: var(--font-mono); font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-3); margin: 0 auto; max-width: none;">13 seconds end-to-end &nbsp;&middot;&nbsp; 4/4 grounding checks &nbsp;&middot;&nbsp; all sources public-record</p>

---

<div class="eyebrow">07 &middot; What's next</div>

# What's next.

<p style="margin-bottom: 14px; font-size: 18px; color: var(--ink-3); font-family: var(--font-mono); letter-spacing: 0.02em;">The architecture is NYC-specific by data choice, not by code.</p>

<div class="box-grid cols-3" style="margin-top: 0;">

<div class="box">
  <div class="lbl">Break out the Stones</div>
  <div class="body">Each Stone is a coherent composition over data sources, models, and deterministic checks. Extract Cornerstone, Touchstone, Keystone, Lodestone as independent packages; any civic-tech project can pull one Stone without the full Riprap stack.</div>
</div>

<div class="box">
  <div class="lbl">Other flood-impacted cities</div>
  <div class="body">Houston (Harvey, Beryl), Miami (king tides), Boston (CSO floods), Jakarta, Manila, Dhaka &mdash; the same five-Stone pattern, different probe sets and RAG corpora per city.</div>
</div>

<div class="box tinted">
  <div class="lbl">Historical-event mode</div>
  <div class="body">Re-run the FSM with snapshot data from any past date. Validate the system against measured outcomes &mdash; what would Riprap have said before Sandy, before Ida, before the 2024 Beryl remnants. Calibration as a first-class feature.</div>
</div>

</div>

---

<!-- _class: cta -->

<img class="cta-mark" src="logo-paper.svg" alt="Riprap dam mark" />

<div class="eyebrow" style="margin-top: 124px; color: var(--accent); border: 0; padding: 0;">Riprap &middot; flood briefings on AMD</div>

<h1 style="white-space: nowrap; font-size: 72px;">github.com/msradam/riprap-nyc</h1>

<hr>

<p style="font-family: var(--font-mono); font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase;">
Apache-2.0 &middot; public data &middot; AMD MI300X &middot; IBM Granite 4.1 &middot; Mellea grounding
</p>

<p style="font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: rgba(244,246,249,0.55); margin-top: 16px;">
AMD &times; lablab.ai &middot; May 4&ndash;10 2026
</p>

<p style="font-family: var(--font-mono); font-size: 9.5px; letter-spacing: 0.08em; color: rgba(244,246,249,0.4); margin-top: 24px; text-transform: none;">
Dam mark: "Dam" by Chintuza via the Noun Project, CC-BY 3.0.
</p>

---

<!-- _paginate: false -->

<div class="eyebrow">Appendix &middot; The receipts</div>

# 5 of 5 NYC addresses. Every claim verified, every run.

<table>
  <thead>
    <tr><th>address</th><th>intent</th><th>wall</th><th>steps</th><th>verified</th></tr>
  </thead>
  <tbody>
    <tr><td>442 E Houston St &middot; LES</td><td>address</td><td>7.6 s</td><td>19</td><td>4/4</td></tr>
    <tr><td>80 Pioneer St &middot; Red Hook</td><td>address</td><td>13.1 s</td><td>19</td><td>4/4</td></tr>
    <tr><td>100 Gold St &middot; Manhattan</td><td>address</td><td>11.2 s</td><td>19</td><td>4/4</td></tr>
    <tr><td>Hollis &middot; Queens</td><td>nbhd</td><td>5.8 s</td><td>9</td><td>4/4</td></tr>
    <tr><td>Coney Island &middot; Brooklyn</td><td>nbhd</td><td>9.9 s</td><td>9</td><td>4/4</td></tr>
  </tbody>
</table>

<div class="box-grid cols-3" style="margin-top: 16px;">
  <div class="box">
    <div class="lbl">Wall-clock</div>
    <div class="stat-value">5.8&ndash;13.1<span style="font-size: 22px; color: var(--ink-3); font-weight: 400; letter-spacing: 0;"> s</span></div>
    <div class="stat-label">vLLM on MI300X</div>
  </div>
  <div class="box">
    <div class="lbl">Stones</div>
    <div class="stat-value">5</div>
    <div class="stat-label">evidence layers per briefing</div>
  </div>
  <div class="box">
    <div class="lbl">Verified</div>
    <div class="stat-value">4 / 4</div>
    <div class="stat-label">source checks every run</div>
  </div>
</div>
