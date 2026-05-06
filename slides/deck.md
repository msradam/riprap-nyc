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

<div class="eyebrow">02 &middot; What riprap is</div>

# Every number cites its source. Or it doesn't appear.

<p style="margin-bottom: 12px;">Type a NYC address &rarr; <strong>five Stones</strong> fan out across NYC's flood evidence &rarr; one paragraph back, with <code>[doc_id]</code> citations on every numeric claim.</p>

<div class="codeblock"><span class="label">Status.</span> 442 East Houston Street, Manhattan, is exposed to flood risk: flooded by Hurricane Sandy in 2012, with recurrent localized flooding evidenced by 19 311 complaints and multiple FloodNet sensor events <span class="cite">[sandy], [nyc311], [floodnet]</span>.

<span class="label">Empirical evidence.</span> Sandy flooded this address Oct 29-30, 2012 <span class="cite">[sandy]</span>. 19 flood-related 311 service requests within 200 m over five years <span class="cite">[nyc311]</span>. Three of five FloodNet sensors within 600 m documented events in the past three years <span class="cite">[floodnet]</span>.</div>

<p style="margin-top: 8px; font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-3);">Hallucination guard &middot; four source-binding checks &middot; reroll until every claim resolves</p>

---

<div class="eyebrow">03 &middot; Architecture</div>

# Five Stones fan out. One cited briefing comes back.

<p style="margin: 4px 0 10px; font-size: 17px; color: var(--ink-3); font-family: var(--font-mono);">query &rarr; <strong style="color: var(--ink);">Planner</strong> (Granite 4.1 3B, intent classification) &rarr; Stone roster &rarr; <strong style="color: var(--ink);">Capstone</strong> (Granite 4.1 8B + Mellea) &rarr; briefing</p>

<div class="box-grid cols-4" style="margin-top: 0; gap: 10px;">

<div class="box" style="border-top: 3px solid #475569; padding: 14px 16px;">
  <div class="lbl" style="color: #475569;">Cornerstone</div>
  <div style="font-size: 14px; font-weight: 600; color: var(--ink); margin-bottom: 6px;">Hazard Reader</div>
  <div style="font-family: var(--font-mono); font-size: 12px; color: var(--ink-3); line-height: 1.5;">Sandy 2012 zone<br>DEP stormwater<br>Ida USGS HWMs<br>Prithvi-EO · LiDAR</div>
</div>

<div class="box" style="border-top: 3px solid #1A4480; padding: 14px 16px;">
  <div class="lbl" style="color: #1A4480;">Keystone</div>
  <div style="font-size: 14px; font-weight: 600; color: var(--ink); margin-bottom: 6px;">Asset Register</div>
  <div style="font-family: var(--font-mono); font-size: 12px; color: var(--ink-3); line-height: 1.5;">NYCHA · DOE · MTA<br>NYS hospitals<br>TerraMind-NYC<br>Buildings adapter</div>
</div>

<div class="box" style="border-top: 3px solid #0E7490; padding: 14px 16px;">
  <div class="lbl" style="color: #0E7490;">Touchstone</div>
  <div style="font-size: 14px; font-weight: 600; color: var(--ink); margin-bottom: 6px;">Live Observer</div>
  <div style="font-family: var(--font-mono); font-size: 12px; color: var(--ink-3); line-height: 1.5;">FloodNet sensors<br>NYC 311 history<br>NOAA tide gauge<br>NWS METAR</div>
</div>

<div class="box" style="border-top: 3px solid #92400E; padding: 14px 16px;">
  <div class="lbl" style="color: #92400E;">Lodestone</div>
  <div style="font-size: 14px; font-weight: 600; color: var(--ink); margin-bottom: 6px;">Projector</div>
  <div style="font-family: var(--font-mono); font-size: 12px; color: var(--ink-3); line-height: 1.5;">NWS alerts<br>Granite TTM r2<br>surge nowcast<br>311 recurrence</div>
</div>

</div>

<div class="box" style="border-top: 3px solid #162E51; margin-top: 10px; padding: 12px 18px;">
  <span style="font-family: var(--font-mono); font-size: 10px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: #162E51;">Capstone</span>
  <span style="font-size: 16px; color: var(--ink-2); margin-left: 14px;">Granite 4.1 8B + Mellea rejection sampling &nbsp;&middot;&nbsp; <code>numerics_grounded</code> &middot; <code>no_placeholder_tokens</code> &middot; <code>citations_dense</code> &middot; <code>citations_resolve</code> &nbsp;&middot;&nbsp; reroll until resolved &nbsp;&rarr;&nbsp; <strong>cited 4-section briefing</strong></span>
</div>

---

<div class="eyebrow">04 &middot; The track</div>

# Submitted to Fine-Tuning on AMD GPUs.

<p style="margin-bottom: 8px; font-size: 20px;">The work spans three tracks. The Fine-Tuning evidence is the strongest: three Apache-2.0 NYC models trained on AMD MI300X, published on HF Hub.</p>

<div class="track-row engaged">
  <div class="check">▸</div>
  <div class="name">Fine-Tuning</div>
  <div class="detail"><strong>Submitting here.</strong> Prithvi-EO-2.0-NYC-Pluvial &middot; TerraMind-NYC-Adapters &middot; Granite-TTM-r2-Battery-Surge &middot; trained on MI300X &middot; Apache-2.0 &middot; live on HF Hub</div>
  <div class="badge">Primary</div>
</div>

<div class="track-row engaged">
  <div class="check">▸</div>
  <div class="name">Agents &amp; Agentic Workflows</div>
  <div class="detail">Burr FSM &middot; five-Stone evidence taxonomy &middot; Planner classifies intent and routes to the right Stone roster &middot; Mellea rejection-sampling guard on every reconcile</div>
  <div class="badge">Supporting</div>
</div>

<div class="track-row engaged">
  <div class="check">▸</div>
  <div class="name">Vision &amp; Multimodal</div>
  <div class="detail">Sentinel-2 chip &rarr; Prithvi pluvial segmentation &middot; TerraMind LULC + Buildings adapters &middot; Granite Embedding 278M retrieval &middot; GLiNER typed extraction</div>
  <div class="badge">Supporting</div>
</div>

---

<div class="eyebrow">05 &middot; The receipts</div>

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

---

<div class="eyebrow">06 &middot; Why it matters</div>

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

<div class="eyebrow">07 &middot; What's next</div>

# The longer arc.

<div class="box-grid cols-3" style="margin-top: 16px;">

<div class="box">
  <div class="lbl">Ida calibration &middot; ASCE NY</div>
  <div class="body">Run the FSM backward against August 31, 2021 snapshot data. Validate Cornerstone + Lodestone outputs against measured Ida inundation. Presentation target: ASCE NY section, May 2026.</div>
</div>

<div class="box">
  <div class="lbl">Stones v1.1 &middot; standalone packages</div>
  <div class="body">Publish Cornerstone, Touchstone, Keystone, Lodestone as independent Python packages. Any NYC civic-tech project can pull one Stone without the full Riprap stack.</div>
</div>

<div class="box tinted">
  <div class="lbl">Methodology paper</div>
  <div class="body">The citation-grounding pipeline (Mellea rejection sampling + four invariants + reroll feedback) as a replicable pattern for any geospatial LLM. Targets MDPI Sustainability or similar open-access venue.</div>
</div>

</div>

<p style="margin-top: 20px; font-size: 20px; color: var(--ink-2);">The architecture is NYC-specific by data choice, not by code. Houston (Harvey + Beryl 2024), Miami (king tides), Boston (CSO floods) are the next cities.</p>

---

<!-- _class: cta -->

<img class="cta-mark" src="logo-paper.svg" alt="Riprap dam mark" />

<div class="eyebrow" style="margin-top: 124px; color: var(--accent); border: 0; padding: 0;">Riprap &middot; flood briefings on AMD</div>

# riprap.nyc

## github.com/msradam/riprap-nyc

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
