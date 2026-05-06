import { chromium } from '@playwright/test';
const browser = await chromium.launch();
const page = await (await browser.newContext()).newPage();
const errors = [];
page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
page.on('console', (m) => {
  if (['error','warning'].includes(m.type())) errors.push(m.type()+': '+m.text());
});
await page.goto('http://127.0.0.1:7860/', { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);
const dims = await page.evaluate(() => {
  const c = document.querySelector('.land-mapmini-canvas');
  if (!c) return { found: false };
  const r = c.getBoundingClientRect();
  const canvas = c.querySelector('canvas.maplibregl-canvas');
  return { found: true, w: r.width, h: r.height, inner_html_len: c.innerHTML.length,
           has_canvas: !!canvas, canvas_w: canvas?.width, canvas_h: canvas?.height };
});
console.log('canvas dims:', JSON.stringify(dims));
console.log('errors:', errors.length ? errors.join('\n') : 'none');
await browser.close();
