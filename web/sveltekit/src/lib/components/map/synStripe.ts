/**
 * v0.4.2 §14 — syn-stripe-45 fill pattern, two density variants.
 *
 * High-density (`syn-stripe-45`) for `tier-synthetic-fill` at z14–z17.
 * Low-density (`syn-stripe-45-low`) for the briefing-prose synthetic-prior
 * glyph at 9–18 px (the high-density tile becomes noise that small).
 *
 * The SVG sources are the canonical 12×12 tiles from the spec page;
 * registerSynStripe loads each into MapLibre as a named image so
 * `paint.fill-pattern: 'syn-stripe-45'` resolves at render time.
 */
import type { Map as MapLibreMap } from 'maplibre-gl';

export const SYN_STRIPE_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">
  <rect width="12" height="12" fill="rgba(42,111,168,0.18)"/>
  <g stroke="#2A6FA8" stroke-width="1.4">
    <line x1="-2" y1="2"  x2="14" y2="-14"/>
    <line x1="-2" y1="8"  x2="14" y2="-8"/>
    <line x1="-2" y1="14" x2="14" y2="-2"/>
    <line x1="-2" y1="20" x2="14" y2="4"/>
  </g>
</svg>`;

export const SYN_STRIPE_LOWDENSITY_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">
  <rect width="12" height="12" fill="rgba(42,111,168,0.16)"/>
  <g stroke="#2A6FA8" stroke-width="1.1">
    <line x1="-2" y1="6"  x2="14" y2="-10"/>
    <line x1="-2" y1="14" x2="14" y2="-2"/>
    <line x1="-2" y1="22" x2="14" y2="6"/>
  </g>
</svg>`;

async function svgToImage(src: string, density: number): Promise<HTMLImageElement> {
  const blob = new Blob([src], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const i = new Image(density, density);
      i.onload = () => resolve(i);
      i.onerror = (err) => reject(err);
      i.src = url;
    });
    return img;
  } finally {
    URL.revokeObjectURL(url);
  }
}

/**
 * Register both density variants of syn-stripe-45 + a 2x retina copy of
 * the high-density tile. Call once after `map.on('style.load', ...)`.
 */
export async function registerSynStripe(map: MapLibreMap): Promise<void> {
  const variants: Array<[string, string, number]> = [
    ['syn-stripe-45', SYN_STRIPE_SVG, 12],
    ['syn-stripe-45-2x', SYN_STRIPE_SVG, 24],
    ['syn-stripe-45-low', SYN_STRIPE_LOWDENSITY_SVG, 12]
  ];
  for (const [id, src, density] of variants) {
    if (map.hasImage(id)) continue;
    try {
      const img = await svgToImage(src, density);
      map.addImage(id, img, { pixelRatio: density / 12 });
    } catch (err) {
      console.warn(`syn-stripe registration failed for ${id}`, err);
    }
  }
}
