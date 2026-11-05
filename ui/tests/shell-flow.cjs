/* Drives the storybook and dev view at real speed against the mock dev server.
   Run: npm run dev (port in TREEHOUSE_UI_URL, default http://127.0.0.1:5173), then npm run test:flow.
   Screenshots go to SHOTS_DIR (default ./test-results/shell). Fails on console errors or unreadable text. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const base = process.env.TREEHOUSE_UI_URL || 'http://127.0.0.1:5173';
const out = process.env.SHOTS_DIR || path.join(__dirname, '..', 'test-results', 'shell');
fs.mkdirSync(out, {recursive: true});
const sleep = ms => new Promise(r => setTimeout(r, ms));
// WCAG contrast of an element's text against the nearest opaque background behind it.
const contrastOf = el => el.evaluate(node => {
  const rgb = s => s.match(/[\d.]+/g).map(Number);
  const lum = ([r, g, b]) => [r, g, b].map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }).reduce((a, v, i) => a + v * [0.2126, 0.7152, 0.0722][i], 0);
  let bg = null, n = node;
  while (n && !bg) { const c = rgb(getComputedStyle(n).backgroundColor); if (c.length < 4 || c[3] > 0.9) bg = c; n = n.parentElement; }
  const a = lum(rgb(getComputedStyle(node).color)), b = lum(bg || [255, 255, 255]);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
});

(async () => {
  // PW_CHANNEL=chrome reuses an installed Google Chrome instead of downloading Playwright's build.
  const browser = await chromium.launch({headless: true, channel: process.env.PW_CHANNEL || undefined, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined});
  const errors = [];
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 900}});
    page.on('console', m => { if (m.type() === 'error' && !m.text().startsWith('Failed to load resource')) errors.push(m.text()); });
    page.on('pageerror', e => errors.push(String(e)));
    // GSI has no aerial tile for some open-sea squares; those 404s are expected, anything else is not.
    page.on('response', r => { if (r.status() >= 400 && !r.url().includes('cyberjapandata.gsi.go.jp')) errors.push(`${r.status()} ${r.url()}`); });
    const shot = name => page.screenshot({path: path.join(out, `${name}.png`)});

    await page.goto(base + '/');
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await sleep(1400); await shot('01-intro');
    const open = page.getByRole('button', {name: 'Open the treehouse'});
    assert.equal(await open.evaluate(b => getComputedStyle(b.closest('.intro-cta')).opacity), '1', 'intro card visible');
    await page.mouse.move(720, 380);
    assert.equal(await page.locator('canvas.world').evaluate(c => c.style.cursor), 'pointer', 'treehouse shows it is clickable');
    await page.mouse.click(720, 380);   // clicking the treehouse starts the zoom
    for (const [ms, name] of [[1300, '02-zoom'], [1400, '03-room-hold'], [1300, '04-into-book']]) { await sleep(ms); await shot(name); }
    const goal = page.locator('#goal');
    await goal.waitFor({timeout: 8000}); await sleep(600); await shot('05-book');
    for (const el of [goal, page.locator('.book select').first(), page.locator('.book h2').first()]) {
      const c = await contrastOf(el); assert(c >= 4.5, `book text contrast ${c.toFixed(2)} < 4.5`);
    }
    await page.locator('.book select').nth(1).selectOption('strands-nova');
    await page.getByRole('button', {name: 'Send the agent'}).click();
    for (let i = 0; i < 14; i++) { await sleep(700); await shot(`06-getup-${String(i).padStart(2, '0')}`); }
    await page.locator('.map-stage').waitFor({timeout: 15000});
    await sleep(2500); await shot('07-map-early');
    assert.match(await page.locator('.agent-line').innerText(), /nova/i, 'chosen agent shown');
    assert.match(await page.locator('.meters').innerText(), /since start/i, 'timer counts from start');
    await page.getByRole('button', {name: 'Read the full summary'}).waitFor({timeout: 80000});
    await sleep(800); await shot('08-map-done');
    await page.getByRole('button', {name: 'Read the full summary'}).click();
    await sleep(400); await shot('09-summary');
    await page.keyboard.press('Escape');

    // reduced motion: zooms become cuts
    const calm = await browser.newPage({viewport: {width: 1280, height: 800}, reducedMotion: 'reduce'});
    calm.on('pageerror', e => errors.push(String(e)));
    await calm.goto(base + '/'); await calm.evaluate(() => localStorage.clear()); await calm.reload();
    await calm.getByRole('button', {name: 'Open the treehouse'}).click();
    await calm.locator('#goal').waitFor({timeout: 1500});

    // dev view: recorded run, select the Strands step, map shows that moment
    await page.goto(base + '/dev?run=mock-nagoya-recorded');
    await page.locator('.rows li').first().waitFor();
    await sleep(1500); await shot('10-dev');
    await page.locator('.rows button', {hasText: 'strands_label'}).click();
    await sleep(1500); await shot('11-dev-strands');
    assert.match(await page.locator('.map-head').innerText(), /strands_label/, 'map follows the selected step');
    await page.locator('.rows button', {hasText: 'build_index'}).click();
    await sleep(1200); await shot('12-dev-build-index');
    assert.deepEqual(errors.filter(e => !/favicon/.test(e)), [], 'no console errors');
    console.log(`ok: flow passed; screenshots in ${out}`);
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
