# Phase 11 — Live Sentinel imagery fetch for TerraMind-NYC

## Goal

Replace the cached Major-TOM monotemporal chips (frozen 2020-2025
acquisition window) with a *live* fetch path so that
`app/context/terramind_nyc.py` can run inference on the most-recent
qualifying Sentinel-2 + Sentinel-1 acquisition for any NYC point. The
imagery freshness is then a number Granite can cite alongside the
prediction.

## What live actually means here

Sentinel revisit times, honestly:

| Source | Native revisit | With cloud filter | STAC availability |
|---|---|---|---|
| Sentinel-2 (S2A + S2B) | 5 days | 5–15 days | < 24 h after acquisition |
| Sentinel-1 (S1A + S1C) | ~6 days | n/a (radar) | < 24 h after acquisition |

So "live" = "most-recent qualifying acquisition" = typically 1–7 days
old. We disclose the per-query age so a Granite synthesis can cite
exactly how fresh the imagery is.

## Sources tested

### probe_earth_search.py — Element 84 / AWS Open Data

Anonymous, no auth, COG-streamable. Result for Empire State Building:

| Modality | Result |
|---|---|
| Sentinel-2 L2A | acquired **1 day ago**, 7.0% cloud, 1.4 s chip read |
| Sentinel-1 GRD (raw slant-range) | acquired 4 days ago, **no embedded CRS**; needs RTC processing |
| Total wall-clock (S2 only) | **3.5 s** |

S2 is great. **GRD is unusable for our model**: it ships in slant range
without a CRS, so reprojection to a chip grid fails. We need RTC.

Earth Search's collection list as of 2026-05-05:

```
sentinel-2-l2a, sentinel-2-l1c, sentinel-2-c1-l2a, sentinel-2-pre-c1-l2a,
sentinel-1-grd,
cop-dem-glo-30, cop-dem-glo-90,
landsat-c2-l2, naip
```

Notably **no `sentinel-1-rtc`**. So Earth Search alone cannot serve the
SAR modality our model needs.

### probe_pc_s1rtc.py — Microsoft Planetary Computer

Anonymous via URL signing, has the `sentinel-1-rtc` collection. Result:

| Modality | Result |
|---|---|
| Sentinel-1 RTC | acquired **4 days ago**, EPSG:32618 (UTM-18N), 2.7 s chip read |
| Total wall-clock | **3.3 s** |

Despite our prior experience (May 3 evening showed >50% timeout rate),
PC was reliable and fast on May 4 evening. The flakiness appears
event-driven, not chronic.

## Sovereignty matrix

| Source | Host | Auth | Sovereignty | Verdict for Riprap |
|---|---|---|---|---|
| **ESA Copernicus Data Space (CDSE)** | ESA | Free registration | EU sovereign, authoritative | Best for production civic-tech, requires user-side credential setup |
| **NASA Earthdata / ASF** | NASA | Earthdata Login (free) | US sovereign, used by FEMA/USGS | Same registration friction as CDSE |
| **Element 84 / AWS Open Data** | AWS | None | Private cloud, public access | Zero-friction; data is ESA-authoritative; host is private |
| **Microsoft Planetary Computer** | Microsoft | None (URL signing) | Private cloud, public access | Zero-friction; flakiness risk |

The DATA is ESA Copernicus under Copernicus License regardless of host.
The HOST differs in sovereignty story.

## Recommended architecture

For Riprap's deployment story (anonymous-by-default, sovereignty-aware,
swap-in capable for credentialed sovereign sources):

```
Primary path (anonymous, zero-friction):
  - Sentinel-2 L2A   from Earth Search (Element 84 / AWS Open Data)
  - Copernicus DEM   from Earth Search (cop-dem-glo-30)
  - Sentinel-1 RTC   from Microsoft Planetary Computer (URL-signed)

Optional sovereign override (set RIPRAP_SENTINEL_SOURCE=cdse with creds):
  - All modalities   from ESA Copernicus Data Space directly

Disclosure in every briefing:
  "Sentinel-2 acquired N days ago, Sentinel-1 acquired M days ago,
   sourced from <host>. Data: ESA Copernicus License."
```

Per-query budget on a fresh fetch (uncached):
- Earth Search S2 + DEM: ~2 s
- PC S1 RTC: ~3 s
- Model inference: ~0.5 s
- **Total: ~5–6 s per query**

With per-MGRS-cell caching (chips don't change between revisits within
a 5-day window for the same scene), repeat queries hit local cache and
return in < 1 s.

## What changes in the integration

`app/context/terramind_nyc.py` (the new specialist) replaces its current
"load from local Major-TOM cache" path with a `fetch_recent_chips(lat, lon)`
function that tries Earth Search first, then PC for S1-RTC. Cache is keyed
by (s2_mgrs_tile, s2_acquisition_date) so cold-cache wall-clock is the
~5 s above and warm-cache is < 100 ms.

The output dict that goes into Granite's document context gains:

```python
{
  ...,
  "s2_acquired_iso": "2026-05-04T16:01:44Z",
  "s2_age_days": 1,
  "s2_cloud_pct": 7.0,
  "s2_source": "Element 84 Earth Search (ESA Copernicus License)",
  "s1_acquired_iso": "2026-05-01T22:51:31Z",
  "s1_age_days": 4,
  "s1_source": "Microsoft Planetary Computer (ESA Copernicus License)",
  "imagery_freshness_disclosed": True,
}
```

Granite can cite both ages and both sources directly.

## What this enables in the briefing

A Brighton Beach briefing currently can't say anything about *current*
imagery. After integration, it can:

> "Structural land cover at this 2.56 km tile is **78% developed,
> 7% open water, 14% green space** [terramind_nyc]. Sentinel-2 imagery
> acquired 1 day ago [esa_s2]; Sentinel-1 SAR acquired 4 days ago
> [esa_s1]. The high imperviousness limits stormwater absorption,
> compounding the address's coastal Sandy-zone exposure [sandy]."

Three new cite-able facts: imperviousness, S2 age, S1 age. All
defensible against ground truth.

## Honest limitations

- **Cloud cover.** When S2 is cloudy, the most-recent low-cloud
  acquisition might be 7–15 days old. Disclosed per query.
- **PC reliability.** Bursty timeouts during high-load windows. Retry
  logic + fallback to S2-only inference (zero-fill S1 channel) is
  the right defensive posture.
- **No RTC anonymously.** Earth Search has no `sentinel-1-rtc` so we
  depend on PC for S1. If PC is down, briefing falls back to S2-only
  with explicit "S1 unavailable for this query" disclosure.
- **Sovereignty.** AWS Open Data and PC are private-cloud-hosted
  mirrors of ESA-authoritative data. The data is sovereign; the host
  is not. For deployments requiring full sovereignty, CDSE direct is
  the swap-in path.

## What to land in `app/`

Two files when this experiment graduates:

1. `app/context/sentinel_live.py` — `fetch_recent_chips(lat, lon)` with
   the multi-source fallback chain, retry logic, per-MGRS cell cache
2. `app/context/terramind_nyc.py` — replaces `load_local_chips()` with
   a call to `sentinel_live.fetch_recent_chips`, otherwise unchanged

Plus tests in `tests/` against three NYC reference points (Manhattan
center, Brighton Beach, Bronx Zoo) with a mock STAC client for offline
CI.

## License + attribution

ESA Copernicus License: free for any use including commercial, with
attribution to Copernicus and the originating mission. Riprap's existing
attribution block needs to add "Sentinel-1 / Sentinel-2 imagery courtesy
of ESA Copernicus" alongside the existing NYC OpenData / NOAA / FEMA
attributions.
