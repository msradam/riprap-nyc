# AMD x lablab.ai Hackathon — Landscape Read
Captured 2026-05-07 as part of the overnight comms pass.
Sources: lablab.ai event pages, AMD developer blog, web search.
Submission pages 403 during scraping; description data from search snippets.

---

## Hackathon structure

Three competition tracks (Build in Public is a documentation track,
not evaluated for the main prize):

| Track | AMD framing | Difficulty label |
|---|---|---|
| AI Agents & Agentic Workflows | Agentic systems, orchestration, FSMs, multi-agent | Entry |
| Fine-Tuning on AMD GPUs | Domain-specific LoRA / full-fine-tune on MI300X or ROCm | Advanced / GPU-intensive |
| Vision & Multimodal AI | Multi-modal pipelines using MI300X memory bandwidth | Advanced |

Prize pool: $21,500+ and one AMD Radeon AI PRO R9700 GPU.
Build phase: May 4–10, 2026 online; on-site May 9–10 in San Francisco
(invitation only).
Judging criteria (lablab.ai standard): Application of Technology,
Presentation, Business Value, Originality.

---

## Representative in-flight submissions (from search snippets; project
pages returned 403 during automated scraping)

| Team / Project | What it appears to do | Track |
|---|---|---|
| **Aegis** | Autonomous 7-agent crisis management system: monitors global risk signals, predicts disruption impact with hybrid ML, auto-executes response | Agents |
| **The Architect's Eye** | Autonomous multi-agent construction safety: multimodal vision + regulatory auditing, real-time hazard detection | Agents + Vision |
| **NyayaLLM** | Legal AI fine-tuned on AMD MI300X for Indian criminal law (BNS/BNSS/BSA); domain-specific LLM for citizens and legal professionals | Fine-Tuning |
| **Hack_AI** | "AI agents that think, learn, and act to solve real-world challenges" — general-purpose agentic description | Agents |
| **Radeon Agents** | "Scalable systems, continuous hands-on innovation" — general-purpose infrastructure / agentic | Agents |
| **NextGen Labs** | Multi-GPU ROCm infrastructure, LLM inference optimization, autonomous agent pipelines | Agents + infra |
| **RoCJ** | Not described in available snippets | Unknown |
| **OneTimeBigTime** | Not described in available snippets | Unknown |

**Caveat**: lablab.ai submission pages returned 403 for all direct fetches.
The above is derived from search result snippets and may be incomplete or
imprecise. Treat as directional, not authoritative.

From search snippets, ~30 in-flight projects total are listed on the event
page. Complete enumeration requires a logged-in session on lablab.ai.

---

## Patterns across the visible field

**Track concentration: Agents dominates.**
Every project description visible in search snippets defaults to agentic
framing. Multi-agent orchestration, autonomous workflows, and "AI that
thinks and acts" are the standard template. Fine-tuning submissions are
sparse in the visible set; domain-specific trained models are notable
exceptions (NyayaLLM is the only clear fine-tune submission in the
visible set other than Riprap).

**Presentation style: general-purpose and horizontal.**
Most descriptions are intentionally broad ("real-world challenges,"
"scalable systems"). Very few name a specific domain, user type, or
measurable outcome in the project headline. This is the default shape
of a lablab.ai submission: apply AMD GPUs to AI + deploy.

**Demo format: live app or video, no architectural depth in the listing.**
The project thumbnail and short description are the first-pass filter.
Demo quality matters more than depth in the listing itself.

**Technology stack: standard.**
vLLM or Ollama for serving, Langchain or custom orchestration for agents,
open-source models (Granite, Llama, Mistral). ROCm + MI300X is the
GPU path. Very few projects mention custom datasets or trained artifacts.

---

## Where Riprap is differentiated

1. **Domain specificity with verifiable receipts.**
   Riprap is the only visible submission targeting a specific civic domain
   (NYC flood risk) with publicly published fine-tune artifacts (three
   Apache-2.0 models on HF Hub). NyayaLLM is the closest comparator on
   domain specificity; it is single-model, single-jurisdiction, and legal
   rather than multi-model geospatial.

2. **Three published fine-tunes on MI300X.**
   `msradam/TerraMind-NYC-Adapters`, `msradam/Prithvi-EO-2.0-NYC-Pluvial`,
   `msradam/Granite-TTM-r2-Battery-Surge` are live on HF Hub, Apache-2.0,
   with training code in the repo. No other visible submission mentions
   published model artifacts. This is the strongest evidence for the
   Fine-Tuning track — it is not a claim about fine-tuning, it is the
   artifact.

3. **Citation discipline as an architectural commitment.**
   Mellea rejection sampling with four named invariants (`numerics_grounded`,
   `no_placeholder_tokens`, `citations_dense`, `citations_resolve`) is
   uncommon in hackathon submissions. Most agentic projects output text;
   Riprap refuses to output text it cannot cite. This is demonstrable in
   the live app.

4. **Civic-tech vs general-purpose.**
   Riprap is a domain tool for urban planners, journalists, grant writers,
   and attorneys — not a coding assistant or general workflow tool. This
   is a double-edged position: judges pattern-matching to "most impressive
   agentic demo" may not immediately read the civic-tech framing as
   technically deep. The architecture slide and the proof table need to
   close that gap.

---

## Where Riprap's framing is at risk

**The domain-tool penalty.** Hackathon judges are often technical
evaluators who are primed to reward visible agent sophistication (tools
called, steps taken, orchestration complexity on screen). A 13-second
flood briefing looks understated next to a 7-agent crisis system that
spawns child agents in real time. Riprap's value is in what the prose
*doesn't* say (hallucinated claims) and what the architecture *proves*
(citation grounding), both of which are harder to demo than agent chatter.

**Three tracks vs one submission.** The current deck says "three of four
tracks." The hackathon format requires one-track submission. A deck that
leads with "we touched three tracks" reads as hedging, not confidence.
The Fine-Tuning track is the strongest single-track argument: three
published MI300X-trained Apache-2.0 models is concrete. Submit to
Fine-Tuning and let the agents + vision work show in the architecture
slide as evidence of depth, not as a co-primary claim.

**Civic vocabulary may not translate immediately.** "RPL §462(2),"
"NYC DEP stormwater plan," "EJNYC FVI" are precise and correct but they
require context. In a 5-minute video, leading with the civic policy
vocabulary before the demo creates a delay. Lead with the demo output
(the briefing paragraph, the citation chips, the Mellea pass), then name
the policy hooks as the second-order impact.

**No comparable submission is trying to do what Riprap does.** That is
an advantage and a risk. Judges evaluating "agentic AI apps" who have
not seen a citation-grounded geospatial briefing tool before will need
15–20 seconds of setup to understand the claim. The architecture slide
and the opening problem frame need to do that work fast.
