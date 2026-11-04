/* Explicit user-initiated replay flow. Use ONLY a server backed by a disposable store copy. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const base = process.env.BASE_URL || 'http://127.0.0.1:8765';
(async () => {
  assert.equal(process.env.DISPOSABLE_STORE, 'yes', 'Set DISPOSABLE_STORE=yes only for a copied store');
  const browser = await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined,headless:true});
  const context = await browser.newContext({reducedMotion:'reduce',viewport:{width:1440,height:900}});
  const page = await context.newPage(); const posts = [], errors = [];
  page.on('request', r => { if (r.method() !== 'GET') posts.push({url:r.url(),body:r.postDataJSON()}); });
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  const tasksResponse = await page.request.get(`${base}/api/tasks`);
  assert.equal(tasksResponse.status(),200);
  const tasks = (await tasksResponse.json()).tasks; assert.ok(tasks.length);
  await page.goto(`${base}/new`);
  assert.equal(posts.length,0,'opening Book must not start a job');
  await page.getByRole('button',{name:/start|run replay/i}).first().click();
  await page.waitForURL(/\/runs\/[^/]+\/(sky|atlas)/, {timeout:30000});
  assert.equal(posts.length,1,'one explicit start creates exactly one job');
  assert.equal(new URL(posts[0].url).pathname,'/api/runs');
  assert.deepEqual(Object.keys(posts[0].body),['preset_id']);
  assert.ok(tasks.some(t => t.preset_id === posts[0].body.preset_id));
  const rid = new URL(page.url()).pathname.split('/')[2];
  let response, b; const deadline = Date.now() + 60000;
  do {
    response = await page.request.get(`${base}/api/runs/${rid}/bundle`);
    if (response.status() === 200) { b = await response.json(); break; }
    assert.equal(response.status(), 409, `unexpected replay status: ${await response.text()}`);
    await new Promise(resolve => setTimeout(resolve, 250));
  } while (Date.now() < deadline);
  assert.ok(b, `replay did not complete; last HTTP ${response.status()}`);
  assert.equal(b.manifest_summary.mode,'replay');
  const v = await (await page.request.get(`${base}/api/runs/${rid}/verify`)).json(); assert.equal(v.ok,true);
  assert.equal(posts.length,1,'polling and navigation must not create another job');
  assert.deepEqual(errors,[]);
  await browser.close(); console.log(`Explicit pinned replay passed: ${rid}`);
})().catch(e => {console.error(e);process.exit(1)});
