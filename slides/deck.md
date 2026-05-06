---
marp: true
theme: riprap
paginate: true
size: 16:9
title: Riprap — Citation-grounded NYC flood briefings
description: AMD x lablab.ai Developer Hackathon, May 4–10 2026
---

<!-- _class: lead -->
<!-- _paginate: false -->

# Riprap

## Citation-grounded NYC flood-exposure briefings, on AMD MI300X.

<div class="meta">
AMD &times; lablab.ai Developer Hackathon &nbsp;·&nbsp; <strong>May 4&ndash;10, 2026</strong>
</div>

---

## the problem

# Climate risk data is a black box.

<div class="two-col">
<div>

**First Street.** Score 1–10.
**ClimateCheck.** Score 1–100.
**Jupiter.** Enterprise SaaS.

A number. A bar chart. A black box.

</div>
<div>

> *"Zillow removed flood-risk data from listings in December 2025 after pressure from the real-estate industry."*

— CNN, Dec 2 2025

</div>
</div>

When a number meets resistance, **the only defense is the audit trail**.

---

## what riprap is

# Every number cites its source. Or it doesn't appear.

Type a NYC address &rarr; **17 specialists fan out** &rarr; one paragraph back, with **`[doc_id]` citations** on every numeric claim. If the model can't cite it, it's silent.

<div class="codeblock"><span class="label">Status.</span> 442 East Houston Street, Manhattan, is exposed to flood risk: flooded by Hurricane Sandy in 2012, with recurrent localized flooding evidenced by 19 311 complaints and multiple FloodNet sensor events <span class="cite">[sandy], [nyc311], [floodnet]</span>.

<span class="label">Empirical evidence.</span> Sandy flooded this address Oct 29-30, 2012 <span class="cite">[sandy]</span>. 19 flood-related 311 service requests within 200 m over five years <span class="cite">[nyc311]</span>. Three of five FloodNet sensors within 600 m documented events in the past three years <span class="cite">[floodnet]</span>.</div>

<span class="smallcaps">Mellea rejection sampling &middot; 4 grounding checks &middot; 4/4 pass = ship</span>

---

## the stack

# Three of four hackathon tracks. One project.

<div class="stack">
  <div class="stack-row gpu">
    <div class="lbl">MI300X &middot; vLLM</div>
    <div class="body"><strong>IBM Granite 4.1 8B</strong> &mdash; planner + reconciler. ROCm 7. AMD-served.</div>
  </div>
  <div class="stack-row gpu">
    <div class="lbl">MI300X &middot; ROCm</div>
    <div class="body"><strong>Three Apache-2.0 NYC fine-tunes</strong> trained on AMD Developer Cloud:
      <code>Prithvi-EO-2.0-NYC-Pluvial</code>,
      <code>TerraMind-NYC-Adapters</code>,
      <code>Granite-TTM-r2-Battery-Surge</code>.</div>
  </div>
  <div class="stack-row gpu">
    <div class="lbl">MI300X &middot; ROCm</div>
    <div class="body"><strong>Multimodal specialists.</strong> Sentinel-2 chip &rarr; Prithvi pluvial seg &middot; TerraMind LULC + Buildings adapters &middot; Granite Embedding 278M &middot; GLiNER typed extraction.</div>
  </div>
  <div class="stack-row app">
    <div class="lbl">FastAPI</div>
    <div class="body"><strong>Burr FSM agent.</strong> 17 specialists fuse FEMA, NYC DEP, NYC 311, FloodNet, NOAA, NWS, USGS HWMs, Sentinel-2. Streamed via SSE.</div>
  </div>
</div>

<div style="margin-top: 18px;">
  <span class="pill accent">Agents</span><span class="pill accent">Fine-tuning</span><span class="pill accent">Vision/Multimodal</span><span class="pill">Build-in-public</span>
</div>

---

## the receipts

# 5 of 5 NYC addresses. Mellea 4/4 every run.

<table>
  <thead>
    <tr><th>address</th><th>intent</th><th>wall</th><th>specialists</th><th>grounding</th></tr>
  </thead>
  <tbody>
    <tr><td>442 E Houston St &middot; LES</td><td>address</td><td>7.6 s</td><td>19</td><td>4/4</td></tr>
    <tr><td>80 Pioneer St &middot; Red Hook</td><td>address</td><td>13.1 s</td><td>19</td><td>4/4</td></tr>
    <tr><td>100 Gold St &middot; Manhattan</td><td>address</td><td>11.2 s</td><td>19</td><td>4/4</td></tr>
    <tr><td>Hollis &middot; Queens</td><td>nbhd</td><td>5.8 s</td><td>9</td><td>4/4</td></tr>
    <tr><td>Coney Island &middot; Brooklyn</td><td>nbhd</td><td>9.9 s</td><td>9</td><td>4/4</td></tr>
  </tbody>
</table>

<span class="smallcaps">scripts/probe_addresses.py &middot; vLLM on MI300X &middot; <strong style="color: var(--accent-text);">5.8&ndash;13.1 s end-to-end</strong></span>

---

## why it matters

# The civic-tech case.

<div class="two-col">
<div>

**NY Property Disclosure Law &middot; March 2024.** Sellers must disclose flood history. Riprap is the citable narrative.

**NYC DEP Stormwater Plan &middot; 2024.** $30B priority list, 86 sites. Riprap is the per-NTA evidence layer.

**EJNYC Flood Vulnerability Index &middot; 2024.** 35% of state climate spend goes to "disadvantaged communities." Riprap stays open-source so advocacy can audit.

</div>
<div>

<p style="font-family: var(--font-serif); font-style: italic; font-size: 24px; color: var(--ink); line-height: 1.4;">No commercial APIs. No closed models. No black-box scores.</p>

<p style="font-size: 18px; color: var(--ink-2); margin-top: 16px;">Every dataset is public-record federal, state, or city. Every foundation model is Apache-2.0. Every claim cites its source.</p>

</div>
</div>

---

## now

# Live demo.

<div style="margin-top: 24px; font-family: var(--font-mono); font-size: 18px; line-height: 1.6;">

<span style="color: var(--accent-text);">▶</span> &nbsp; <code>https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space</code>

<span style="color: var(--accent-text);">▶</span> &nbsp; query: <em style="font-family: var(--font-serif); font-style: italic; color: var(--ink); border: none; padding: 0;">442 East Houston Street, Manhattan</em>

</div>

<div style="margin-top: 36px;">
<blockquote>17 specialists, ~10 seconds, audit-grade prose. Watch the Stones light up.</blockquote>
</div>

---

<!-- _class: cta -->

# riprap

## github.com/msradam/riprap-nyc

Apache-2.0 &middot; public data &middot; AMD MI300X &middot; IBM Granite 4.1 &middot; Mellea grounding

<p style="margin-top: 32px; font-family: var(--font-mono); font-size: 14px; letter-spacing: 0.1em; text-transform: uppercase; color: rgba(250,250,247,0.6);">
AMD &times; lablab.ai &middot; May 4&ndash;10 2026
</p>
