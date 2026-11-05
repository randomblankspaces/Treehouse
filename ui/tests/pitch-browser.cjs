/* Drives /pitch: every slide renders, the recorded demo steps 1 → 2 → 3 on scroll, modes switch, no page errors,
   no horizontal overflow on desktop or phone. Works against `npm run dev` (recorded mode needs no API) or
   `treehouse ui serve` (TREEHOUSE_UI_URL=http://127.0.0.1:8765). Run: npm run test:pitch.
   Screenshots go to SHOTS_DIR (default ./test-results/pitch). */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const base = process.env.TREEHOUSE_UI_URL || 'http://127.0.0.1:5173';
const out = process.env.SHOTS_DIR || path.join(__dirname, '..', 'test-results', 'pitch');
fs.mkdirSync(out, {recursive: true});
const SLIDES = ['problem', 'context', 'backwards', 'solution', 'architecture', 'demo', 'numbers', 'impact', 'future'];

(async () => {
  const browser = await chromium.launch({headless: true, channel: process.env.PW_CHANNEL || undefined, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined});
  const errors = [];
  try {
    for (const [name, viewport] of [['desktop', {width: 1440, height: 900}], ['phone', {width: 390, height: 844}]]) {
      const page = await browser.newPage({viewport, reducedMotion: 'reduce'});
      page.on('pageerror', e => errors.push(`${name}: ${e}`));
      page.on('console', m => { if (m.type() === 'error' && !m.text().startsWith('Failed to load resource')) errors.push(`${name}: ${m.text()}`); });
      await page.goto(base + '/pitch?demo=recorded', {waitUntil: 'networkidle'});
      for (const id of SLIDES) {
        await page.evaluate(i => document.getElementById(i).scrollIntoView(), id);
        await page.waitForTimeout(250);
        assert.equal(await page.locator(`#${id}`).getAttribute('data-in'), '1', `${name}: slide ${id} revealed`);
        await page.screenshot({path: path.join(out, `${name}-${id}.png`)});
      }
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${name}: no horizontal overflow`);
      if (name === 'desktop') {
        const stageOn = () => page.locator('.stages li.on').innerText();
        for (const [i, title] of ['The agent investigates', 'Every step is captured', 'The run is scored'].entries()) {
          await page.evaluate(s => scrollTo(0, document.getElementById('demo').offsetTop + s * innerHeight), i);
          await page.waitForTimeout(300);
          assert.match(await stageOn(), new RegExp(title), `stage ${i + 1}`);
        }
        await page.getByText('synthetic fixtures').first().waitFor();
        await page.getByRole('radio', {name: 'Live on Bedrock'}).click();
        await page.getByRole('heading', {name: /Pinned live task|Warehouses|server isn’t reachable/}).first().waitFor();
        await page.getByRole('radio', {name: 'Treehouse app'}).click();
        await page.locator('.embedded, .notice').first().waitFor();
        await page.keyboard.press('t');
        assert.equal(await page.locator('.pitch').getAttribute('data-theme'), 'light', 'T toggles the theme');
      }
      await page.close();
    }
    assert.deepEqual(errors, [], errors.join('\n'));
    console.log(`pitch ok: ${SLIDES.length} slides, 3 demo stages, 3 modes; screenshots in ${out}`);
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e); process.exit(1); });
