/* Independent browser acceptance. BASE_URL points to the product server; no source imports.
   node product-browser.cjs  (requires the preinstalled Playwright and Chrome). */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const base = process.env.BASE_URL || 'http://127.0.0.1:8765';
const rid = process.env.RUN_ID || 'synth-good';
(async () => {
  const browser = await chromium.launch({executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined, headless: true});
  const ctx = await browser.newContext({viewport:{width:1440,height:900}, reducedMotion:'reduce'});
  const page = await ctx.newPage();
  const errors = [], unsafe = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('request', req => {
    const u = new URL(req.url());
    if (u.origin !== new URL(base).origin || (/\/api\//.test(u.pathname) && req.method() !== 'GET')) unsafe.push(`${req.method()} ${req.url()}`);
  });
  const json = async path => { const r = await page.request.get(base + path); assert.equal(r.status(), 200, path); return r.json(); };
  const searches = (await json(`/api/runs/${rid}/clay-searches`)).searches;
  const bundle = await json(`/api/runs/${rid}/bundle`);
  const cells = searches.flatMap(s => s.result.cells.map(c => ({...c, search:s.search_id})));
  assert.ok(cells.length, 'fixture must have Clay cells');
  assert.ok(bundle.claims.length && bundle.evidence.length, 'fixture must have claims and evidence');
  await page.goto(`${base}/runs/${rid}/sky`);
  await page.getByText(/geographic/i).first().waitFor();
  assert.equal(await page.getByText('Product API unavailable').count(), 0, 'capability data must decode successfully');
  const first = cells[0];
  await page.getByText(first.cell_id, {exact:false}).first().waitFor();
  await page.getByText(first.cell_id, {exact:false}).first().click();
  assert.ok((await page.locator('body').innerText()).includes(first.cell_id));
  const selectedURL = page.url();
  const mode = page.getByRole('button', {name:/story mode|developer mode/i}).first();
  await mode.click();
  assert.equal(page.url(), selectedURL, 'mode switch preserves selected run and cell URL');
  assert.ok((await page.locator('body').innerText()).includes(first.cell_id), 'mode switch preserves selected cell');
  await page.reload();
  await page.getByText(first.cell_id, {exact:false}).first().waitFor();
  assert.equal(page.url(), selectedURL, 'deep selection survives reload');
  await page.goto(`${base}/runs/${rid}/atlas`);
  const claim = bundle.claims.find(c => c.evidence_refs.length);
  assert.ok(claim);
  await page.getByRole('link', {name:'Dataset', exact:true}).click();
  await page.getByRole('button', {name:claim.claim_id, exact:true}).click();
  const ref = claim.evidence_refs[0].result_id;
  const evidence = bundle.evidence.find(e => e.result_id === ref);
  assert.ok(evidence, 'claim reference must resolve in bundle');
  await page.locator('tr').filter({has:page.getByRole('button',{name:claim.claim_id, exact:true})}).getByRole('link',{name:new RegExp(ref)}).first().click();
  const evidenceCard = page.locator('[data-evidence-id]').filter({hasText:ref});
  await evidenceCard.waitFor();
  assert.equal(await evidenceCard.getAttribute('data-evidence-id'), ref);
  await evidenceCard.getByText(evidence.scene_id, {exact:false}).first().waitFor();
  await page.getByRole('link', {name:'Summary', exact:true}).click();
  const text = await page.locator('body').innerText();
  assert.match(text, /synthetic/i); assert.match(text, /recorded|replay/i);
  assert.match(text, /not issued/i); assert.doesNotMatch(text, /(?:combined|overall) score\s*[:=]\s*\d/i);
  await page.getByRole('link', {name:'Evaluation', exact:true}).click();
  const metric = Object.values(bundle.scorecard.process.numbers).find(n => n.value !== null && n.type === 'count');
  assert.ok(metric, 'fixture must include a count metric');
  const metricCard = page.locator('[data-metric]').filter({has:page.getByText(metric.metric.replaceAll('_',' '), {exact:true})}).first();
  await metricCard.waitFor();
  assert.match(await metricCard.innerText(), new RegExp(String(metric.value)));
  if (metric.synthetic) assert.match(await metricCard.innerText(), /synthetic/i);
  if (metric.replayed) assert.match(await metricCard.innerText(), /recorded|replay/i);
  await metricCard.getByText('Method & provenance').click();
  assert.match(await metricCard.innerText(), new RegExp(metric.tier));
  await page.goto(`${base}/runs/${rid}/scene/${encodeURIComponent(claim.claim_id)}`);
  assert.match(await page.locator('body').innerText(), /planned|not available|unavailable/i);
  assert.doesNotMatch(await page.locator('body').innerText(), /start simulation/i);
  for (const width of [320,390,1440]) {
    await page.setViewportSize({width,height:900});
    for (const workspace of ['sky','atlas']) {
      await page.goto(`${base}/runs/${rid}/${workspace}`);
      await page.locator('main').first().waitFor();
      const dims = await page.evaluate(() => ({scroll:document.documentElement.scrollWidth, viewport:document.documentElement.clientWidth}));
      assert.ok(dims.scroll <= dims.viewport + 1, `${workspace} overflow at ${width}: ${JSON.stringify(dims)}`);
    }
  }
  await page.goto(`${base}/runs/${rid}/sky`);
  await page.keyboard.press('Tab');
  assert.ok(await page.evaluate(() => document.activeElement && document.activeElement !== document.body), 'keyboard focus must be visible in navigation');
  assert.equal(await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches), true);
  assert.deepEqual(unsafe, [], 'page loads must not contact remote services or start jobs');
  assert.deepEqual(errors, [], 'browser errors');
  await browser.close();
  console.log('Independent browser acceptance passed');
})().catch(e => {console.error(e); process.exit(1);});
