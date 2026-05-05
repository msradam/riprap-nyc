import type { Citation, BriefingBlock } from '$lib/types/claim';
import type { EvidenceItem } from '$lib/types/evidence';
import type { TraceNode } from '$lib/types/trace';

export const SAMPLE_QUERY = '80 Pioneer Street, Red Hook, Brooklyn';
export const SAMPLE_ADDRESS = '80 Pioneer Street · Red Hook · Brooklyn';

export const CITATIONS: Record<string, Citation> = {
  c1: { id: 'c1', n: 1, tier: 'empirical', source: 'USGS', title: 'Hurricane Sandy storm tide elevations, NY-NJ Harbor', docId: 'USGS-OFR-2013-1234', url: 'https://pubs.usgs.gov/of/2013/1234/', vintage: '2013-05', retrieved: '2026-04-28' },
  c2: { id: 'c2', n: 2, tier: 'empirical', source: 'NYC OEM', title: 'Hurricane Sandy Inundation Zone (2012)', docId: 'NYCOEM-SIZ-2013', url: 'https://data.cityofnewyork.us/dataset/sandy-inundation-zone', vintage: '2013-01', retrieved: '2026-04-28' },
  c3: { id: 'c3', n: 3, tier: 'empirical', source: 'FloodNet NYC', title: 'Sensor BK-RH-002 — Coffey Park, monthly exceedance', docId: 'FN-BK-RH-002', url: 'https://floodnet.nyc/sensor/BK-RH-002', vintage: '2026-04', retrieved: '2026-05-02' },
  c4: { id: 'c4', n: 4, tier: 'modeled', source: 'FEMA', title: 'Preliminary Flood Insurance Rate Map, panel 36047C0207G', docId: 'FEMA-FIRM-36047C0207G', url: 'https://msc.fema.gov/portal/search', vintage: '2024-09', retrieved: '2026-04-28' },
  c5: { id: 'c5', n: 5, tier: 'modeled', source: 'NYC DEP', title: 'Stormwater Flood Map — Moderate Stormwater Scenario', docId: 'NYCDEP-SWFM-2024', url: 'https://nyc.gov/stormwater-map', vintage: '2024-06', retrieved: '2026-04-28' },
  c6: { id: 'c6', n: 6, tier: 'modeled', source: 'NPCC4', title: 'Sea-level rise projections, 2050 90th percentile', docId: 'NPCC4-Ch3-Tbl3.2', url: 'https://nyas.org/npcc4', vintage: '2024-03', retrieved: '2026-04-28' },
  c7: { id: 'c7', n: 7, tier: 'proxy', source: 'NYC 311', title: 'Flooding service requests, BK CB6 2019–2025', docId: 'NYC311-FLD-CB6', url: 'https://data.cityofnewyork.us/311', vintage: '2025-12', retrieved: '2026-05-01' },
  c8: { id: 'c8', n: 8, tier: 'proxy', source: 'FEMA NFIP', title: 'National Flood Insurance Program claims, tract 36047008500', docId: 'NFIP-T36047008500', url: 'https://www.fema.gov/openfema', vintage: '2024-12', retrieved: '2026-04-28' },
  c9: { id: 'c9', n: 9, tier: 'synthetic', source: 'TerraMind v1.2', title: 'Synthetic SAR backscatter for 2025-09-14 (Sentinel-1 cloud-occluded)', docId: 'RIPRAP-SYN-20250914', url: '#methodology-synthetic', vintage: '2025-09', retrieved: '2026-05-02' },
  c10: { id: 'c10', n: 10, tier: 'modeled', source: 'NYC DCP', title: 'Waterfront Revitalization Program — Coastal Risk Area', docId: 'NYCDCP-WRP-2022', url: 'https://nyc.gov/dcp/wrp', vintage: '2022-11', retrieved: '2026-04-28' }
};

export const BRIEFING_BLOCKS: BriefingBlock[] = [
  {
    kind: 'status',
    html: `<p class="briefing-deck"><strong>80 Pioneer Street, Red Hook, Brooklyn 11231.</strong> Block 597, Lot 30. Industrial Business Zone (IBZ-RH). Queried 2026-05-02 14:22 ET. <span class="briefing-meta">Briefing v0.4.2 · 9 specialists fired · 1 silent (TidalGauge: out of range)</span></p>`
  },
  { kind: 'head', n: '01', label: 'Status', title: 'Coastal-edge, post-Sandy, multi-hazard' },
  {
    kind: 'prose',
    parts: [
      { tier: 'empirical', text: 'The address sits 380 ft inland of the Erie Basin bulkhead, at a ground elevation of 6.2 ft NAVD88', cite: 'c1' },
      { text: ' — within the ' },
      { tier: 'empirical', text: '2012 Sandy Inundation Zone, which recorded a peak storm tide of 11.4 ft NAVD88 at the Battery', cite: 'c2' },
      { text: ' 2.4 mi to the northwest. ' },
      { tier: 'modeled', text: "FEMA's preliminary FIRM places the parcel in Zone AE (BFE 11 ft NAVD88)", cite: 'c4' },
      { text: ', a 4.8 ft freeboard above current grade. The site is upgradient of two FloodNet sensors and three blocks from a chronic 311 cluster.' }
    ]
  },
  { kind: 'head', n: '02', label: 'Empirical evidence', tier: 'empirical' },
  {
    kind: 'prose',
    parts: [
      { tier: 'empirical', text: 'FloodNet sensor BK-RH-002 (Coffey Park, 1,200 ft south) recorded 7 above-curb events between 2024-06 and 2026-04', cite: 'c3' },
      { text: ", with a peak depth of 14.3 cm during the 2025-09-29 nor'easter. " },
      { tier: 'empirical', text: 'USGS post-Sandy high-water marks within 500 ft cluster between 6.8 and 8.1 ft NAVD88', cite: 'c1' },
      { text: ', consistent with 0.6–1.9 ft of standing water at the queried address during the storm.' }
    ]
  },
  { kind: 'head', n: '03', label: 'Modeled scenarios', tier: 'modeled' },
  {
    kind: 'prose',
    parts: [
      { tier: 'modeled', text: "DEP's Moderate Stormwater Scenario (2.13 in/hr design storm) shows ponding ≥4 in across the western half of the lot", cite: 'c5' },
      { text: ', routed by the 1.2% slope toward Imlay St. ' },
      { tier: 'modeled', text: "Under NPCC4's 2050 90th-percentile sea-level rise (30 in)", cite: 'c6' },
      { text: ', the parcel falls within the projected daily-tidal floodplain by mid-century. ' },
      { tier: 'synthetic', text: 'Synthetic SAR backscatter for 2025-09-14 (Sentinel-1 cloud-occluded) was generated by TerraMind v1.2 and is presented as a prior, not an observation', cite: 'c9' },
      { text: '; treat with appropriate caution.' }
    ]
  },
  { kind: 'head', n: '04', label: 'Policy context' },
  {
    kind: 'prose',
    parts: [
      { tier: 'proxy', text: '311 flood complaints within the surrounding census tract total 89 calls over 2019–2025, with seasonal clustering in Aug–Oct', cite: 'c7' },
      { text: '. ' },
      { tier: 'proxy', text: 'NFIP claims aggregated to tract 36047008500 total $4.1M across 47 paid losses since 2000', cite: 'c8' },
      { text: '. ' },
      { tier: 'modeled', text: 'The site lies within the NYC Waterfront Revitalization Program Coastal Risk Area; CEQR §817 review applies to any discretionary action', cite: 'c10' },
      { text: '.' }
    ]
  }
];

export const EVIDENCE: EvidenceItem[] = [
  {
    id: 'e1', citeId: 'c1', tier: 'empirical', source: 'USGS',
    title: 'Post-Sandy high-water marks within 500ft',
    fmt: { kind: 'table', columns: ['id', 'elev.', 'dist.'],
      rows: [['HWM-NY-3081', '7.4 ft NAVD88', '0.18 mi'],
             ['HWM-NY-3082', '8.1 ft NAVD88', '0.22 mi'],
             ['HWM-NY-3105', '6.8 ft NAVD88', '0.31 mi']] },
    docId: 'USGS-OFR-2013-1234', vintage: '2013-05'
  },
  {
    id: 'e2', citeId: 'c3', tier: 'empirical', source: 'FloodNet NYC',
    title: 'Sensor BK-RH-002 — monthly above-curb events',
    fmt: { kind: 'spark',
      data: [0,0,1,0,2,1,0,0,3,0,1,0,0,0,2,1,0,0,1,0,2,4,1,1],
      headline: '7 events', sub: "Jun 2024 → Apr 2026 · peak 14.3 cm" },
    docId: 'FN-BK-RH-002', vintage: '2026-04'
  },
  {
    id: 'e3', citeId: 'c4', tier: 'modeled', source: 'FEMA',
    title: 'Preliminary FIRM, panel 36047C0207G',
    fmt: { kind: 'scalar', value: 'Zone AE', unit: 'BFE 11 ft NAVD88', aux: 'freeboard +4.8 ft' },
    docId: 'FEMA-FIRM-36047C0207G', vintage: '2024-09'
  },
  {
    id: 'e4', citeId: 'c5', tier: 'modeled', source: 'NYC DEP',
    title: 'Stormwater Flood Map — moderate scenario',
    fmt: { kind: 'thumb', thumbKind: 'stormwater',
      sub: '2.13 in/hr · ponding ≥4 in W half of lot · routed toward Imlay St' },
    docId: 'NYCDEP-SWFM-2024', vintage: '2024-06'
  },
  {
    id: 'e5', citeId: 'c6', tier: 'modeled', source: 'NPCC4',
    title: 'Sea-level rise projections for Lower NY Harbor',
    fmt: { kind: 'forecast',
      data: [
        { year: 2030, low: 4, mid: 6, high: 9 },
        { year: 2050, low: 13, mid: 22, high: 30 },
        { year: 2080, low: 28, mid: 49, high: 75 },
        { year: 2100, low: 38, mid: 71, high: 114 }
      ],
      caption: 'inches MSL · 17th–83rd %ile range, median line' },
    docId: 'NPCC4-Ch3-Tbl3.2', vintage: '2024-03'
  },
  {
    id: 'e6', citeId: 'c9', tier: 'synthetic', source: 'TerraMind v1.2',
    title: 'Synthetic SAR for 2025-09-14 (Sentinel-1 cloud-occluded)',
    fmt: { kind: 'thumb', thumbKind: 'synthetic',
      sub: 'Generated, not observed. Confidence 0.71. Provided as prior for downstream models; do not cite as observation.' },
    docId: 'RIPRAP-SYN-20250914', vintage: '2025-09'
  },
  {
    id: 'e7', citeId: 'c7', tier: 'proxy', source: 'NYC 311',
    title: 'Flood complaints, BK CB6 (2019–2025)',
    fmt: { kind: 'histogram',
      data: [3,2,1,0,1,4,7,12,18,11,5,3,4,2,1,0,2,3,8,9,4,2,1,0],
      headline: '89 calls', sub: 'seasonal cluster Aug–Oct' },
    docId: 'NYC311-FLD-CB6', vintage: '2025-12'
  },
  {
    id: 'e8', citeId: 'c8', tier: 'proxy', source: 'FEMA NFIP',
    title: 'NFIP claims, tract 36047008500',
    fmt: { kind: 'scalar', value: '$4.1M', unit: '47 paid losses', aux: 'since 2000-01-01' },
    docId: 'NFIP-T36047008500', vintage: '2024-12'
  }
];

export const TRACE_ROOT: TraceNode = {
  id: 'root', name: 'briefing.run', status: 'ok', ms: 14820, tier: null,
  children: [
    { id: 'n1', name: 'geocode.address', status: 'ok', ms: 142, tier: null,
      output: { lat: 40.6776, lon: -74.0096, bbl: '3005970030' } },
    { id: 'n2', name: 'fan_out.specialists', status: 'fan', ms: 0, tier: null,
      note: '9 specialists dispatched in parallel',
      children: [
        { id: 's1', name: 'sandy_inundation.lookup', status: 'ok', ms: 380, tier: 'empirical', claims: 2, output: 'polygon: contains; nearest HWM 0.4mi' },
        { id: 's2', name: 'floodnet.history', status: 'ok', ms: 1240, tier: 'empirical', claims: 1, output: 'BK-RH-002: 7 events, peak 14.3cm' },
        { id: 's3', name: 'usgs.high_water_marks', status: 'ok', ms: 612, tier: 'empirical', claims: 1, output: '9 marks within 500ft' },
        { id: 's4', name: 'fema.firm.preliminary', status: 'ok', ms: 488, tier: 'modeled', claims: 1, output: 'Zone AE, BFE 11ft NAVD88' },
        { id: 's5', name: 'dep.stormwater.scenario', status: 'ok', ms: 2104, tier: 'modeled', claims: 1, output: 'moderate: ponding ≥4in W half' },
        { id: 's6', name: 'npcc4.slr.projection', status: 'ok', ms: 320, tier: 'modeled', claims: 1, output: '2050 90th: +30in' },
        { id: 's7', name: 'nyc311.flood_complaints', status: 'ok', ms: 980, tier: 'proxy', claims: 1, output: '89 calls / tract / 2019–25' },
        { id: 's8', name: 'nfip.claims_aggregate', status: 'ok', ms: 540, tier: 'proxy', claims: 1, output: '$4.1M / 47 paid losses' },
        { id: 's9', name: 'terramind.synthetic_sar', status: 'ok', ms: 6840, tier: 'synthetic', claims: 1, output: 'synthesis confidence 0.71' },
        { id: 's10', name: 'tidal_gauge.range', status: 'silent', ms: 18, tier: null, claims: 0, output: 'out of range: nearest gauge >2mi' },
        { id: 's11', name: 'wrp.coastal_risk_area', status: 'ok', ms: 210, tier: 'modeled', claims: 1, output: 'within Coastal Risk Area' }
      ]
    },
    { id: 'n3', name: 'merge.evidence', status: 'merge', ms: 92, tier: null, note: '10 cards · 1 silent · 0 errors' },
    { id: 'n4', name: 'compose.briefing', status: 'ok', ms: 1380, tier: null, output: '4 sections · 11 claims · 10 citations' },
    { id: 'n5', name: 'stream.sse', status: 'ok', ms: 4940, tier: null, output: '1812 tokens · 11 sentence chunks' }
  ]
};
