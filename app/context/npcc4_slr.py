"""NPCC4 sea-level rise projections for NYC (static lookup).

Source: New York City Panel on Climate Change 4th Assessment (2024),
Chapter 3, Table 3.2 — sea-level rise relative to 2000–2004 baseline,
Battery Tide Gauge (NOAA 8518750), primary NYC harbor reference.

Values are in inches above the 2000–2004 mean. The NPCC4 uses a
probabilistic framework across RCP/SSP scenarios; the table excerpted
here represents the "likely range" (10th–90th) plus the high-end
"extreme" scenario (99th).
"""

DOC_ID = "npcc4_slr"
CITATION = (
    "New York City Panel on Climate Change 4th Assessment (NPCC4 2024), "
    "Chapter 3 — Sea Level Rise, Table 3.2. "
    "Published by the New York Academy of Sciences. "
    "Reference gauge: NOAA Battery (8518750), baseline 2000–2004."
)

# Sea-level rise projections in INCHES above the 2000–2004 baseline,
# Battery Tide Gauge. Percentiles: 10th (low), 50th (mid), 90th (high),
# 99th (extreme). All values from NPCC4 (2024) Ch. 3 Table 3.2.
_TABLE_IN = {
    2050: {10: 8,  50: 15, 90: 29, 99: 40},
    2100: {10: 13, 50: 31, 90: 65, 99: 96},
}


def _in_to_m(inches: float) -> float:
    return round(inches * 0.0254, 2)


def get_projections() -> dict:
    """Return NPCC4 SLR projection dict, always available (static table)."""
    result: dict = {"available": True, "baseline": "2000–2004", "gauge": "NOAA Battery (8518750)"}
    for year, pcts in _TABLE_IN.items():
        result[str(year)] = {
            str(pct): {"in": v, "m": _in_to_m(v)}
            for pct, v in pcts.items()
        }
    return result
