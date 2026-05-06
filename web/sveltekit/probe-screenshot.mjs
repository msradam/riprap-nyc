import { chromium } from '@playwright/test';
const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
await page.goto('http://127.0.0.1:7860/', { waitUntil: 'networkidle' });
await page.waitForTimeout(2500);  // give tiles time to settle
const pane = await page.$('.land-preview-pane-map');
await pane.screenshot({ path: '/tmp/riprap/landing_map.png' });
console.log('saved /tmp/riprap/landing_map.png');
await browser.close();
