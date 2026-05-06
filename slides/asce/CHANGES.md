# ASCE NY State Convention Deck — Changes from Hackathon Deck

## What is different

The ASCE deck is a complete content rewrite targeting civil and transportation
engineers at the inaugural ASCE NY State Convention in Albany (May 13, 2026).
The visual system is identical — same IBM Plex fonts, same Civic Hydrology
palette, same Stone color tokens, same box/grid layout primitives, same dam
mark. The content register shifts from "AI hackathon submission" to
"engineer-to-engineer PDH talk." The AMD/lablab.ai framing is retained but
moved to a single late slide (08 · How it was built) rather than leading.
Civil-engineering vocabulary (FEMA NFHL, NPCC4, HEC-RAS, SWMM, ICM, HAND,
TWI, USGS HWMs) appears throughout as first-language terms. The Five Stones
are introduced with explicit note that the names are structural/masonry terms.
A PDH learning-objectives slide opens the deck. An "honest boundaries" slide
(what Riprap is not) is new and load-bearing for a PE audience. The closing
slide solicits feedback from the room rather than pitching a hackathon track.

## Slide map

| ASCE slide | Content | Relationship to hackathon deck |
|---|---|---|
| 00 · Learning objectives | PDH takeaways, 4 objectives | **New** — no equivalent in hackathon deck |
| 01 · The problem | Evidence scatter across 8+ sources, engineer's framing | **Rewritten** — replaces "Climate risk is a black box" (HK slide 01); same underlying problem, civil-eng vocabulary |
| 02 · Solution | What Riprap does; screenshot placeholder | **Adapted** — same structure as HK slide 02; subhead and caption rewritten |
| 03 · Architecture — Five Stones | Four Stone cards + Capstone footer | **Adapted** — same inline evidence-card layout as HK slide 04; card body text rewritten for engineering audience; Stone names contextualized as structural terms |
| 04 · Live demo | Same query, same riprap.nyc URL; stat cards below | **Reused** — same as HK slide 06; stat cards added below for PDH pacing |
| 05 · Civic applications | 4 use cases for civil engineers | **Rewritten** — replaces HK slide 03 "civic-tech case"; adds Infrastructure Report Card and property disclosure; removes EJNYC/advocacy framing |
| 06 · Honest boundaries | 4-card "what Riprap is not" | **New** — no equivalent in hackathon deck; load-bearing for PE audience |
| 07 · Directions | 4 forward directions including upstate NY | **Adapted** — replaces HK slide 07 "What's next"; adds upstate NY riverine/ice-jam/dam-failure direction; drops "other flood-impacted cities" |
| 08 · How it was built | AMD hackathon context, models, agentic stack | **Rewritten** — replaces HK slide 05 (fine-tunes); honestly frames the hackathon as context, not headline |
| 09 · Discussion / Q&A | 3 feedback questions for the room | **New** — no equivalent in hackathon deck |
| 10 · CTA closing | github URL, colophon | **Adapted** — same dark CTA slide; AMD/lablab eyebrow replaced with ASCE event line |
| Appendix A · Receipts | 5/5 address probe table | **Reused** — identical to HK appendix slide |
| Appendix B · Sources | Primary sources by jurisdiction tier | **New** — no equivalent in hackathon deck; useful for PE attendees who want to follow up |

Hackathon-only slides not carried over:
- HK slide 05 · Fine-Tuning on AMD MI300X — the fine-tune cards are folded
  into slide 08 as a secondary detail block; they are not the lead for this
  audience.

## Open placeholders for Adam to fill in

1. **`[ IBM STSM placeholder ]`** on slide 00 (cover) — the name of the IBM
   STSM who invited Adam to speak. Replace the literal string with the person's
   name and title before presenting.

2. **`[ screenshot of riprap.nyc landing — to be added ]`** on slide 02 — the
   dashed placeholder box. Replace with an actual screenshot of the running
   system at full resolution before presenting. The box is 260 px tall; a
   1280×520 screenshot at 2× will fill it cleanly.

3. **Slide 04 stat cards** — the three stat values (13 s, 4/4, 8+) are from
   the hackathon probe runs on AMD MI300X. If the demo environment changes
   (e.g., HF Space cpu-basic instead of MI300X), update the wall-clock and
   note the hardware in the stat label.
