# Riprap demo script

Generated via `npm run test:demo`. Each query lands a full-page screenshot
in `test-results/demo-screenshots/<name>.png`. Use the curatorial top-5
ordering for the 5-min pitch slot.

## Curatorial top-5 (5-min pitch)

| Order | Screenshot | What lands | Audience |
|-------|------------|------------|----------|
| 1 | `red-hook.png` | Visual language: claim glyphs in the gutter, 4 sections, citations 1-4 in the drawer, MapLibre with Sandy + DEP layers, trace UI ticking through 9 specialists. The "this is what Riprap *is*" frame. | Everyone |
| 2 | `red-hook-houses-nycha.png` | Specific damning number: ~85% of the 2,878-unit Red Hook Houses footprint inside the 2012 Sandy Inundation Zone. NYCHA register card with per-row provenance grid. | Journalists, agency analysts |
| 3 | `hollis.png` | The Mellea reroll demo — Riprap catches itself getting an order of magnitude wrong (0.19% → 19%) and corrects in front of the audience. The system showing its work. | Researchers, methodology audience |
| 4 | `battery-live-now.png` | Shifts gears from archival to real-time: NOAA Battery gauge + NWS active alerts + TTM r2 surge nowcast. Streams in seconds, not minutes. | Agency analysts (OEM), planners |
| 5 | `downing-street-london.png` | Silence-over-confabulation. The briefing politely refuses to invent NYC content for an out-of-scope address. Closes the philosophical loop. | Researchers, anyone evaluating epistemic discipline |

## Full screenshot index

### Pre-vetted (passing on local Ollama with `RIPRAP_HEAVY_SPECIALISTS=0`)

| Screenshot | Query | Intent | Stakeholder fit |
|------------|-------|--------|-----------------|
| `red-hook.png` | 80 Pioneer Street, Red Hook, Brooklyn | single_address | Everyone — canonical opening |
| `far-rockaway.png` | Far Rockaway flood exposure briefing | neighborhood | CB-14, Queens-borough planners, journalists |
| `coney-island.png` | Coney Island Brooklyn | neighborhood | CB-13 |
| `hollis.png` | Hollis | neighborhood | Researchers — Mellea reroll path |

### Added (need `RIPRAP_HEAVY_SPECIALISTS=1` for register-card cells)

| Screenshot | Query | Intent | Stakeholder fit |
|------------|-------|--------|-----------------|
| `red-hook-houses-nycha.png` | Red Hook Houses NYCHA | single_address | Equity / housing journalists, NYCHA-policy watchers |
| `nyu-langone.png` | NYU Langone Hospital, Manhattan | single_address | Healthcare-resilience analysts; Sandy memory |
| `battery-live-now.png` | current conditions at the Battery, Manhattan | live_now | NYC OEM, NWS forecasters, anyone in surge mode |
| `gowanus-superfund.png` | Gowanus Canal Superfund flood exposure briefing | neighborhood | EPA Region 2 + DEC + DEP; methodology |
| `sheepshead-bay.png` | Sheepshead Bay flood exposure briefing | neighborhood | CB-15; canonical register-card showcase per spec §15 |

### Honest scope

| Screenshot | Query | Outcome | Stakeholder fit |
|------------|-------|---------|-----------------|
| `downing-street-london.png` | 10 Downing Street, London | Geocodes; every NYC specialist falls silent; ErrorCard `all-silent` OR honest "no grounded data" briefing | Researchers, evaluators of epistemic discipline |

## Reading a screenshot

Each image captures the full page after the SSE `done` event. Look for:

1. **Header**: wordmark, query echo, `live` status pill
2. **Briefing prose** (left column): four sections numbered 01–04, claim
   glyphs in the gutter (filled square = empirical, open square = modeled,
   filled circle = proxy, striped square = synthetic prior), citations
   numbered `[1]`–`[N]`
3. **Map** (right column, sticky): four tier-coloured polygon/dot layers.
   Layers with zero features are **omitted** from the legend (silence
   over confabulation, applied to the map)
4. **Citation drawer** (right column, below map): every cite line shows
   tier glyph + source + vintage + doc_id
5. **Register cards** (when present): per-row asset table for subway /
   NYCHA / schools / hospitals
6. **Trace UI** (bottom): one row per FSM step with `fired · silent ·
   errors` summary; tier badge per row when applicable

## Re-running the deck

```bash
# Local Ollama (granite4.1:8b on Mac, ~3 min/query average)
cd web/sveltekit
RIPRAP_HEAVY_SPECIALISTS=1 npm run test:demo

# AMD MI300X (vLLM, ~15 s/query)
RIPRAP_LLM_PRIMARY=vllm RIPRAP_LLM_BASE_URL=http://129.212.182.52:8000/v1 \
RIPRAP_LLM_API_KEY=<vllm-token> .venv/bin/uvicorn web.main:app --port 7860 &
cd web/sveltekit && npm run test:demo
```

The screenshots overwrite on each run; back them up under
`pitch/screenshots/<date>/` before iterating on the briefing prose.
