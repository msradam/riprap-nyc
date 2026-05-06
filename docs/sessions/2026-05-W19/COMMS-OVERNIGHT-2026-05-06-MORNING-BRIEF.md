# Morning brief — comms overnight pass, 2026-05-07

Branch: `comms-overnight-2026-05-06`
Work is local-only, not pushed to remote or HF.

---

## Status

All four work streams completed. Research memos are in `research/`.
Deck is revised (9 slides, built to PDF/HTML/PPTX locally). Submission
copy is drafted in `submission/COPY-DRAFTS.md`. Cover image was not
auto-generated — a design brief is in that same file with the quickest
path (re-export the deck cover slide as PNG). One verification item
remains open before submission: the Mellea 4/4 claim on slide 05.

There is a branch-state anomaly to be aware of: commits during this
session landed on both `comms-overnight-2026-05-06` (the intended
branch) and `overnight-2026-05-06` (a prior session's branch). The
content is the same on both. `comms-overnight-2026-05-06` has the clean
set (research + deck + change log + submission copy). You can merge
either branch; both are local-only.

---

## Research pass — five bullets each

### AMD hackathon landscape (`research/AMD-HACKATHON-LANDSCAPE.md`)

- **Agents track dominates the visible field.** Most in-flight
  submissions are multi-agent orchestration systems. Fine-Tuning
  submissions are sparse; NyayaLLM is the only comparable one
  (domain-specific legal LLM on MI300X), but it's single-model,
  single-jurisdiction, and has no published artifacts.
- **Three published Apache-2.0 fine-tunes is the differentiator.**
  No other visible submission mentions published model artifacts.
  The three HF Hub repos are verifiable; judges can clone and run them.
- **The domain-tool penalty is real.** A 13-second cited flood briefing
  is harder to demo than a 7-agent crisis system that spawns child
  agents in real time. The architecture slide and the receipts table
  need to close that gap before the civic-tech hook can land.
- **"Three of four tracks" was a liability.** The hackathon is
  one-track submission. "Engaged in three tracks" reads as hedging.
  Fine-Tuning is the right single-track argument.
- **Lablab.ai submission pages 403'd.** Project descriptions above are
  from search snippets only. The full 30+ project list requires a
  logged-in lablab.ai session. The landscape read is directional, not
  exhaustive.

### Pitch deck landscape (`research/PITCH-DECK-LANDSCAPE.md`)

- **Problem-first into receipts-first is the right pattern for Riprap.**
  The Zillow pullout gives the problem in one CNN headline. The 5/5
  table is the receipts. Demo in the middle, fine-tune evidence before
  the civic case.
- **The architecture diagram was the single biggest missing slide.**
  Judges scanning a PDF without a system diagram can't assess technical
  depth. The new slide 03 (Five Stones → Capstone flow) does that work
  in one scan.
- **The "Live Demo" slide was inert in a static deck.** Repurposing to
  "What's Next" opens the longer arc visible to both the hackathon
  audience (May 10) and the ASCE audience (May 13). No content loss.
- **Do not lead with AI vocabulary; lead with civic vocabulary.**
  "RPL §462(2)" and "NYC DEP" are signals of domain expertise, not
  buzzwords. Name them early in the video, not in the deck's second
  half.
- **5-minute video structure:** 0:00 problem sentence, 0:20 demo,
  0:50 architecture, 1:30 receipts, 2:00 track argument (fine-tunes),
  2:30 civic case, 3:30 what's next, 4:00 CTA. Full breakdown in the
  research memo.

---

## Deck changes — condensed

| Slide | Before | After |
|---|---|---|
| 01 · Problem | CNN quote as direct citation, no counter-positioning | Quote marked as paraphrase, corrected to Nov 14 removal date; added "not a score" distinction |
| 02 · What riprap is | Unchanged | Unchanged |
| NEW 03 · Architecture | Did not exist | New: query → Planner → 4 evidence Stones (with data sources named) → Capstone + Mellea → briefing |
| 03 → 04 · The track | "Three of four tracks. One project." + Build in Public Skipped row | "Submitted to Fine-Tuning." Fine-Tuning = Primary, Agents/Vision = Supporting. Skipped row removed. |
| 04 → 05 · Receipts | Unchanged | Unchanged (see open item below) |
| 05 → 06 · Why it matters | Unchanged | Unchanged |
| 06 → 07 · Now / Demo | Live demo URL + blockquote (inert in static deck) | WHAT'S NEXT: Ida/ASCE calibration, Stones v1.1 packages, methodology paper |
| CTA | Unchanged | Unchanged |

Slide count: 8 → 9.

---

## Cover image

The cover image (`submission/cover-16x9.png`) was not auto-generated.
Design brief is in `submission/COPY-DRAFTS.md`.

**Quickest path:** export the cover slide from the deck PDF as a
1920×1080 PNG. The Marp cover slide already uses the correct tokens,
dam mark, and layout. From `slides/`:

```
npx @marp-team/marp-cli@latest deck.md --theme riprap.css \
  --allow-local-files --images png
```

This generates `deck.001.png` (the cover slide) which is the 16:9
thumbnail. Rename to `submission/cover-16x9.png`.

---

## Submission copy — recommended

**Title:** `Riprap — Cited NYC flood briefings on AMD` (42 chars)

**Short (237 chars):**
Riprap writes NYC flood-exposure briefings where every numeric claim cites its source — or doesn't appear. Granite 4.1 8B on AMD MI300X, three Apache-2.0 NYC fine-tunes, Mellea citation grounding. 5/5 addresses, 4/4 checks every run.

**Long (~280 words):** in `submission/COPY-DRAFTS.md`, no changes needed.

**Runner-up title:** `Riprap: citation-grounded flood briefings`

---

## Three things to look at first

1. **Run the 20-query Mellea probe suite and check slide 05.**
   The deck's "4/4 every run" claim is verified against the 5-address
   probe. If Track A's 20-query stakeholder suite is complete, check
   the grounding results. If any query failed at < 4/4, update the
   slide. Do not submit a deck with a "4/4" claim that doesn't hold
   across the wider suite. Command from `scripts/`:
   ```
   .venv/bin/python scripts/probe_addresses.py
   ```

2. **Generate the cover image** from the deck cover slide (see above).
   One npx command, one rename. Takes 2 minutes.

3. **Review the architecture slide (new slide 03)** in the rendered PDF.
   It uses inline styles and box-grid classes. Verify it renders cleanly
   in the PDF before submission — particularly the four Stone columns and
   the Capstone row at the bottom. If the layout is cramped, reducing the
   Stone cell font sizes by 1–2px will fix it. Source: `slides/deck.md`
   lines ~103–160.

---

## Open questions that need Adam's call

**1. Track submission: Fine-Tuning is the call, but confirm.**
The research pass found no evidence against Fine-Tuning as primary. If
you have information about lablab.ai's scoring criteria that suggests
Agents is stronger (e.g., the FSM + Burr architecture is judged
separately), change slide 04 before submission. The deck frame is easy
to swap — the track-row badges are the only change.

**2. The CNN quote on slide 01 — exact vs paraphrase.**
Current: "Zillow removed climate risk scores from listings under pressure
from the real-estate industry. In their place: a link, far less visible."
Marked as paraphrase. If you want a direct quote for a public-facing
deck, the TechCrunch version is: "Zillow removed the listings' climate
scores. In their place is a subtle link to their records at First Street."
(TechCrunch, Dec 1, 2025.) Either is defensible; this is an editorial
call.

**3. ASCE talk (May 13) — which slides to adapt.**
The new "What's Next" slide (07) and the "Why it Matters" slide (06)
are the ASCE-relevant ones. For ASCE, slide 04 (The Track) should be
replaced with a "Methods" slide. The architecture diagram (slide 03)
and receipts (slide 05) travel unchanged. Make the branch decision:
fork a new `asce-2026-05-13` branch off this deck or iterate in place.

**4. `overnight-2026-05-06` branch cleanup.**
That branch has duplicate commits plus `e203d5f tests: add 20-query
stakeholder integration suite` from the prior session. Decide whether
to merge it into main, keep it as a holding branch, or delete it. The
comms work you need is all on `comms-overnight-2026-05-06`.
