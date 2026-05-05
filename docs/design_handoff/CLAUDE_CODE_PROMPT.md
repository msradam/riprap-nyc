# Prompt for Claude Code · v0.4.5 polish session

Copy-paste this whole block into Claude Code as your opening message.

---

v0.4.4 has shipped to the local development environment. The Findings region with the Five Stones, evidence cards, and Capstone meta-card are live and rendering against real queries via local uvicorn (`uvicorn web.main:app --host 127.0.0.1 --port 7860`). Screenshots from 80 Pioneer Street, Red Hook confirm the architecture working: four Stones producing genuinely different evidence-card kinds, each carrying its tier badge, the briefing prose with citations resolving cleanly, and the map with three tier-encoded layers.

**v0.4.5 is polish.** Nine specific issues observed in production-shaped local runs, plus a new Stone-tinted light-theming layer. **None of the fixes are structural. Don't rebuild anything.** Read the current implementations of `src/lib/components/findings/StoneRegion.svelte`, `src/lib/components/findings/EvidenceCard.svelte`, and `src/lib/components/findings/CapstoneCard.svelte` and apply the deltas described in `V0.4.5_SPEC.md`.

**Important context.**

- Public mirrors (GitHub, HF Space) were deleted pre-hackathon for caution and re-publish during the hackathon window. **The HF Space link is currently delisted; do not reference it.** All references in this work target local development.
- The codebase is **SvelteKit (Svelte 5 with runes)**. Stay in idiomatic Svelte: `$state`, `$derived`, `$props`, scoped `<style>` blocks. No React. No Tailwind. No animation libraries.
- The card grammar (header / body / footer / tier badge / source link), the four-section briefing prose, the Mellea reroll status strip, the four-tier color palette and glyphs, the cold-start state, the trust-signal footer, and the PDF template's core layout are **not changing**. Don't touch them.

**Read these files first, in order:**

1. `V0.4.5_SPEC.md` — the nine fixes, with file-level deltas, expected outputs, and acceptance criteria.
2. `README.md` — v0.4.4 spec for context (card grammar, tier system, data schema, hover-link contract). Reference, not rework.
3. `design_files/Riprap Stone-Grouped UI v0.4.5.html` — open in browser; this is the **visual target** with all nine v0.4.5 deltas applied.
4. `design_files/Riprap Stone-Grouped UI v0.4.4.html` — kept only for diff/reference against the previously shipped state.

**Order of work** (matches `V0.4.5_SPEC.md` priority):

1. **Status semantics first.** Split the FSM specialist status into `fired / silent_by_design / warned / errored / not_invoked`. Update the per-Stone summary and top tally aggregate counts to render the breakdown. Update provenance row visual treatment per status. This is the most important fix — it's the one actively misrepresenting system integrity.
2. **Capstone meta-card field plumbing.** Wire the four metrics to the reconciler's actual state fields. Acceptance: a clean Red Hook run shows `1 reroll · 4/4 grounding · 4 citations · 24.0s`.
3. **Provenance roster completeness.** Each Stone's expander always shows the full specialist inventory, never a filtered subset. Missing specialists render as `not_invoked` with one-line reasons.
4. **Touchstone card additions** (TerraMind LULC, Prithvi-NYC-Pluvial). If the specialists aren't firing yet, land the card components anyway so they're ready when the data is.
5. **Lodestone fine-tuned TTM card.** Add alongside the existing zero-shot card. Footer must include the HF model-card link, RMSE, and AMD MI300X badge.
6. **Drop the "anomaly" tag.** The new status counts make it redundant.
7. **LAYERS panel restructure.** Group by Stone, add the four new raster layers (default-off), include the explicit "no map layers — see Findings cards" label under Lodestone.
8. **Card-to-map hover linking.** Verify and ship the connection. Click-to-fitBounds() on register cards is new in v0.4.5.
9. **Stone-tinted accent colors.** Add the five `--stone-*` tokens with the proposed values (designer can adjust within constraints). Apply at the recommended placements: 3px left-rule on Stone region headers, 6px dot beside Stone names in the cold-start list, optional row tint on the methodology matrix. Print-media override drops all five to `#999`.

**What to verify before reporting done.**

- A query at 80 Pioneer Street, Red Hook produces a Findings region matching the "v0.4.5 ready looks like" section at the bottom of `V0.4.5_SPEC.md`.
- No regressions in the briefing prose, the Mellea status strip, the cold-start, the footer, the PDF template, or the existing map layers.
- New status messages match the engineering-honest voice in `V0.4.5_SPEC.md` §1 (no euphemism — `"no entrances within radius"`, not "no data found").
- Print stylesheet drops Stone tints to neutral gray.

A v0.4.5 implementation session is a few hours of focused polish, not a day. The structural work is already done.
