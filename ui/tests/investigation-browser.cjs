/* Run against a live local server with TREEHOUSE_UI_URL and TREEHOUSE_TEST_RUN_ID set.
   The seeded run must contain one positive claim with linked decision, prior evidence,
   alternatives and a parent decision. Test behavior; selectors use accessible names. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.TREEHOUSE_UI_URL;
  const runId = process.env.TREEHOUSE_TEST_RUN_ID;
  assert(base && runId, 'Set TREEHOUSE_UI_URL and TREEHOUSE_TEST_RUN_ID to a seeded local run');
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined });
  try {
    const page = await browser.newPage({ reducedMotion: 'reduce' });
    await page.goto(base, { waitUntil: 'networkidle' });
    await page.getByText(runId, { exact: false }).first().click();
    const pane = page.getByRole('button', { name: /investigation/i }).or(page.getByRole('tab', { name: /investigation/i })).first();
    await pane.click();
    await page.getByText(/rationale/i).first().waitFor();
    assert(await page.getByText(/alternative/i).count(), 'alternatives visible');
    assert(await page.getByText(/confidence/i).count(), 'agent confidence visible');
    assert(await page.getByText(/self.report|agent.claim/i).count(), 'confidence labeled as agent self-report');
    assert(await page.getByText(/evidence/i).count(), 'prior evidence links visible');
    assert(await page.getByText(/outcome|success|blocked|error/i).count(), 'actual action outcome visible');
    assert(await page.getByRole('table').count(), 'prediction table visible');
    const marker = page.getByRole('button', { name: /prediction.*marker|marker.*prediction/i }).first();
    await marker.focus();
    await page.keyboard.press('Enter');
    assert(await page.getByText(/claim/i).count(), 'selected marker identifies claim');
    assert(await page.getByText(/decision/i).count(), 'selected marker links its decision');
    const shot = await marker.screenshot();
    assert(shot.length > 0, 'marker rendered');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
