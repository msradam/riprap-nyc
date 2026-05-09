---
marp: true
theme: riprap
paginate: true
size: 16:9
title: Riprap. Flood risk analysis for any NYC address.
description: AMD x lablab.ai Developer Hackathon, May 4–10 2026
---

<!-- _class: lead -->
<!-- _paginate: false -->

<img class="lead-mark" src="logo.svg" alt="Riprap dam mark" />

<div class="eyebrow" style="padding-top: 132px;">
  AMD &times; LABLAB.AI &nbsp;·&nbsp; DEVELOPER HACKATHON
</div>

# Riprap

## Flood risk analysis for any NYC address.

<p style="font-size: 22px; color: var(--ink-2); max-width: 680px; margin: 0 0 32px;">Powered by a multi-agent AI system that reads satellites, watches sensors, forecasts surges, and refuses to stay silent.</p>

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

<div class="eyebrow">01 &middot; INTRO</div>

<div style="display: grid; grid-template-columns: 320px 1fr; gap: 48px; align-items: center; margin-top: 20px; height: 450px;">

<div style="display: flex; flex-direction: column; justify-content: center; align-items: center;">
  <img src="assets/adam.jpg" style="width: 300px; height: 300px; border-radius: 50%; object-fit: cover; border: 3px solid #162E51;" />
</div>

<div style="display: flex; flex-direction: column; justify-content: center;">
  <h1 style="margin: 0 0 14px; font-size: 52px;">Hi! I'm Adam. 👋</h1>
  <p style="font-size: 17px; color: var(--ink-2); margin: 0 0 12px; line-height: 1.55;"><strong>Staff Software Engineer at IBM.</strong> <strong>MS Computer Engineering at NYU.</strong></p>
  <p style="font-size: 17px; color: var(--ink-2); margin: 0 0 12px; line-height: 1.55;">I build <strong>civic-tech systems</strong> for places where infrastructure fails the people who live there. Previous projects ran AI locally for refugee field offices, accessibility routing in five boroughs, and offline geospatial analysis on Raspberry Pi.</p>
  <p style="font-size: 17px; color: var(--ink-2); margin: 0 0 20px; line-height: 1.55;">Riprap is the <strong>third hackathon I've built civic-tech AI for in six months.</strong> The discipline carries: <strong>open-source, public-record, runs where the people are.</strong></p>
  <p style="font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.1em; color: var(--ink-3);">github.com/msradam &nbsp;&middot;&nbsp; linkedin.com/in/adamsrahman</p>
</div>

</div>

---

<div class="eyebrow">02 &middot; The problem</div>

# Sandy killed 43 New Yorkers in 2012. Ida killed 13 in basement apartments in 2021.

<p style="font-size: 20px; color: var(--ink-2); max-width: 820px; margin: 8px 0 16px;">The flood evidence existed both times. Scattered across eight public-record sources: FEMA, USGS, NOAA, NYC DEP, FloodNet, NYC 311, NWS, NPCC4. None of it reached the people exposed in a form they could read.</p>

<div class="box-grid cols-2">

<div class="box">
  <div class="lbl">Eight sources. Zero synthesis.</div>
  <div class="body">
    Sandy inundation zones. Ida high-water marks. DEP stormwater scenarios. FloodNet sensor records. 311 flood complaints. NWS alerts. NOAA tide gauges. NPCC4 sea-level projections.<br><br>
    Public record. Unread.
  </div>
</div>

<div class="box tinted">
  <div class="lbl">Nov 14&middot;2025 &middot; CNN / TechCrunch (paraphrase)</div>
  <div class="body" style="font-size: 19px; line-height: 1.4;">
    Zillow removed climate risk scores from listings under pressure from the real-estate industry. In their place: a link, far less visible.
  </div>
</div>

</div>

<p style="margin-top: 20px; font-size: 22px;">When a number meets resistance, <strong>the only defense is the audit trail.</strong> <span style="white-space: nowrap;">Riprap is the audit trail.</span></p>

---

<div class="eyebrow">03 &middot; What Riprap does</div>

<h1 style="font-size: 36px; margin: 4px 0 4px;">A flood-exposure briefing for any place in NYC.</h1>

<p style="margin: 0 0 8px; font-size: 16px; color: var(--ink-2);">Type an address. Get a cited briefing in 5&ndash;13 seconds, fusing satellite imagery, sensor data, modeled scenarios, and projections.</p>

<div style="border: 2px solid #94A3B8; border-radius: 2px; overflow: hidden; height: 600px;">
  <img src="../assets/screenshots/hero.png" style="width: 100%; height: 100%; object-fit: cover; object-position: top;" />
</div>

---

<div class="eyebrow">04 &middot; Civic-tech case</div>

# The citable narrative for NYC disclosure and equity.

<p style="margin: 4px 0 12px; font-size: 19px; color: var(--ink-2);">Open-source, public-record, and runs where the people are.</p>

<div class="box-grid cols-2" style="margin-top: 4px; gap: 10px;">

<div class="box" style="padding: 14px 18px;">
  <div class="lbl">NY Property Disclosure Law</div>
  <div class="body" style="font-size: 17px; line-height: 1.3;">
    Effective March 2024, sellers must disclose flood history. Riprap provides the citable narrative that makes these disclosures meaningful.
  </div>
</div>

<div class="box" style="padding: 14px 18px;">
  <div class="lbl">DEP Stormwater Priority</div>
  <div class="body" style="font-size: 17px; line-height: 1.3;">
    The DEP's $30 billion stormwater plan covers 86 sites. Riprap provides the evidence layer that backs up these infrastructure rankings.
  </div>
</div>

<div class="box" style="padding: 14px 18px;">
  <div class="lbl">EJNYC Flood Vulnerability</div>
  <div class="body" style="font-size: 17px; line-height: 1.3;">
    Environmental Justice (EJ) advocates can audit the same system used by developers. No commercial gatekeeping or proprietary scores.
  </div>
</div>

<div class="box tinted" style="padding: 14px 18px;">
  <div class="lbl">No Commercial APIs</div>
  <div class="body" style="font-size: 17px; line-height: 1.3;">
    Every model is Apache-2.0. Every dataset is public record. Built to run on local infrastructure without recurring data costs.
  </div>
</div>

</div>

---

<div class="eyebrow">05 &middot; Architecture</div>

# Five specialist agents fan out. One cited briefing comes back.

<p style="margin: 2px 0 8px; font-size: 16px; color: var(--ink-3); font-family: var(--font-mono);">query &rarr; <strong style="color: var(--ink);">Planner</strong> (Granite 4.1 3B) &rarr; Stone roster &rarr; <strong style="color: var(--ink);">Capstone</strong> (Granite 4.1 8B) &rarr; briefing</p>

<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 0;">

  <div style="background: var(--paper-deep); border: 1px solid var(--rule-soft); border-top: 3px solid #475569; padding: 10px 12px; display: flex; flex-direction: column; gap: 3px;">
    <div style="display: flex; justify-content: space-between; align-items: baseline;">
      <span style="font-family: var(--font-mono); font-size: 8px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #475569;">Cornerstone</span>
      <span style="font-family: var(--font-mono); font-size: 8px; color: var(--ink-3);">2020</span>
    </div>
    <div style="font-size: 12px; font-weight: 600; color: var(--ink); line-height: 1.1; margin-bottom: 3px;">Microtopography</div>
    <div style="display: grid; grid-template-columns: auto 1fr; gap: 1px 6px;">
      <span style="font-family: var(--font-mono); font-size: 8px; color: var(--ink-3); text-transform: uppercase;">HAND</span><span style="font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: #475569;">0.82 m</span>
      <span style="font-family: var(--font-mono); font-size: 8px; color: var(--ink-3); text-transform: uppercase;">TWI</span><span style="font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: #475569;">14.3</span>
      <span style="font-family: var(--font-mono); font-size: 8px; color: var(--ink-3); text-transform: uppercase;">Elev.</span><span style="font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: #475569;">2.1 m</span>
    </div>
    <div style="margin-top: 6px; padding-top: 4px; border-top: 1px solid var(--rule-soft); font-family: var(--font-mono); font-size: 9px; color: #475569; font-weight: 600;">[topo]</div>
  </div>

  <div style="background: var(--paper-deep); border: 1px solid var(--rule-soft); border-top: 3px solid #1A4480; padding: 10px 12px; display: flex; flex-direction: column; gap: 3px;">
    <div style="display: flex; justify-content: space-between; align-items: baseline;">
      <span style="font-family: var(--font-mono); font-size: 8px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #1A4480;">Keystone</span>
      <span style="font-family: var(--font-mono); font-size: 8px; color: var(--ink-3);">2024</span>
    </div>
    <div style="font-size: 12px; font-weight: 600; color: var(--ink); line-height: 1.1; margin-bottom: 3px;">Building footprint</div>
    <div style="margin: 4px 0;">
      <div style="font-family: var(--font-mono); font-size: 26px; font-weight: 700; color: #1A4480; line-height: 1;">48.41<span style="font-size: 14px;">%</span></div>
      <div style="font-family: var(--font-mono); font-size: 9px; color: var(--ink-3); margin-top: 2px;">TerraMind NYC</div>
    </div>
    <div style="margin-top: 6px; padding-top: 4px; border-top: 1px solid var(--rule-soft); font-family: var(--font-mono); font-size: 9px; color: #1A4480; font-weight: 600;">[keystone_bldg]</div>
  </div>

  <div style="background: var(--paper-deep); border: 1px solid var(--rule-soft); border-top: 3px solid #0E7490; padding: 10px 12px; display: flex; flex-direction: column; gap: 3px;">
    <div style="display: flex; justify-content: space-between; align-items: baseline;">
      <span style="font-family: var(--font-mono); font-size: 8px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #0E7490;">Touchstone</span>
      <span style="font-family: var(--font-mono); font-size: 8px; color: var(--ink-3);">live</span>
    </div>
    <div style="font-size: 12px; font-weight: 600; color: var(--ink); line-height: 1.1; margin-bottom: 3px;">Flood complaints</div>
    <div style="margin: 3px 0;">
      <svg viewBox="0 0 220 60" style="width:100%; display:block;">
        <rect x="8" y="52" width="212" height="1" fill="#CBD5E1"/>
        <rect x="12" y="35" width="28" height="17" fill="#0E7490" rx="1"/>
        <rect x="54" y="18" width="28" height="34" fill="#0E7490" rx="1"/>
        <rect x="96" y="10" width="28" height="42" fill="#0E7490" rx="1"/>
        <rect x="138" y="10" width="28" height="42" fill="#0E7490" rx="1"/>
        <rect x="180" y="27" width="28" height="25" fill="#0E7490" rx="1"/>
        <text x="26" y="59" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="7" fill="#94A3B8">'19</text>
        <text x="110" y="59" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="7" fill="#94A3B8">'21</text>
        <text x="194" y="59" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="7" fill="#94A3B8">'23</text>
      </svg>
    </div>
    <div style="margin-top: 6px; padding-top: 4px; border-top: 1px solid var(--rule-soft); font-family: var(--font-mono); font-size: 9px; color: #0E7490; font-weight: 600;">[nyc311]</div>
  </div>

  <div style="background: var(--paper-deep); border: 1px solid var(--rule-soft); border-top: 3px solid #92400E; padding: 10px 12px; display: flex; flex-direction: column; gap: 3px;">
    <div style="display: flex; justify-content: space-between; align-items: baseline;">
      <span style="font-family: var(--font-mono); font-size: 8px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #92400E;">Lodestone</span>
      <span style="font-family: var(--font-mono); font-size: 8px; color: var(--ink-3);">live</span>
    </div>
    <div style="font-size: 12px; font-weight: 600; color: var(--ink); line-height: 1.1; margin-bottom: 3px;">Surge residual</div>
    <div style="margin: 3px 0;">
      <svg viewBox="0 0 220 60" style="width:100%; display:block;">
        <polyline points="10,40 35,30 60,19 85,16 110,21 135,27 160,34 185,40 210,45" fill="none" stroke="#92400E" stroke-width="2" stroke-linejoin="round"/>
        <circle cx="60" cy="19" r="3" fill="#92400E"/>
      </svg>
    </div>
    <div style="margin-top: 6px; padding-top: 4px; border-top: 1px solid var(--rule-soft); font-family: var(--font-mono); font-size: 9px; color: #92400E; font-weight: 600;">[ttm_surge]</div>
  </div>

</div>

<p style="margin-top: 6px; font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-3);">Real evidence cards rendered by the live system. These are the Five Stones.</p>

<div class="box" style="border-top: 3px solid #162E51; margin-top: 6px; padding: 10px 16px;">
  <span style="font-family: var(--font-mono); font-size: 9px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: #162E51;">Capstone</span>
  <span style="font-size: 15px; color: var(--ink-2); margin-left: 12px;">Granite 4.1 8B + Mellea rejection sampling &nbsp;&middot;&nbsp; <code>grounded</code> &middot; <code>citations</code> &nbsp;&rarr;&nbsp; <strong>cited briefing</strong></span>
</div>

---

<div class="eyebrow">05 &middot; Fine-Tuning on AMD MI300X</div>

# Three Apache-2.0 NYC fine-tunes on MI300X.

<p style="margin-bottom: 10px; font-size: 18px; color: var(--ink-2);">Built for the Fine-Tuning track. All three published. All three reproducible.</p>

<div class="box-grid cols-3" style="margin-top: 12px; gap: 14px;">

<div class="box" style="border-top: 3px solid #0E7490; padding: 18px 18px 16px;">
  <div class="lbl" style="color: #0E7490; margin-bottom: 6px;">Prithvi-EO-2.0-NYC-Pluvial</div>
  <div style="font-size: 14px; color: var(--ink-2); margin-bottom: 12px;">Hurricane Ida pluvial flood detection from Sentinel-2</div>
  <div style="font-family: var(--font-mono); font-size: 22px; font-weight: 700; color: var(--ink); letter-spacing: -0.02em;">IoU 0.598</div>
  <div style="font-family: var(--font-mono); font-size: 11px; color: var(--ink-3); margin-bottom: 10px;">6&times; lift over Sen1Floods11 baseline</div>
  <div style="font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3);">MI300X &middot; AMD Developer Cloud</div>
</div>

<div class="box" style="border-top: 3px solid #1A4480; padding: 18px 18px 16px;">
  <div class="lbl" style="color: #1A4480; margin-bottom: 6px;">TerraMind-NYC-Adapters</div>
  <div style="font-size: 14px; color: var(--ink-2); margin-bottom: 12px;">LULC + Buildings + TiM LoRA adapters for NYC</div>
  <div style="font-family: var(--font-mono); font-size: 22px; font-weight: 700; color: var(--ink); letter-spacing: -0.02em;">mIoU 0.587</div>
  <div style="font-family: var(--font-mono); font-size: 11px; color: var(--ink-3); margin-bottom: 10px;">+6.13 pp over full-FT baseline &nbsp;·&nbsp; 18 min training</div>
  <div style="font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3);">MI300X</div>
</div>

<div class="box" style="border-top: 3px solid #92400E; padding: 18px 18px 16px;">
  <div class="lbl" style="color: #92400E; margin-bottom: 6px;">Granite-TTM-r2-Battery-Surge</div>
  <div style="font-size: 14px; color: var(--ink-2); margin-bottom: 12px;">NOAA Battery tide gauge 96h surge residual nowcast</div>
  <div style="font-family: var(--font-mono); font-size: 22px; font-weight: 700; color: var(--ink); letter-spacing: -0.02em;">RMSE 0.157<span style="font-size: 15px;">m</span></div>
  <div style="font-family: var(--font-mono); font-size: 11px; color: var(--ink-3); margin-bottom: 10px;">&minus;35% vs persistence baseline</div>
  <div style="font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3);">MI300X &middot; Apache-2.0 &middot; HF Hub</div>
</div>

</div>

<p style="margin-top: 18px; font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-3);">Track submitted: Fine-Tuning on AMD GPUs &nbsp;&middot;&nbsp; All three models Apache-2.0, published on HF Hub</p>

---

<div class="eyebrow">06 &middot; DEMO</div>

# Demo.

<div style="margin: 20px 0 18px;">
  <div style="font-family: var(--font-mono); font-size: 12px; font-weight: 500; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-3); margin-bottom: 12px;">Three queries staged for the recording</div>
  <div class="box-grid cols-3" style="gap: 14px;">
    <div class="box" style="border-top: 3px solid #475569;">
      <div class="lbl" style="color: #475569;">Query 1 &middot; single address</div>
      <div class="body" style="font-size: 18px; line-height: 1.35; margin-top: 6px;">&ldquo;80 Pioneer St&rdquo;</div>
    </div>
    <div class="box" style="border-top: 3px solid #0E7490;">
      <div class="lbl" style="color: #0E7490;">Query 2 &middot; zero-risk demo</div>
      <div class="body" style="font-size: 18px; line-height: 1.35; margin-top: 6px;">&ldquo;Is 1 MetroTech Center in Brooklyn at risk during major storms?&rdquo;</div>
    </div>
    <div class="box" style="border-top: 3px solid #1A4480;">
      <div class="lbl" style="color: #1A4480;">Query 3 &middot; grant application</div>
      <div class="body" style="font-size: 15px; line-height: 1.35; margin-top: 6px;">&ldquo;Generate the vulnerability assessment section for a FEMA BRIC application for Jackson Heights, Queens&rdquo;</div>
    </div>
  </div>
</div>

<p style="text-align: center; font-family: var(--font-mono); font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-3); margin: 0 auto; max-width: none;">5.8&ndash;13.1s end-to-end &nbsp;&middot;&nbsp; 4/4 grounding every run &nbsp;&middot;&nbsp; 8+ public-record sources</p>

---

<div class="eyebrow">07 &middot; Why this works</div>

# It refuses to stay silent. It also refuses to make things up.

<div class="box-grid cols-2" style="margin-top: 8px; gap: 14px;">

<div>
<p style="font-size: 17px; color: var(--ink-2); margin-bottom: 10px;">Mellea rejection sampling enforces four checks per briefing. All four must pass.</p>

<div style="display: flex; flex-direction: column; gap: 6px;">
  <div style="font-family: var(--font-mono); font-size: 12px; padding: 6px 12px; background: var(--paper-deep); border-left: 3px solid #162E51;"><code>grounded</code> &mdash; numbers appear verbatim in source</div>
  <div style="font-family: var(--font-mono); font-size: 12px; padding: 6px 12px; background: var(--paper-deep); border-left: 3px solid #162E51;"><code>clean</code> &mdash; no leaked template fragments</div>
  <div style="font-family: var(--font-mono); font-size: 12px; padding: 6px 12px; background: var(--paper-deep); border-left: 3px solid #162E51;"><code>dense</code> &mdash; citations in the same sentence</div>
  <div style="font-family: var(--font-mono); font-size: 12px; padding: 6px 12px; background: var(--paper-deep); border-left: 3px solid #162E51;"><code>resolve</code> &mdash; cited IDs exist in corpus</div>
</div>
</div>

<div>
<p style="font-size: 17px; color: var(--ink-2); margin-bottom: 10px;">If a Stone has no evidence, the system renders SILENT. If Capstone cannot cite, it rerolls.</p>

<div class="box" style="border-top: 3px solid #162E51; padding: 14px 18px;">
  <div class="lbl">Verified Performance</div>
  <div class="body" style="font-size: 16px;">
    5/5 addresses &nbsp;&middot;&nbsp; 4/4 grounding every run &nbsp;&middot;&nbsp; 0 confabulations.
  </div>
</div>
</div>

</div>

---

<div class="eyebrow">08 &middot; What's next</div>

# What's next.

<p style="margin-bottom: 14px; font-size: 18px; color: var(--ink-3); font-family: var(--font-mono); letter-spacing: 0.02em;">The architecture is NYC-specific by data choice, not by code.</p>

<div class="box-grid cols-3" style="margin-top: 0;">

<div class="box">
  <div class="lbl">Stones as standalone packages</div>
  <div class="body">Each Stone is a coherent composition over data sources, models, and deterministic checks. Extract Cornerstone, Touchstone, Keystone, Lodestone as independent packages so any civic-tech project can pull one Stone without the full Riprap stack.</div>
</div>

<div class="box">
  <div class="lbl">Other flood-impacted cities</div>
  <div class="body">Houston (Harvey, Beryl), Miami (king tides), Boston (CSO floods), Jakarta, Manila, Dhaka. The same five-Stone pattern, different probe sets and RAG corpora per city.</div>
</div>

<div class="box tinted">
  <div class="lbl">Historical-event mode</div>
  <div class="body">Re-run the FSM with snapshot data from any past date. Validate the system against measured outcomes: what would Riprap have said before Sandy, before Ida, before the 2024 Beryl remnants. Calibration as a first-class feature.</div>
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

---

<!-- _class: cta -->
<!-- _paginate: false -->

<img class="cta-mark" src="logo-paper.svg" alt="Riprap dam mark" />

<div class="eyebrow" style="margin-top: 124px; color: var(--accent); border: 0; padding: 0;">Riprap &middot; flood briefings on AMD</div>

<h1 style="font-size: 120px; letter-spacing: -0.02em;">Thank you.</h1>

<hr>

<p style="font-family: var(--font-mono); font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase;">
AMD &times; lablab.ai &middot; Developer Hackathon &middot; May 4&ndash;10 2026
</p>

<p style="font-size: 20px; color: rgba(244,246,249,0.78); margin-top: 18px; max-width: 760px;">
Built on AMD MI300X &middot; IBM Granite 4.1 &middot; Mellea grounding &middot; Apache-2.0 throughout. Questions, forks, and city ports welcome.
</p>

<p style="font-family: var(--font-mono); font-size: 13px; letter-spacing: 0.08em; color: rgba(244,246,249,0.7); margin-top: 16px;">
github.com/msradam/riprap-nyc
</p>
