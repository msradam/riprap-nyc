---
marp: true
theme: riprap
paginate: true
size: 16:9
title: Riprap. Citation-grounded flood-exposure briefings for any place in New York.
description: ASCE NY State Convention, Albany, May 13, 2026
---

<!-- _class: lead -->
<!-- _paginate: false -->

<img class="lead-mark" src="logo.svg" alt="Riprap dam mark" />

<div class="eyebrow" style="padding-top: 132px;">
  ASCE NY State Convention &nbsp;&middot;&nbsp; Albany, NY &nbsp;&middot;&nbsp; May 13, 2026
</div>

# Riprap

## Citation-grounded flood-exposure briefings for any place in New York.

<div class="meta" style="grid-template-columns: auto 1px auto 1px auto; margin-top: 28px;">
  <div>
    <div class="meta-label">Speaker</div>
    <div class="meta-value">Adam Munawar Rahman &middot; IBM &middot; MS CE, NYU</div>
  </div>
  <div class="meta-divider"></div>
  <div>
    <div class="meta-label">Invited by</div>
    <div class="meta-value">[ IBM STSM placeholder ]</div>
  </div>
  <div class="meta-divider"></div>
  <div>
    <div class="meta-label">PDH</div>
    <div class="meta-value">1.0 hour &middot; Technical Specialty</div>
  </div>
</div>

---

<div class="eyebrow">00 &middot; Learning objectives</div>

# What you will take away.

<p style="font-size: 18px; color: var(--ink-3); margin-bottom: 16px; max-width: none;">After this session, you will be able to:</p>

<ol style="margin-top: 0;">
  <li>Describe a <strong>citation-grounded synthesis architecture</strong> for fusing multi-source flood evidence into auditable, site-specific narratives.</li>
  <li>Identify where this approach is <strong>appropriate</strong> (screening, grant evidence, capital planning) and where it is <strong>not</strong> (hydraulic modeling, stamped deliverables).</li>
  <li>Evaluate the <strong>epistemic guarantees and limitations</strong> of LLM-based evidence synthesis in civil engineering practice.</li>
  <li>Apply the Five-Stone architecture to <strong>other flood-exposure domains</strong> — riverine, ice-jam, dam-failure — relevant to upstate NY.</li>
</ol>

<p style="position: absolute; bottom: 52px; left: 64px; right: 64px; font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-3); margin: 0;">PDH documentation available on request &nbsp;&middot;&nbsp; 1.0 contact hour</p>

---

<div class="eyebrow">01 &middot; The problem</div>

# When you assess flood exposure, the evidence is scattered.

<p style="font-size: 20px; color: var(--ink-2); max-width: 72ch; margin-bottom: 14px;">For a capital project, a grant application, a vulnerability assessment, or a property disclosure — the relevant evidence sits across eight or more disconnected primary sources. Synthesizing them into a citable narrative takes hours of GIS work per site.</p>

<div class="box-grid cols-4" style="margin-top: 0; gap: 10px;">

<div class="box tinted">
  <div class="lbl" style="color: #005EA2;">Federal</div>
  <div class="body" style="font-size: 15px;">FEMA NFHL<br>USGS 3DEP LiDAR<br>USGS HWMs (Ida, Sandy)<br>NOAA CO-OPS tide</div>
</div>

<div class="box tinted">
  <div class="lbl" style="color: #1A4480;">State</div>
  <div class="body" style="font-size: 15px;">NPCC4 SLR projections<br>NYS Mesonet<br>NWS METAR / watches<br>NY EJNYC FVI</div>
</div>

<div class="box tinted">
  <div class="lbl" style="color: #0E7490;">City</div>
  <div class="body" style="font-size: 15px;">NYC DEP stormwater scenarios<br>NYC 311 flood complaints<br>FloodNet sensor network<br>NYC DOB filings</div>
</div>

<div class="box dark">
  <div class="lbl">The gap</div>
  <div class="body" style="font-size: 15px;">No common schema. Different vintages. Different spatial resolutions. Different epistemic tiers.<br><br><strong>Each site synthesized by hand.</strong></div>
</div>

</div>

<p style="margin-top: 12px; font-size: 20px;">When a number meets resistance, <strong>the only defense is the audit trail.</strong></p>

---

<div class="eyebrow">02 &middot; Solution</div>

# A flood-exposure briefing for any place in New York.

<p style="margin-bottom: 14px; font-size: 20px; max-width: 72ch; color: var(--ink-2);">Type an address or neighborhood. Get a written briefing in 5&ndash;13 seconds, fusing four temporal modes &mdash; historical inundation, current observations, modeled scenarios, projections &mdash; into one cited paragraph.</p>

<div style="border: 2px dashed #94A3B8; background: #E8ECF2; display: flex; align-items: center; justify-content: center; height: 260px; border-radius: 2px; margin-bottom: 10px;">
  <p style="font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-3); text-align: center; margin: 0; padding: 24px;">
    [ screenshot of riprap.nyc landing &mdash; to be added ]
  </p>
</div>

<p style="font-size: 15px; color: var(--ink-3); margin: 0;">Behind the prose: every numeric claim links to its primary public-record source. Mellea rejection sampling refuses to publish what it can&rsquo;t cite.</p>

---

<div class="eyebrow">03 &middot; Architecture</div>

# Five Stones. Each with one job and one epistemic posture.

<p style="font-size: 16px; color: var(--ink-3); margin: 0 0 10px; font-style: normal;">The names are deliberate &mdash; these are load-bearing terms from masonry and structural engineering. The components carry analogous responsibilities.</p>

<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 0;">

  <div style="background: var(--paper-deep); border: 1px solid var(--rule-soft); border-top: 3px solid #475569; padding: 12px 14px; display: flex; flex-direction: column; gap: 6px;">
    <div style="font-family: var(--font-mono); font-size: 9px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: #475569;">Cornerstone</div>
    <div style="font-size: 13px; font-weight: 700; color: var(--ink); line-height: 1.2;">Hazard Reader</div>
    <div style="font-size: 13px; color: var(--ink-2); line-height: 1.4;">What the ground remembers. Sandy 2012 inundation, Ida 2021 HWMs, NYC DEP stormwater scenarios, USGS 3DEP microtopography (HAND, TWI).</div>
    <div style="margin-top: auto; padding-top: 8px; border-top: 1px solid var(--rule-soft); font-family: var(--font-mono); font-size: 9px; color: #475569; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em;">Empirical &middot; Historical</div>
  </div>

  <div style="background: var(--paper-deep); border: 1px solid var(--rule-soft); border-top: 3px solid #1A4480; padding: 12px 14px; display: flex; flex-direction: column; gap: 6px;">
    <div style="font-family: var(--font-mono); font-size: 9px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: #1A4480;">Keystone</div>
    <div style="font-size: 13px; font-weight: 700; color: var(--ink); line-height: 1.2;">Asset Register</div>
    <div style="font-size: 13px; color: var(--ink-2); line-height: 1.4;">What is exposed. NYCHA developments, DOE schools, MTA subway entrances, NYS hospitals, building footprints via TerraMind-NYC.</div>
    <div style="margin-top: auto; padding-top: 8px; border-top: 1px solid var(--rule-soft); font-family: var(--font-mono); font-size: 9px; color: #1A4480; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em;">Modeled &middot; Administrative</div>
  </div>

  <div style="background: var(--paper-deep); border: 1px solid var(--rule-soft); border-top: 3px solid #0E7490; padding: 12px 14px; display: flex; flex-direction: column; gap: 6px;">
    <div style="font-family: var(--font-mono); font-size: 9px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: #0E7490;">Touchstone</div>
    <div style="font-size: 13px; font-weight: 700; color: var(--ink); line-height: 1.2;">Live Observer</div>
    <div style="font-size: 13px; color: var(--ink-2); line-height: 1.4;">What is happening now. FloodNet sensors, NYC 311 complaints, NOAA CO-OPS tide gauge, NWS METAR. Real-time evidence, not modeled.</div>
    <div style="margin-top: auto; padding-top: 8px; border-top: 1px solid var(--rule-soft); font-family: var(--font-mono); font-size: 9px; color: #0E7490; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em;">Observational &middot; Live</div>
  </div>

  <div style="background: var(--paper-deep); border: 1px solid var(--rule-soft); border-top: 3px solid #92400E; padding: 12px 14px; display: flex; flex-direction: column; gap: 6px;">
    <div style="font-family: var(--font-mono); font-size: 9px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: #92400E;">Lodestone</div>
    <div style="font-size: 13px; font-weight: 700; color: var(--ink); line-height: 1.2;">Projector</div>
    <div style="font-size: 13px; color: var(--ink-2); line-height: 1.4;">What is coming. NPCC4 SLR projections, NWS flood watches, IBM Granite TTM r2 storm-surge nowcast. Forward-looking, explicitly uncertain.</div>
    <div style="margin-top: auto; padding-top: 8px; border-top: 1px solid var(--rule-soft); font-family: var(--font-mono); font-size: 9px; color: #92400E; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em;">Modeled &middot; Forecast</div>
  </div>

</div>

<div class="box" style="border-top: 3px solid #162E51; margin-top: 10px; padding: 10px 18px;">
  <span style="font-family: var(--font-mono); font-size: 10px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: #162E51;">Capstone</span>
  <span style="font-size: 15px; color: var(--ink-2); margin-left: 14px;">Granite 4.1 8B + Mellea rejection sampling &nbsp;&middot;&nbsp; <code>numerics_grounded</code> &middot; <code>no_placeholder_tokens</code> &middot; <code>citations_dense</code> &middot; <code>citations_resolve</code> &nbsp;&middot;&nbsp; reroll until every claim cites its source &nbsp;&rarr;&nbsp; <strong>cited 4-section briefing</strong></span>
</div>

---

<div class="eyebrow">04 &middot; Demo</div>

# Live demo.

<div style="margin: 40px 0 28px; text-align: center;">
  <p style="font-family: var(--font-mono); font-size: 28px; font-weight: 700; color: var(--ink); margin: 0 auto; max-width: 860px; line-height: 1.35;">&ldquo;I&rsquo;m thinking about renting an apartment at 80 Pioneer Street, Brooklyn. Should I worry?&rdquo;</p>
</div>

<div style="text-align: center; margin-bottom: 36px;">
  <span style="font-family: var(--font-mono); font-size: 20px; letter-spacing: 0.06em; color: var(--accent); font-weight: 700;">riprap.nyc</span>
</div>

<div class="box-grid cols-3" style="margin-top: 0;">
  <div class="box" style="text-align: center; padding: 14px 18px;">
    <div class="stat-value" style="font-size: 40px;">13 s</div>
    <div class="stat-label">end-to-end on AMD MI300X</div>
  </div>
  <div class="box" style="text-align: center; padding: 14px 18px;">
    <div class="stat-value" style="font-size: 40px;">4 / 4</div>
    <div class="stat-label">grounding checks every run</div>
  </div>
  <div class="box tinted" style="text-align: center; padding: 14px 18px;">
    <div class="stat-value" style="font-size: 40px;">8+</div>
    <div class="stat-label">primary public-record sources</div>
  </div>
</div>

---

<div class="eyebrow">05 &middot; Civic applications</div>

# The civic case for civil engineers.

<div class="box-grid cols-2" style="margin-top: 8px;">

<div class="box">
  <div class="lbl" style="color: #005EA2;">Grant evidence</div>
  <div class="body">HUD CDBG-DR and FEMA BRIC vulnerability assessments. Riprap auto-generates the per-NTA evidence section for each site in a program area. Citable, reproducible, open-source.</div>
</div>

<div class="box">
  <div class="lbl" style="color: #1A4480;">Capital project screening</div>
  <div class="body">NYC DEP Bluebelt expansion, NYCHA resilience hardening, MTA station prioritization, DOE school siting. Site-by-site evidence packages at the screening tier, before the hydraulic modeling budget is spent.</div>
</div>

<div class="box">
  <div class="lbl" style="color: #0E7490;">NY State Infrastructure Report Card</div>
  <div class="body">The 2026 report is in preparation. Riprap is the per-place evidence layer for the flood-exposure chapter of any future NY State infrastructure report &mdash; reproducible at every address.</div>
</div>

<div class="box">
  <div class="lbl" style="color: #92400E;">Property disclosure compliance</div>
  <div class="body">NY&rsquo;s March 2024 Property Condition Disclosure flood-risk amendment requires sellers to disclose flood history. Riprap is the citable narrative behind the disclosure &mdash; every claim sourced.</div>
</div>

</div>

---

<div class="eyebrow">06 &middot; Honest boundaries</div>

# What Riprap is not.

<p style="font-size: 18px; color: var(--ink-3); margin-bottom: 14px; max-width: none;">The civil engineer carries the stamp. Riprap surfaces the evidence the engineer judges.</p>

<div class="box-grid cols-2" style="margin-top: 0; gap: 12px;">

<div class="box" style="border-top: 3px solid var(--rule-soft);">
  <div class="lbl">Not a hydraulic model</div>
  <div class="body" style="font-size: 17px;">Riprap does not replace HEC-RAS, SWMM, or ICM. It synthesizes evidence from completed modeling work; it does not produce new flow or stage estimates. No substitute for a calibrated hydraulic model.</div>
</div>

<div class="box" style="border-top: 3px solid var(--rule-soft);">
  <div class="lbl">Not a stamped deliverable</div>
  <div class="body" style="font-size: 17px;">The briefing is a starting point for a memo, not the memo itself. Professional judgment, field reconnaissance, and the engineer&rsquo;s stamp are required for any actionable deliverable.</div>
</div>

<div class="box" style="border-top: 3px solid var(--rule-soft);">
  <div class="lbl">Not a substitute for site investigation</div>
  <div class="body" style="font-size: 17px;">Microtopography is from 1 m USGS 3DEP LiDAR &mdash; appropriate for screening, not for design. Field reconnaissance, soil borings, and survey are not replaced.</div>
</div>

<div class="box" style="border-top: 3px solid var(--rule-soft);">
  <div class="lbl">Not a risk score</div>
  <div class="body" style="font-size: 17px;">Riprap does not output a 1&ndash;10 or 1&ndash;100 number. Score-based tools (First Street, ClimateCheck, Jupiter) are different products for different audiences. Riprap is the evidence audit trail behind any such judgment.</div>
</div>

</div>

---

<div class="eyebrow">07 &middot; Directions</div>

# Where this goes from here.

<p style="margin-bottom: 14px; font-size: 18px; color: var(--ink-3); font-family: var(--font-mono); letter-spacing: 0.02em;">The architecture is data-choice-specific, not code-specific.</p>

<div class="box-grid cols-2" style="margin-top: 0;">

<div class="box">
  <div class="lbl" style="color: #005EA2;">Upstate NY flooding</div>
  <div class="body">The Five-Stone pattern adapted for riverine flooding (Mohawk River, Hudson tributaries), ice-jam events, and dam-failure inundation downstream of NYS&rsquo;s aging dam inventory. Same architecture, different primary sources.</div>
</div>

<div class="box">
  <div class="lbl" style="color: #475569;">Historical-event mode</div>
  <div class="body">Re-run the FSM with snapshot data from any past date. Validate the system against measured outcomes &mdash; what would Riprap have said before Sandy, before Ida, before the 2024 Beryl remnants. Calibration as a first-class feature for civil engineering use.</div>
</div>

<div class="box">
  <div class="lbl" style="color: #1A4480;">Stones as standalone packages</div>
  <div class="body">Each Stone is a coherent composition over data sources, models, and deterministic checks. Extract Cornerstone, Touchstone, Keystone, Lodestone as independent packages; any civic-tech or consulting workflow can pull one Stone without the full Riprap stack.</div>
</div>

<div class="box tinted">
  <div class="lbl" style="color: #0E7490;">Cross-domain</div>
  <div class="body">The same epistemic pattern &mdash; citation-grounded synthesis, silent when uncertain &mdash; applied to transit, water, energy, and structural-condition reporting. The architecture is general; flood is the first domain.</div>
</div>

</div>

---

<div class="eyebrow">08 &middot; How it was built</div>

# The art of the possible.

<div class="box-grid cols-2" style="margin-top: 8px; gap: 20px;">

<div>
  <p style="font-size: 20px; color: var(--ink-2); max-width: none; margin-bottom: 16px;">Three days of agentic AI-assisted development, on top of months of design thinking. Four foundation models. Three Apache-2.0 NYC fine-tunes trained on AMD MI300X for the AMD &times; lablab.ai Developer Hackathon (May 4&ndash;10, 2026).</p>
  <p style="font-size: 20px; color: var(--ink-2); max-width: none;">Apache-2.0 end-to-end on public-record federal, state, and city data. No commercial APIs contacted at runtime.</p>
  <p style="font-size: 20px; color: var(--ink); max-width: none; margin-top: 12px;"><strong>A working civic-tech tool is now a three-day artifact for an engineer who knows what they want to build.</strong> The substance is what we just walked through. The build approach is the demonstration of how reachable that substance has become.</p>
</div>

<div>
  <div class="box tinted" style="margin-bottom: 10px;">
    <div class="lbl">Foundation models</div>
    <div class="body" style="font-size: 15px;">IBM Granite 4.1 8B (synthesizer) &middot; IBM Granite Embedding 278M (RAG) &middot; GLiNER (typed extraction) &middot; vLLM on AMD MI300X</div>
  </div>
  <div class="box tinted" style="margin-bottom: 10px;">
    <div class="lbl">NYC fine-tunes (Apache-2.0, HF Hub)</div>
    <div class="body" style="font-size: 15px;">Prithvi-EO-2.0-NYC-Pluvial (flood detection, IoU 0.598) &middot; TerraMind-NYC-Adapters (LULC + Buildings) &middot; Granite-TTM-r2-Battery-Surge (surge nowcast, RMSE 0.157 m)</div>
  </div>
  <div class="box tinted">
    <div class="lbl">Agentic framework</div>
    <div class="body" style="font-size: 15px;">Burr FSM &middot; Mellea rejection sampling &middot; LiteLLM Router (vLLM / Ollama failover) &middot; FastAPI SSE stream</div>
  </div>
</div>

</div>

---

<div class="eyebrow">09 &middot; Discussion</div>

# What I want from this room.

<div class="box" style="border-left: 3px solid var(--accent); padding: 18px 24px; margin-bottom: 18px; background: var(--paper-deep);">
  <div class="body" style="font-size: 19px; line-height: 1.5; max-width: none;">I am a software engineer, not a civil engineer. The system I just showed you is opinionated about epistemic posture &mdash; citation-grounded, silent when uncertain, public-record only &mdash; but I am less sure about where it falls short of how a stamped engineering deliverable would need to behave.</div>
</div>

<p style="font-size: 19px; font-weight: 600; color: var(--ink); margin-bottom: 10px;">Three questions for the room:</p>

<ol>
  <li>Where in your practice would a tool like this be <strong>useful</strong>, and where would it be a <strong>liability</strong>?</li>
  <li>What <strong>evidence sources</strong> are you using that Riprap does not yet know about?</li>
  <li>What would have to be true for a citation-grounded narrative tool to be <strong>trusted as a screening-tier deliverable</strong>?</li>
</ol>

<hr style="margin: 16px 0;" />

<p style="font-family: var(--font-mono); font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--accent); margin: 0;">Open-source &middot; Apache-2.0 &middot; github.com/msradam/riprap-nyc</p>

---

<!-- _class: cta -->

<img class="cta-mark" src="logo-paper.svg" alt="Riprap dam mark" />

<div class="eyebrow" style="margin-top: 124px; color: var(--accent); border: 0; padding: 0;">Riprap &middot; citation-grounded flood briefings</div>

<h1 style="white-space: nowrap; font-size: 72px;">github.com/msradam/riprap-nyc</h1>

<hr>

<p style="font-family: var(--font-mono); font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase;">
Apache-2.0 &middot; public data only &middot; IBM Granite 4.1 &middot; AMD MI300X &middot; Mellea grounding
</p>

<p style="font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: rgba(244,246,249,0.55); margin-top: 16px;">
ASCE NY State Convention &middot; Albany, NY &middot; May 13, 2026
</p>

<p style="font-family: var(--font-mono); font-size: 9.5px; letter-spacing: 0.08em; color: rgba(244,246,249,0.4); margin-top: 24px; text-transform: none;">
Dam mark: &ldquo;Dam&rdquo; by Chintuza via the Noun Project, CC-BY 3.0.
</p>

---

<!-- _paginate: false -->

<div class="eyebrow">Appendix A &middot; The receipts</div>

# 5 of 5 NYC addresses. Every claim verified, every run.

<table>
  <thead>
    <tr><th>address</th><th>intent</th><th>wall</th><th>steps</th><th>verified</th></tr>
  </thead>
  <tbody>
    <tr><td>442 E Houston St &middot; LES</td><td>address</td><td>7.6 s</td><td>19</td><td>4/4</td></tr>
    <tr><td>80 Pioneer St &middot; Red Hook</td><td>address</td><td>13.1 s</td><td>19</td><td>4/4</td></tr>
    <tr><td>100 Gold St &middot; Manhattan</td><td>address</td><td>11.2 s</td><td>19</td><td>4/4</td></tr>
    <tr><td>Hollis &middot; Queens</td><td>neighborhood</td><td>5.8 s</td><td>9</td><td>4/4</td></tr>
    <tr><td>Coney Island &middot; Brooklyn</td><td>neighborhood</td><td>9.9 s</td><td>9</td><td>4/4</td></tr>
  </tbody>
</table>

<div class="box-grid cols-3" style="margin-top: 16px;">
  <div class="box">
    <div class="lbl">Wall-clock</div>
    <div class="stat-value">5.8&ndash;13.1<span style="font-size: 22px; color: var(--ink-3); font-weight: 400; letter-spacing: 0;"> s</span></div>
    <div class="stat-label">vLLM on AMD MI300X</div>
  </div>
  <div class="box">
    <div class="lbl">Evidence layers</div>
    <div class="stat-value">5</div>
    <div class="stat-label">Stones per briefing</div>
  </div>
  <div class="box">
    <div class="lbl">Grounding</div>
    <div class="stat-value">4 / 4</div>
    <div class="stat-label">source checks every run</div>
  </div>
</div>

---

<!-- _paginate: false -->

<div class="eyebrow">Appendix B &middot; Primary sources</div>

# Sources. Every claim traces to one of these.

<div class="box-grid cols-3" style="margin-top: 8px; gap: 10px;">

<div class="box tinted">
  <div class="lbl" style="color: #005EA2;">Federal</div>
  <div class="body" style="font-size: 14px; line-height: 1.6;">
    FEMA NFHL (current)<br>
    USGS 3DEP 1 m LiDAR (2020)<br>
    USGS HWMs &mdash; Sandy 2012, Ida 2021<br>
    NOAA CO-OPS tide gauge, Battery (live)<br>
    NWS METAR / flood watches (live)
  </div>
</div>

<div class="box tinted">
  <div class="lbl" style="color: #1A4480;">State / regional</div>
  <div class="body" style="font-size: 14px; line-height: 1.6;">
    NPCC4 SLR projections (2023)<br>
    NY EJNYC Flood Vulnerability Index (2024)<br>
    NYS Mesonet (live)<br>
    NY Property Condition Disclosure (Mar 2024)
  </div>
</div>

<div class="box tinted">
  <div class="lbl" style="color: #0E7490;">City</div>
  <div class="body" style="font-size: 14px; line-height: 1.6;">
    NYC DEP stormwater scenarios (2024)<br>
    NYC 311 flood complaints (live, 5-yr)<br>
    FloodNet sensor network (live)<br>
    NYC DOB filings (live)<br>
    NYC Open Data &mdash; NYCHA, DOE, MTA, hospitals
  </div>
</div>

</div>

<p style="margin-top: 14px; font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-3);">All datasets are public-record. No commercial data APIs. No proprietary hazard scores.</p>
