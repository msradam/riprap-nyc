# Pitch Deck Landscape — Hackathon 5-Minute Video Format
Captured 2026-05-07. Sources: Devpost blog, Taikai, SlideModel, Medium / Circles.Life,
TechCrunch 2014, and AMD/lablab hackathon context from AMD-HACKATHON-LANDSCAPE.md.

---

## Four opening patterns in winning hackathon pitches

### 1. Problem-first
Open with "here's what's broken, here's who it hurts, here's the number."
Strongest when the problem is legible in under 10 seconds. Works well when
the audience already knows the space (healthcare, finance, real estate).
Risk: the problem frame can eat half the video if it's not stripped to one
sentence.

### 2. Demo-first
Show the live product within the first 30 seconds; let the judge form an
impression before explanation. Works well when the interface is visually
obvious and the output is striking. Risk: judges who don't know what they're
looking at will miss the point.

### 3. Receipts-first
Open with a proof table, a metric, or a live score. "5 of 5 addresses,
every claim verified, every run." Works well when the artifact is the
argument and the audience has technical credibility to read it.
Risk: dry if the receipts don't connect to a felt problem.

### 4. Architecture-first
Start with the diagram, then show the demo. Works well when the
architecture *is* the differentiator (multi-agent, novel pipeline).
Risk: too slow; judges have already moved on before the demo.

---

## Which pattern fits Riprap

**Recommended: Problem-first into receipts, with demo in the middle.**

The structure that works for Riprap's 5-minute video:

1. **0:00–0:20 — Problem sentence.** One CNN headline on screen.
   One line: "A number meets resistance. The only defense is the
   audit trail." (This is already on slide 2 of the current deck
   and it's good.)

2. **0:20–0:50 — Demo (live or recorded).** Type "442 East Houston
   Street, Manhattan." Watch the Stones fire, the briefing stream,
   the citation chips light up. The Mellea 4/4 meta card.

3. **0:50–1:30 — What you just saw.** Slide: five Stones, the data
   sources named under each, the Capstone reconciler with Mellea.
   Not a prose explanation — a diagram. 10 seconds to scan.

4. **1:30–2:00 — The receipts.** The 5/5 table. 5.8–13.1 s.
   4/4 every run.

5. **2:00–2:30 — Why it's a Fine-Tuning submission.** Three Apache-2.0
   models, named, on AMD MI300X. Test MAE vs zero-shot on the TTM
   fine-tune. This is the hackathon track argument.

6. **2:30–3:30 — The civic case.** Property disclosure law, DEP
   stormwater plan, EJNYC FVI. The open-source argument. This is
   the "why it matters beyond the demo."

7. **3:30–4:00 — What's next.** Ida calibration for ASCE. Stones as
   standalone packages v1.1. Methodology paper.

8. **4:00–5:00 — CTA.** Space URL, GitHub, the three HF Hub models.

**Reasoning.** The Aegis-style projects (7 agents, autonomous crisis
response) are demo-first: the agent chatter is the spectacle. Riprap's
spectacle is quieter — it's the briefing paragraph that reads like a
professional memo and cites every number. That requires 10 seconds of
setup so the judge knows what to look at. Problem-first provides that
10-second setup without burning time.

The receipts are load-bearing because the Fine-Tuning track requires
evidence of GPU work. Putting the 5/5 table and the HF Hub model links
on screen in the first 2 minutes closes the "did they actually run this
on AMD hardware" question before the judge asks it.

---

## Specific weaknesses in the current deck against this pattern

**Slide 3 (THE STACK) is the biggest structural problem.** Leading with
a four-track table (three green, one skipped) communicates "we tried
to cover everything" rather than "we built something specific and deep."
For a hackathon submission, one strong track argument is better than
three partial ones. Reframe to Fine-Tuning as primary; Agents and Vision
as supporting evidence of depth.

**No architecture diagram.** The current deck has no slide that shows
what the system *does* architecturally — just prose descriptions. A
diagram (even a plain text flow: query → planner → five Stones → Capstone
→ briefing) would let judges scan the system in 10 seconds instead of
reading for 45 seconds. This is missing and needs adding.

**Slide 6 (Live Demo) is inert in a PDF/video deck.** "Navigate to
this URL" is not a demo. In a video, the demo is in the recording.
The slide should show either a still of the briefing output (or the
meta card) or serve a different purpose entirely. Repurposing it as
WHAT'S NEXT is the right call — it opens the longer arc and makes
the deck reusable for the ASCE audience.

**The problem slide quote is paraphrased, not exact.** The CNN article
(Dec 2, 2025) is real and cited correctly in RESEARCH.md. The slide
text reads "Zillow removed flood-risk data from listings in December
2025 after pressure from the real-estate industry." The TechCrunch
coverage confirms Zillow's sitewide removal took effect November 14,
reported first in December. The slide should note it as a paraphrase
or tighten to what the article actually says. Adding the "not a score"
distinction is the right addition — it is the exact counter-position
to the Zillow pullout.

**Strengths:** Slide 4 (THE RECEIPTS) is the deck's best slide —
dense, verifiable, numbers-first. The briefing codeblock on slide 2
is the best visual: judges can see the output format immediately.
Slide 5 (WHY IT MATTERS) has the right register and the right policy
hooks — don't touch the voice there.

---

## Common failure modes in hackathon pitches (to avoid)

- More than two sentences per bullet. Judges skim; paragraphs die.
- Explaining the tech before showing the output. Show first, explain second.
- "We plan to" language. The build is done. Everything should be past tense
  or present tense.
- Slides that require the presenter to animate them (arrows appearing, etc.)
  — a PDF must stand alone.
- Over-crediting the AI ("powered by Granite 4.1, the state-of-the-art...").
  Name the model once; the audience knows it.
- Apologizing for scope ("we didn't have time to..."). Cut the feature or
  cut the sentence.
