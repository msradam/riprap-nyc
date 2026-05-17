# Riprap Briefing Standards — Compliance Reference

This document is the trust contract enforced on every Riprap briefing
(both the LLM-tier Granite 4.1 output and the templated-tier output).
Rules are sourced from established standards in flood-risk communication,
climate-risk disclosure, environmental site assessment, public-health
risk communication, and data journalism — they are not invented.

The predicates derived from these rules live in
`riprap/core/compliance/predicates.py`. Each rule is tagged:
**YES** = text-pattern detectable as a Mellea requirement;
**PARTIAL** = detectable with a structured-data check or NLI;
**NO** = requires editorial review.

---

## 1. FEMA Flood Risk Communication

Sources:
- [FEMA Flood Zones glossary](https://www.fema.gov/about/glossary/flood-zones)
- [FEMA Flood Maps program](https://www.fema.gov/flood-maps)
- [FEMA IS-0273: How to Read a FIRM](https://emilms.fema.gov/is_0273/groups/157.html)

**Rule 1.1.** The 1% annual chance flood is the canonical reference; "100-year flood" is acceptable only with the recurrence-interval caveat.
- Source: SFHAs are "the area that will be inundated by the flood event having a 1-percent chance of being equaled or exceeded in any given year" `[close paraphrase, FEMA glossary]`.
- Enforceable: **YES** — if "100-year flood" appears, require "1% annual chance" or "any given year" nearby.

**Rule 1.2.** "In a flood zone" must not be conflated with "will flood."
- Source: SFHAs describe areas that *would be inundated by* the base flood, not areas that *will* flood `[paraphrase]`.
- Enforceable: **YES** — flag bare assertions like "will flood", "is going to flood", "this address floods" without hedging.

**Rule 1.3.** "Outside the SFHA" must not be communicated as "no risk."
- Source: "There is no such thing as a 'no-risk zone'" `[paraphrase, FloodSmart]`.
- Enforceable: **YES** — flag "no risk", "zero risk", "safe from flooding", "won't flood" without context.

**Rule 1.4.** Cumulative-probability framing required when referencing mortgage-period exposure.
- Enforceable: **PARTIAL**.

**Rule 1.5.** Flood maps cited must carry their effective date (FIRM vintage).
- Enforceable: **YES** — when "FEMA flood map", "FIRM", "flood zone" tokens appear, require a year token nearby.

**Rule 1.6.** Regulatory flood-zone status is distinct from actual or future flood risk.
- Enforceable: **PARTIAL** — when future risk or stormwater flooding discussed, require explicit statement that FEMA SFHA is regulatory.

---

## 2. IPCC AR6 Calibrated Uncertainty Language

Sources:
- [IPCC AR5 Uncertainty Guidance Note (carried into AR6)](https://www.ipcc.ch/site/assets/uploads/2017/08/AR5_Uncertainty_Guidance_Note.pdf)
- [IPCC AR6 WG1 SPM](https://www.ipcc.ch/report/ar6/wg1/downloads/report/IPCC_AR6_WGI_SPM.pdf)

**Rule 2.1.** The likelihood lexicon is fixed:

| Term | Probability |
|---|---|
| Virtually certain | 99–100% |
| Extremely likely | 95–100% |
| Very likely | 90–100% |
| Likely | 66–100% |
| More likely than not | >50–100% |
| About as likely as not | 33–66% |
| Unlikely | 0–33% |
| Very unlikely | 0–10% |

- Enforceable: **YES** — whitelist these terms; if a likelihood term appears alongside a numeric probability, check the percentage falls inside the range.

**Rule 2.2.** Likelihood terms reserved for probabilistic statements; uncalibrated hedges to be avoided when paired with a number.
- Enforceable: **YES** — flag "probably", "fairly likely", "good chance" in sentences containing numbers.

**Rule 2.3.** Confidence is qualitative on a 5-step scale: very low, low, medium, high, very high.
- Enforceable: **YES** — confidence terms from the whitelist.

**Rule 2.4.** Confidence and likelihood not interchangeable. Flag "high likelihood" / "likely confidence."
- Enforceable: **PARTIAL**.

---

## 3. TCFD Final Recommendations

Source: [TCFD recommendations](https://www.fsb-tcfd.org/recommendations/) (FSB disbanded TCFD Oct 2023; monitoring transferred to IFRS / ISSB S2).

**Rule 3.1.** Disclosures must separate physical risk from transition risk.
- Source: Physical risks are "acute" (extreme events) or "chronic" (long-term shifts) `[verbatim]`.
- Enforceable: **YES** — Riprap is physical-only; declare scope.

**Rule 3.2.** Time horizons must be declared: short, medium, and long term.
- Source: "Describe... risks and opportunities... over the short, medium, and long term" `[verbatim, Strategy disclosure a)]`.
- Enforceable: **YES** — require explicit horizon statement when projections are cited.

**Rule 3.3.** Multiple scenarios cited where relevant (including a 2°C or lower scenario).
- Enforceable: **PARTIAL** — when SLR projections cited, require scenario family name (NPCC4; SSP).

**Rule 3.4.** Materiality and data limitations disclosed alongside metrics.
- Enforceable: **PARTIAL** — require a "data limitations" or "caveats" element.

---

## 4. ASTM E1527-21 (Phase I ESA) — Scope & Declaration Rules

Sources:
- [ASTM store overview](https://store.astm.org/e1527-21.html)
- [Haley Aldrich summary](https://www.haleyaldrich.com/resources/articles/the-epa-will-adopt-the-astm-e1527-21-standard-practice-for-phase-i-environmental-site-assessments/)

(Full standard is paywalled; rules summarize public-facing scope language. Verify against a licensed copy before quoting verbatim.)

**Rule 4.1.** Deliverable must explicitly state its scope.
- Source: practice "is intended primarily as an approach to conducting an inquiry designed to identify recognized environmental conditions" `[verbatim, §1]`.
- Riprap analog: every brief must declare itself as a *flood-exposure briefing*, not a flood certificate, elevation certificate, or insurance determination.
- Enforceable: **YES** — require scope-declaration sentence at head.

**Rule 4.2.** Defined terms must not be used loosely.
- Enforceable: **PARTIAL** — terminology whitelist.

**Rule 4.3.** Non-scope items must be explicitly excluded.
- Riprap analog: structural elevation, indoor air, sewer backups (in non-coastal contexts), legal title.
- Enforceable: **YES** — boilerplate non-scope block.

**Rule 4.4.** Significant data gaps must be disclosed.
- Source: a "significant data gap" affects ability to identify conditions; report must discuss how gaps affect conclusions `[close paraphrase]`.
- Enforceable: **YES** — when any probe returns offline / missing, brief must include data-gap statement.

**Rule 4.5.** Machine-generated briefs must declare automation and name model/data sources.
- Enforceable: **YES** — automation disclosure required.

**Rule 4.6.** Brief is informational, not a substitute for professional assessment.
- Enforceable: **YES** — closing disclaimer required.

---

## 5. EPA Risk Communication Primer & CDC CERC

Sources:
- [EPA Seven Cardinal Rules](https://archive.epa.gov/care/web/pdf/7_cardinal_rules.pdf)
- [CDC CERC manual](https://www.cdc.gov/cerc/php/cerc-manual/index.html)

**Rule 5.1.** Be honest, frank, and open.
- Enforceable: **PARTIAL** — flag definitive predictions; require qualifying language.

**Rule 5.3.** Coordinate with other credible sources.
- Enforceable: **YES** — every claim carries a source attribution from authoritative-source whitelist.

**Rule 5.6.** CERC's "Be Right" principle: state what is known, what is not known, what is being done to fill gaps.
- Enforceable: **YES** — when probes offline, require "what we know / what we don't know" structure.

**Rule 5.7.** Avoid false reassurance.
- Enforceable: **YES** — block "nothing to worry about", "completely safe", "no chance of flooding", "guaranteed dry".

**Rule 5.8.** Use risk comparison anchors carefully; don't compare unrelated risks to minimize concern.
- Enforceable: **YES** — flag comparisons of flood risk to car accidents, lightning, etc.

**Rule 5.9.** Multi-hazard combining: do not silently aggregate probabilities.
- Enforceable: **YES** — composite ratings must declare their inputs.

---

## 6. AP Stylebook — Statistics, Numbers, Attribution

Source: [AP Stylebook polls-and-surveys entry](https://americanpressinstitute.org/ap-stylebook-entry-polls-and-surveys/)

**Rule 6.1.** Every statistic must be attributed to a named source.
- Enforceable: **YES** — every numeric token co-occurs with attribution span or citation marker.

**Rule 6.2.** State the time period the data covers.
- Enforceable: **YES** — claims about "flood history", "311 complaints", "sensor readings" require date range.

**Rule 6.3.** Do not turn a probability or a lead into a prediction.
- Source: "No matter how good the poll... the poll does not say one candidate will win an election" `[close paraphrase]`.
- Enforceable: **YES** — flag future-tense definitive verbs attached to model output.

**Rule 6.4.** Distinguish correlation from causation.
- Enforceable: **PARTIAL** — flag causal verbs in multi-variable claims without documented causal source.

**Rule 6.5.** Round consistently; no false precision.
- Enforceable: **YES** — require rounding to significant figures appropriate to the source.

**Rule 6.6.** Margin of error / uncertainty disclosed when reporting a measured value.
- Enforceable: **YES** — measured quantities include uncertainty token.

---

## 7. SPJ Code of Ethics

Source: [SPJ Code of Ethics](https://www.spj.org/spj-code-of-ethics/)

**Rule 7.1.** Take responsibility for accuracy. Verify before publishing. `[verbatim]`
- Enforceable: **YES** — every factual claim resolves to a probe record with non-null payload.

**Rule 7.2.** Use original sources whenever possible. `[verbatim]`
- Enforceable: **YES** — source URLs must match whitelist of primary authorities.

**Rule 7.3.** Provide context; do not misrepresent or oversimplify. `[verbatim]`
- Enforceable: **PARTIAL**.

**Rule 7.4.** Identify sources clearly. `[verbatim]`
- Enforceable: **YES** — visible source attribution next to each claim.

**Rule 7.5.** Label advocacy and commentary. `[verbatim]`
- Enforceable: **YES** — brief must mark measurement/citation vs model-inferred vs general guidance.

**Rule 7.7.** Acknowledge mistakes; correct promptly. `[verbatim]`
- Enforceable: **YES** — version stamps and probe-record IDs in every brief.

**Rule 7.8.** Distinguish news from advertising. `[verbatim]`
- Enforceable: **YES** — block named commercial entities outside an explicit resources zone.

---

## Cross-cutting predicate summary

| Predicate | Sources |
|---|---|
| `no_will_flood_without_hedge` | FEMA 1.2, AP 6.3 |
| `no_false_reassurance` | FEMA 1.3, EPA 5.7 |
| `firm_citation_has_vintage` | FEMA 1.5 |
| `hundred_year_flood_clarified` | FEMA 1.1 |
| `likelihood_term_in_whitelist` | IPCC 2.1, 2.2 |
| `confidence_term_in_whitelist` | IPCC 2.3 |
| `no_likelihood_confidence_mixup` | IPCC 2.4 |
| `projection_has_horizon` | TCFD 3.2 |
| `projection_names_scenario` | TCFD 3.3 |
| `scope_declaration_present` | ASTM 4.1 |
| `non_scope_disclaimer_present` | ASTM 4.3 |
| `data_gap_disclosed_when_probe_offline` | ASTM 4.4, CERC 5.6 |
| `automation_disclosure_present` | ASTM 4.5 |
| `informational_disclaimer_present` | ASTM 4.6 |
| `no_unsupported_causation` | AP 6.4 |
| `no_rounding_to_false_precision` | AP 6.5 |
| `no_unrelated_risk_comparisons` | EPA 5.8 |
| `composite_rating_declares_inputs` | EPA 5.9 |
| `every_number_cited` | SPJ 7.1, AP 6.1 (existing `citations_dense`) |
| `every_citation_resolves` | SPJ 7.4 (existing `citations_resolve`) |

---

## Notes on scope and currency

- TCFD content reflects the 2017 final recommendations. The FSB disbanded
  the TCFD in October 2023 and transferred monitoring to the IFRS Foundation
  under ISSB S2.
- ASTM E1527-21 is paywalled. Section-4 rules here are sourced from the
  public store description and reputable legal-firm / consultancy summaries.
- IPCC likelihood ranges are from the AR5 Uncertainty Guidance Note, which
  AR6 explicitly continued to use.
- For each rule, the predicate in `riprap/core/compliance/predicates.py`
  returns `(passed: bool, reason: str)` so audit reports can quote the
  failing sentence verbatim.
