# Riprap pitch deck

Marp-rendered slides for the AMD x lablab.ai hackathon submission
video (May 4 to 10, 2026). Eight slides, around 30 s of voiceover
each, sized to leave three or more minutes for the live demo inside
the five-minute video cap.

## Files

- `deck.md`. Slide source (Marp markdown).
- `riprap.css`. Marp theme that ports the SvelteKit UI's design
  tokens 1:1: IBM Plex (Sans / Mono / Serif), Civic Hydrology paper
  register (`#F4F6F9`), Stone palette, the dam mark.
- `logo.svg`, `logo-paper.svg`. Cleaned dam mark variants used by
  the title and CTA slides. The original Noun Project file (with
  embedded attribution text) lives at `assets/` in the repo root.
- `Makefile`. One-command builds.

## Render

Marp CLI is the simplest path. Install once:

```bash
npm install -g @marp-team/marp-cli
```

Build any of the three artefacts:

```bash
make pdf    # writes deck.pdf      (best for sharing)
make html   # writes deck.html     (best for live presenting in browser)
make pptx   # writes deck.pptx     (best for editing in Keynote / PowerPoint)
make all    # all three
make clean
```

Or directly:

```bash
marp deck.md --theme riprap.css --pdf  --output deck.pdf
marp deck.md --theme riprap.css --html --output deck.html
marp deck.md --theme riprap.css --pptx --output deck.pptx
```

## Notes

- The theme `@import`s IBM Plex from Google Fonts, so Marp needs
  network access on first build. Cache it by building once on a
  connected machine.
- The deck targets a 1280×720 16:9 frame.
- Slide 7 is the demo handoff. Leave the slide visible while you
  cut to the live screen capture, then return to slide 8 for the
  closing CTA.

## Slide map (5-min video budget)

| # | Slide | Voiceover beat | Time |
|---|---|---|---|
| 1 | Title | Hook: "Riprap. Citation-grounded NYC flood briefings on AMD MI300X." | 0:10 |
| 2 | Problem | Zillow yanked First Street in Dec 2025; black-box scores hit a wall | 0:30 |
| 3 | What it is | Show the cited paragraph; "every number cites its source or it doesn't appear" | 0:35 |
| 4 | Stack | Three of four hackathon tracks; MI300X, vLLM, three NYC fine-tunes | 0:40 |
| 5 | Receipts | 5 of 5 probe pass, 5.8 to 13.1 s, every claim verified | 0:30 |
| 6 | Civic impact | NY disclosure law, DEP $30B plan, EJNYC FVI; open-source matters | 0:25 |
| 7 | Demo handoff | Cut to the live HF Space; type the query; let the FSM speak | ~3:00 |
| 8 | Closing CTA | github.com/msradam/riprap-nyc | 0:10 |
