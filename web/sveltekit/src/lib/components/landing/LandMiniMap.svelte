<script lang="ts">
  import { onMount } from 'svelte';
  import { POSITRON } from '$lib/components/map/baseStyle';
  import 'maplibre-gl/dist/maplibre-gl.css';

  /** Tiny MapLibre instance for the landing-page "What you'll get back"
   *  preview. Stays inside the 6:5 container of the third pane; no nav
   *  controls, no scale, no popups — just the basemap, a small AE-zone
   *  polygon, an HWM contour, a few 311 dots, a FloodNet pin, and the
   *  queried-address pin. Centered on 80 Pioneer Street, Red Hook. */

  // 80 Pioneer Street, Red Hook, Brooklyn — same anchor the briefing
  // and sample fixture use. Zoom 14.5 keeps the neighborhood context.
  const ADDR: [number, number] = [-74.0095, 40.6781];

  let container: HTMLDivElement | null = $state(null);

  // The `map` ref is captured outside the async loader so the synchronous
  // teardown returned from onMount() can dispose of it. onMount() doesn't
  // accept a teardown returned from an async callback in Svelte 5, so we
  // bridge through a mutable closure variable.
  type Map = import('maplibre-gl').Map;
  let map: Map | null = null;

  onMount(() => {
    let cancelled = false;
    (async () => {
      if (!container || cancelled) return;
      const maplibre = await import('maplibre-gl');
      if (cancelled || !container) return;
      map = new maplibre.Map({
        container,
        style: POSITRON,
        center: ADDR,
        zoom: 14.5,
        interactive: false,
        attributionControl: false,
      });

      map.on('load', () => {
        if (!map) return;
      // Coastline FEMA AE-style polygon — a few blocks centered on the
      // address. Modeled-tier translucent fill + dashed line.
      map.addSource('fema-ae', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: [{
            type: 'Feature', properties: {},
            geometry: {
              type: 'Polygon',
              coordinates: [[
                [-74.0140, 40.6790],
                [-74.0070, 40.6800],
                [-74.0050, 40.6770],
                [-74.0090, 40.6755],
                [-74.0140, 40.6790],
              ]],
            },
          }],
        },
      });
      map.addLayer({
        id: 'fema-ae-fill', type: 'fill', source: 'fema-ae',
        paint: { 'fill-color': '#2A6FA8', 'fill-opacity': 0.22 },
      });
      map.addLayer({
        id: 'fema-ae-line', type: 'line', source: 'fema-ae',
        paint: { 'line-color': '#2A6FA8', 'line-width': 1, 'line-dasharray': [3, 2] },
      });

      // Empirical HWM contour — short curve north of the address.
      map.addSource('hwm-contour', {
        type: 'geojson',
        data: {
          type: 'Feature', properties: {},
          geometry: {
            type: 'LineString',
            coordinates: [
              [-74.0125, 40.6790],
              [-74.0105, 40.6792],
              [-74.0080, 40.6790],
              [-74.0060, 40.6786],
            ],
          },
        },
      });
      map.addLayer({
        id: 'hwm-contour-line', type: 'line', source: 'hwm-contour',
        paint: { 'line-color': '#0B5394', 'line-width': 1.4 },
      });

      // 311 cluster — three open circles south-west of the pin.
      map.addSource('proxy-311', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: [
            [-74.0118, 40.6770], [-74.0114, 40.6767], [-74.0121, 40.6772],
          ].map((c) => ({
            type: 'Feature', properties: {},
            geometry: { type: 'Point', coordinates: c },
          })),
        },
      });
      map.addLayer({
        id: 'proxy-311-circle', type: 'circle', source: 'proxy-311',
        paint: {
          'circle-radius': 3,
          'circle-color': 'transparent',
          'circle-stroke-color': '#6B6B6B',
          'circle-stroke-width': 1,
        },
      });

      // Empirical FloodNet sensor — a small filled square (rendered as
      // a circle since maplibre-gl doesn't draw squares natively; the
      // landing's tier legend covers the symbology distinction).
      map.addSource('floodnet', {
        type: 'geojson',
        data: {
          type: 'Feature', properties: {},
          geometry: { type: 'Point', coordinates: [-74.0103, 40.6788] },
        },
      });
      map.addLayer({
        id: 'floodnet-pin', type: 'circle', source: 'floodnet',
        paint: {
          'circle-radius': 4,
          'circle-color': '#0B5394',
          'circle-stroke-color': '#FFFFFF',
          'circle-stroke-width': 1,
        },
      });

      // Queried address pin — concentric circles, paper-on-ink.
      map.addSource('addr', {
        type: 'geojson',
        data: {
          type: 'Feature', properties: {},
          geometry: { type: 'Point', coordinates: ADDR },
        },
      });
      map.addLayer({
        id: 'addr-ring', type: 'circle', source: 'addr',
        paint: {
          'circle-radius': 9,
          'circle-color': 'transparent',
          'circle-stroke-color': '#0F172A',
          'circle-stroke-width': 1.4,
        },
      });
      map.addLayer({
          id: 'addr-dot', type: 'circle', source: 'addr',
          paint: { 'circle-radius': 3, 'circle-color': '#0F172A' },
        });
      });
    })();

    return () => {
      cancelled = true;
      if (map) {
        map.remove();
        map = null;
      }
    };
  });
</script>

<div class="land-mapmini" role="img" aria-label="Live mini-map preview of Red Hook flood exposure layers">
  <div bind:this={container} class="land-mapmini-canvas"></div>
  <div class="land-mapmini-legend">
    <span><span class="lm-sw lm-sw-emp"></span>empirical</span>
    <span><span class="lm-sw lm-sw-mod"></span>modeled</span>
    <span><span class="lm-sw lm-sw-prx"></span>proxy</span>
  </div>
</div>

<style>
  .land-mapmini {
    position: relative;
    aspect-ratio: 6 / 5;
    border: 1px solid var(--rule-soft);
    overflow: hidden;
    background: var(--paper-deep);
  }
  .land-mapmini-canvas {
    position: absolute;
    inset: 0;
  }
  .land-mapmini-legend {
    position: absolute;
    left: 6px;
    bottom: 6px;
    right: 6px;
    display: flex;
    gap: 10px;
    padding: 4px 6px;
    background: rgba(255, 255, 255, 0.92);
    font-family: var(--font-mono);
    font-size: 9.5px;
    letter-spacing: 0.04em;
    color: var(--ink-secondary);
    z-index: 1;
    pointer-events: none;
  }
  .land-mapmini-legend span {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .lm-sw { display: inline-block; width: 8px; height: 8px; }
  .lm-sw-emp { background: var(--tier-empirical); }
  .lm-sw-mod {
    background: rgba(42, 111, 168, 0.4);
    border: 1px dashed var(--tier-modeled);
  }
  .lm-sw-prx {
    background: transparent;
    border: 1px solid #6B6B6B;
    border-radius: 50%;
  }
</style>
